"""
DoseAgent - Manages dose logging and tracking

Responsibilities:
- Log taken doses
- Log missed doses  
- Undo/cancel dose logs
- Query dose history

Does NOT:
- Calculate adherence (AdherenceAgent)
- Manage medications (MedicationAgent)
"""

from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime, date, time
import logging

logger = logging.getLogger(__name__)


@dataclass
class DoseLog:
    log_id: int
    medication_id: int
    medication_name: str
    taken_at: datetime
    was_taken: bool
    notes: Optional[str] = None
    already_logged: bool = False


class DoseAgent:
    """
    Agent for managing dose logs
    
    Usage:
        agent = DoseAgent(db_session)
        log = agent.log_dose(med_id=1, taken=True)
        agent.undo_log(log_id=5)
    """
    
    def __init__(self, db_session):
        self.db = db_session
    
    def log_dose(self, medication_id: int, taken: bool = True, 
                 taken_at: Optional[datetime] = None,
                 notes: Optional[str] = None) -> DoseLog:
        """
        Log a dose as taken or missed
        
        Args:
            medication_id: Which medication
            taken: True if taken, False if missed
            taken_at: When (default: now)
            notes: Optional notes
            
        Returns:
            DoseLog object
        """
        from backend.models import MedicationLog, Medication

        if taken_at is None:
            taken_at = datetime.now()

        # Guard: prevent duplicate logs when the expected doses for today are already recorded
        if taken:
            med = self.db.query(Medication).filter(Medication.id == medication_id).first()
            if med:
                expected_today = len([r for r in med.reminders if r.is_active]) or 1
                already_taken = self.get_dose_count_today(medication_id)
                if already_taken >= expected_today:
                    # Return the most recent log instead of creating a duplicate
                    existing = self.db.query(MedicationLog).filter(
                        MedicationLog.medication_id == medication_id,
                        MedicationLog.was_taken == True,
                        MedicationLog.taken_at >= datetime.combine(date.today(), time.min)
                    ).order_by(MedicationLog.taken_at.desc()).first()
                    if existing:
                        logger.info(f"Duplicate log prevented for medication {medication_id}")
                        return DoseLog(
                            log_id=existing.id,
                            medication_id=medication_id,
                            medication_name=med.name,
                            taken_at=existing.taken_at,
                            was_taken=True,
                            notes=existing.notes,
                            already_logged=True,
                        )

        # Create log entry
        log = MedicationLog(
            medication_id=medication_id,
            taken_at=taken_at,
            was_taken=taken,
            notes=notes
        )
        
        self.db.add(log)
        self.db.commit()
        self.db.refresh(log)
        
        # Get medication name
        med = self.db.query(Medication).filter(Medication.id == medication_id).first()
        med_name = med.name if med else "Unknown"
        
        logger.info(f"Logged dose: {med_name} - {'taken' if taken else 'missed'}")
        
        return DoseLog(
            log_id=log.id,
            medication_id=medication_id,
            medication_name=med_name,
            taken_at=taken_at,
            was_taken=taken,
            notes=notes
        )
    
    def mark_taken(self, medication_id: int) -> DoseLog:
        """Quick method to mark a dose as taken"""
        return self.log_dose(medication_id, taken=True)
    
    def mark_missed(self, medication_id: int) -> DoseLog:
        """Quick method to mark a dose as missed"""
        return self.log_dose(medication_id, taken=False)
    
    def undo_log(self, log_id: int) -> bool:
        """
        Undo/remove a log entry
        
        Returns:
            True if successful, False if not found
        """
        from backend.models import MedicationLog
        
        log = self.db.query(MedicationLog).filter(MedicationLog.id == log_id).first()
        
        if not log:
            return False
        
        self.db.delete(log)
        self.db.commit()
        
        logger.info(f"Undo log: {log_id}")
        return True
    
    def undo_last_dose(self, medication_id: int) -> bool:
        """Undo the most recent dose for a medication"""
        from backend.models import MedicationLog
        
        log = self.db.query(MedicationLog).filter(
            MedicationLog.medication_id == medication_id
        ).order_by(MedicationLog.taken_at.desc()).first()
        
        if log:
            return self.undo_log(log.id)
        
        return False
    
    def get_today_logs(self) -> List[DoseLog]:
        """Get all dose logs for today"""
        from backend.models import MedicationLog, Medication
        
        today_start = datetime.combine(date.today(), time.min)
        today_end = datetime.combine(date.today(), time.max)
        
        db_logs = self.db.query(MedicationLog).filter(
            MedicationLog.taken_at >= today_start,
            MedicationLog.taken_at <= today_end
        ).order_by(MedicationLog.taken_at.desc()).all()
        
        result = []
        for log in db_logs:
            med = self.db.query(Medication).filter(Medication.id == log.medication_id).first()
            result.append(DoseLog(
                log_id=log.id,
                medication_id=log.medication_id,
                medication_name=med.name if med else "Unknown",
                taken_at=log.taken_at,
                was_taken=log.was_taken,
                notes=log.notes
            ))
        
        return result
    
    def is_dose_logged_today(self, medication_id: int) -> bool:
        """Check if a dose has been logged today for a medication"""
        from backend.models import MedicationLog
        
        today_start = datetime.combine(date.today(), time.min)
        
        log = self.db.query(MedicationLog).filter(
            MedicationLog.medication_id == medication_id,
            MedicationLog.taken_at >= today_start,
            MedicationLog.was_taken == True
        ).first()
        
        return log is not None
    
    def get_dose_count_today(self, medication_id: int) -> int:
        """Get number of doses taken today for a medication"""
        from backend.models import MedicationLog
        
        today_start = datetime.combine(date.today(), time.min)
        
        count = self.db.query(MedicationLog).filter(
            MedicationLog.medication_id == medication_id,
            MedicationLog.taken_at >= today_start,
            MedicationLog.was_taken == True
        ).count()
        
        return count
    
    def get_logs_for_date(self, check_date: date) -> List[DoseLog]:
        """Get all logs for a specific date"""
        from backend.models import MedicationLog, Medication
        
        date_start = datetime.combine(check_date, time.min)
        date_end = datetime.combine(check_date, time.max)
        
        db_logs = self.db.query(MedicationLog).filter(
            MedicationLog.taken_at >= date_start,
            MedicationLog.taken_at <= date_end
        ).order_by(MedicationLog.taken_at.desc()).all()
        
        result = []
        for log in db_logs:
            med = self.db.query(Medication).filter(Medication.id == log.medication_id).first()
            result.append(DoseLog(
                log_id=log.id,
                medication_id=log.medication_id,
                medication_name=med.name if med else "Unknown",
                taken_at=log.taken_at,
                was_taken=log.was_taken,
                notes=log.notes
            ))
        
        return result
