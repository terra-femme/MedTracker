"""
MedicationAgent - Manages medication CRUD operations

Responsibilities:
- Create medications with schedules
- Read medication details
- Update medications (including schedules)
- Archive/restore medications
- Delete medications

Does NOT:
- Log doses (DoseAgent)
- Calculate adherence (AdherenceAgent)
- Manage schedule display (ScheduleAgent)
"""

from typing import List, Dict, Optional
from dataclasses import dataclass
from datetime import date, time, datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class MedicationInfo:
    id: int
    name: str
    dosage: str
    frequency: str
    start_date: date
    reminder_times: List[str]
    is_active: bool
    created_at: datetime
    last_taken: Optional[datetime] = None


class MedicationAgent:
    """
    Agent for managing medication records
    
    Usage:
        agent = MedicationAgent(db_session)
        med = agent.create(name="Advil", dosage="200mg", frequency="twice_daily")
        agent.update_schedule(med.id, reminder_times=["08:00", "20:00"])
    """
    
    def __init__(self, db_session, user_id: int = None):
        self.db = db_session
        self.user_id = user_id

    def create(self, name: str, dosage: Optional[str] = None,
               frequency: str = "once_daily",
               start_date: Optional[date] = None,
               reminder_times: Optional[List[str]] = None) -> MedicationInfo:
        """
        Create a new medication with schedule
        
        Args:
            name: Medication name
            dosage: Dosage info (e.g., "200mg")
            frequency: Frequency key
            start_date: When to start (default: today)
            reminder_times: List of "HH:MM" times
            
        Returns:
            Created MedicationInfo
        """
        from backend.models import Medication, Reminder
        
        if start_date is None:
            start_date = date.today()
        
        # Create medication
        med = Medication(
            name=name,
            dosage=dosage,
            frequency=frequency,
            start_date=start_date
        )
        
        self.db.add(med)
        self.db.flush()  # Get ID
        
        # Create reminders
        if reminder_times:
            for time_str in reminder_times:
                reminder = Reminder(
                    medication_id=med.id,
                    reminder_time=self._parse_time(time_str),
                    is_active=True
                )
                self.db.add(reminder)
        else:
            # Create default reminders based on frequency
            default_times = self._get_default_times(frequency)
            for t in default_times:
                reminder = Reminder(
                    medication_id=med.id,
                    reminder_time=t,
                    is_active=True
                )
                self.db.add(reminder)
        
        self.db.commit()
        self.db.refresh(med)
        
        logger.info(f"Created medication: {name}")
        
        return self._to_info(med)
    
    def get(self, medication_id: int) -> Optional[MedicationInfo]:
        """Get medication by ID"""
        from backend.models import Medication
        
        med = self.db.query(Medication).filter(Medication.id == medication_id).first()
        
        if not med:
            return None
        
        return self._to_info(med)
    
    def get_all(self, include_archived: bool = False) -> List[MedicationInfo]:
        """Get all medications"""
        from backend.models import Medication
        
        query = self.db.query(Medication)
        
        if not include_archived:
            query = query.filter(Medication.is_active == True)
        
        meds = query.order_by(Medication.name).all()
        
        return [self._to_info(m) for m in meds]
    
    def update(self, medication_id: int, 
               name: Optional[str] = None,
               dosage: Optional[str] = None,
               frequency: Optional[str] = None,
               start_date: Optional[date] = None,
               reminder_times: Optional[List[str]] = None) -> Optional[MedicationInfo]:
        """
        Update medication details
        
        If reminder_times is provided, replaces all existing reminders
        """
        from backend.models import Medication, Reminder
        
        med = self.db.query(Medication).filter(Medication.id == medication_id).first()
        
        if not med:
            return None
        
        # Update fields
        if name is not None:
            med.name = name
        if dosage is not None:
            med.dosage = dosage
        if frequency is not None:
            med.frequency = frequency
        if start_date is not None:
            med.start_date = start_date
        
        # Update reminder times if provided
        if reminder_times is not None:
            # Delete existing reminders
            self.db.query(Reminder).filter(
                Reminder.medication_id == medication_id
            ).delete()
            
            # Create new ones
            for time_str in reminder_times:
                reminder = Reminder(
                    medication_id=medication_id,
                    reminder_time=self._parse_time(time_str),
                    is_active=True
                )
                self.db.add(reminder)
        
        self.db.commit()
        self.db.refresh(med)
        
        logger.info(f"Updated medication: {med.name}")
        
        return self._to_info(med)
    
    def archive(self, medication_id: int) -> bool:
        """Archive (soft delete) a medication"""
        from backend.models import Medication
        
        med = self.db.query(Medication).filter(Medication.id == medication_id).first()
        
        if not med:
            return False
        
        med.is_active = False
        self.db.commit()
        
        logger.info(f"Archived medication: {med.name}")
        return True
    
    def restore(self, medication_id: int) -> bool:
        """Restore an archived medication"""
        from backend.models import Medication
        
        med = self.db.query(Medication).filter(Medication.id == medication_id).first()
        
        if not med:
            return False
        
        med.is_active = True
        self.db.commit()
        
        logger.info(f"Restored medication: {med.name}")
        return True
    
    def delete(self, medication_id: int, permanent: bool = False) -> bool:
        """
        Delete a medication
        
        Args:
            medication_id: Which medication
            permanent: If True, hard delete; if False, archive only
        """
        from backend.models import Medication, Reminder, MedicationLog
        
        med = self.db.query(Medication).filter(Medication.id == medication_id).first()
        
        if not med:
            return False
        
        if permanent:
            # Delete logs first (foreign key)
            self.db.query(MedicationLog).filter(
                MedicationLog.medication_id == medication_id
            ).delete()
            
            # Delete reminders
            self.db.query(Reminder).filter(
                Reminder.medication_id == medication_id
            ).delete()
            
            # Delete medication
            self.db.delete(med)
            
            logger.info(f"Permanently deleted medication: {med.name}")
        else:
            # Just archive
            med.is_active = False
            logger.info(f"Archived medication: {med.name}")
        
        self.db.commit()
        return True
    
    def update_schedule(self, medication_id: int, 
                        reminder_times: List[str]) -> Optional[MedicationInfo]:
        """Update just the schedule for a medication"""
        return self.update(medication_id, reminder_times=reminder_times)
    
    def get_count(self, active_only: bool = True) -> int:
        """Get count of medications"""
        from backend.models import Medication
        
        query = self.db.query(Medication)
        
        if active_only:
            query = query.filter(Medication.is_active == True)
        
        return query.count()
    
    def _to_info(self, med) -> MedicationInfo:
        """Convert DB model to MedicationInfo"""
        try:
            reminder_times = []
            if hasattr(med, 'reminders') and med.reminders:
                reminder_times = [
                    str(r.reminder_time)[:5] for r in med.reminders 
                    if hasattr(r, 'is_active') and r.is_active
                ]
            
            # Get last taken
            last_taken = None
            if hasattr(med, 'logs') and med.logs:
                taken_logs = [l for l in med.logs if hasattr(l, 'was_taken') and l.was_taken]
                if taken_logs:
                    last_taken = max(l.taken_at for l in taken_logs)
            
            # Get created_at if it exists, otherwise use start_date
            created_at = getattr(med, 'created_at', None)
            if not created_at and hasattr(med, 'start_date'):
                from datetime import datetime
                if med.start_date:
                    created_at = datetime.combine(med.start_date, datetime.min.time())
            if not created_at:
                from datetime import datetime
                created_at = datetime.now()
            
            return MedicationInfo(
                id=getattr(med, 'id', 0),
                name=getattr(med, 'name', 'Unknown'),
                dosage=getattr(med, 'dosage', '') or "",
                frequency=getattr(med, 'frequency', 'once_daily'),
                start_date=getattr(med, 'start_date', None),
                reminder_times=reminder_times,
                is_active=getattr(med, 'is_active', True),
                created_at=created_at,
                last_taken=last_taken
            )
        except Exception as e:
            logger.error(f"Error in _to_info: {e}")
            # Return minimal info on error
            return MedicationInfo(
                id=getattr(med, 'id', 0),
                name=getattr(med, 'name', 'Unknown'),
                dosage="",
                frequency="once_daily",
                start_date=None,
                reminder_times=[],
                is_active=True,
                created_at=datetime.now(),
                last_taken=None
            )
    
    def _parse_time(self, time_str: str) -> time:
        """Parse time string in various formats"""
        try:
            # Try HH:MM
            parts = time_str.split(':')
            return time(int(parts[0]), int(parts[1]))
        except (ValueError, IndexError):
            # Default to 9 AM
            return time(9, 0)
    
    def _get_default_times(self, frequency: str) -> List[time]:
        """Get default reminder times for frequency"""
        defaults = {
            'once_daily': [time(9, 0)],
            'twice_daily': [time(9, 0), time(21, 0)],
            'three_times_daily': [time(8, 0), time(14, 0), time(20, 0)],
            'every_morning': [time(8, 0)],
            'every_night': [time(22, 0)],
        }
        return defaults.get(frequency, [time(9, 0)])
