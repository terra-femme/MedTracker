"""
ScheduleAgent - Time-based medication schedule management

Responsibilities:
- Organize medications into NOW/LATER/MISSED/TAKEN buckets
- Handle snooze functionality
- Determine next dose times

Does NOT:
- Log doses (DoseAgent)
- Calculate adherence (AdherenceAgent)
"""

from enum import Enum
from typing import List, Dict, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta, date, time
import logging

logger = logging.getLogger(__name__)


def _fmt_time(t: time) -> str:
    """Format a time object as '9:00 am' / '12:30 pm'.

    Pure-Python replacement for strftime('%#I:%M %p') [Windows] /
    strftime('%-I:%M %p') [Linux]. Both flags are platform-specific;
    this version works identically on Windows, Linux, and macOS.
    """
    hour = t.hour % 12 or 12  # 0 -> 12 (midnight), 13 -> 1, etc.
    ampm = "am" if t.hour < 12 else "pm"
    return f"{hour}:{t.minute:02d} {ampm}"


class TimeBucket(Enum):
    NOW = "now"  # Within 30 min window (or snoozed until now)
    LATER = "later"  # Future today
    MISSED = "missed"  # Past with no log
    TAKEN = "taken"  # Already logged today
    SNOOZED = "snoozed"  # Explicitly snoozed


@dataclass
class ScheduledDose:
    medication_id: int
    name: str
    dosage: str
    scheduled_time: time  # Time of day
    display_time: str  # Formatted time (e.g., "8:00 AM")
    bucket: TimeBucket
    snooze_until: Optional[datetime] = None
    is_taken: bool = False
    taken_at: Optional[datetime] = None
    can_snooze: bool = True


@dataclass  
class DailySchedule:
    date: date
    now_window_start: time
    now_window_end: time
    now: List[ScheduledDose] = field(default_factory=list)
    later: List[ScheduledDose] = field(default_factory=list)
    missed: List[ScheduledDose] = field(default_factory=list)
    taken: List[ScheduledDose] = field(default_factory=list)
    snoozed: List[ScheduledDose] = field(default_factory=list)
    
    @property
    def all_doses(self) -> List[ScheduledDose]:
        return self.now + self.later + self.missed + self.taken + self.snoozed
    
    @property
    def pending_count(self) -> int:
        """Count of doses still pending (now + later + missed)"""
        return len(self.now) + len(self.later) + len(self.missed)
    
    @property
    def is_complete(self) -> bool:
        """True if all doses for today are taken"""
        return self.pending_count == 0 and len(self.all_doses) > 0


class ScheduleAgent:
    """
    Agent for managing time-based medication schedules
    
    Usage:
        agent = ScheduleAgent(db_session)
        schedule = agent.get_today_schedule()
        
        # Get NOW medications
        for dose in schedule.now:
            show_notification(dose)
        
        # Snooze a medication
        agent.snooze(med_id, minutes=60)
    """
    
    # Configurable time windows
    NOW_WINDOW_MINUTES = 30  # +/- 30 min from scheduled time = NOW
    MISSED_THRESHOLD_MINUTES = 30  # 30 min past = MISSED
    DEFAULT_SNOOZE_MINUTES = 60
    
    def __init__(self, db_session, user_id: Optional[int] = None):
        self.db = db_session
        self.user_id = user_id
        self._snooze_cache: Dict[int, datetime] = {}  # med_id -> snooze_until
    
    def get_today_schedule(self, user_id: Optional[int] = None) -> DailySchedule:
        """
        Get today's complete schedule organized into buckets
        
        Returns:
            DailySchedule with NOW, LATER, MISSED, TAKEN, SNOOZED lists
        """
        try:
            from backend.models import Medication, Reminder, MedicationLog
        except ImportError as e:
            logger.error(f"Failed to import models: {e}")
            # Return empty schedule
            return DailySchedule(
                date=date.today(),
                now_window_start=time(0, 0),
                now_window_end=time(23, 59)
            )
        
        today = date.today()
        now = datetime.now()
        current_time = now.time()
        
        # Create schedule object
        now_window = self._calculate_now_window(current_time)
        schedule = DailySchedule(
            date=today,
            now_window_start=now_window['start'],
            now_window_end=now_window['end']
        )
        
        # Get active medications — scoped to user if user_id is set
        med_query = self.db.query(Medication).filter(
            Medication.is_active == True,
            Medication.start_date <= today
        )
        if self.user_id is not None:
            med_query = med_query.filter(Medication.user_id == self.user_id)
        meds = med_query.all()
        
        # Get today's logs
        today_start = datetime.combine(today, time.min)
        today_end = datetime.combine(today, time.max)
        
        today_logs = self.db.query(MedicationLog).filter(
            MedicationLog.taken_at >= today_start,
            MedicationLog.taken_at <= today_end,
            MedicationLog.was_taken == True
        ).all()
        
        # Build per-medication list of today's taken logs, sorted by taken_at.
        # Using a list (not a single entry) so multi-dose medications can match
        # each reminder slot independently — prevents one logged dose from marking
        # all reminder times (e.g. 9 AM and 9 PM) as TAKEN simultaneously.
        from collections import defaultdict
        taken_logs_by_med: dict = defaultdict(list)
        for log in sorted(today_logs, key=lambda l: l.taken_at):
            taken_logs_by_med[log.medication_id].append(log)

        logger.info(f"Schedule: {len(meds)} active meds, {len(today_logs)} taken logs, taken_ids={list(taken_logs_by_med.keys())}")

        # Process each medication
        for med in meds:
            try:
                # Get reminder times
                reminders = self.db.query(Reminder).filter(
                    Reminder.medication_id == med.id
                ).all()

                if not reminders:
                    # Use frequency-based default times
                    reminder_times = self._get_default_times(med.frequency)
                else:
                    reminder_times = [r.reminder_time for r in reminders]

                # Sort reminder times so the earliest slot consumes the earliest log
                reminder_times = sorted(reminder_times)
                taken_logs = taken_logs_by_med.get(med.id, [])

                # Create a ScheduledDose for each reminder time
                for i, reminder_time in enumerate(reminder_times):
                    # Each slot only claims one log entry — slot 0 → log[0], slot 1 → log[1], etc.
                    taken_log = taken_logs[i] if i < len(taken_logs) else None
                    dose = self._create_scheduled_dose(
                        med=med,
                        reminder_time=reminder_time,
                        current_time=current_time,
                        taken_log=taken_log,
                        now=now
                    )
                    
                    # Add to appropriate bucket
                    if dose.bucket == TimeBucket.NOW:
                        schedule.now.append(dose)
                    elif dose.bucket == TimeBucket.LATER:
                        schedule.later.append(dose)
                    elif dose.bucket == TimeBucket.MISSED:
                        schedule.missed.append(dose)
                    elif dose.bucket == TimeBucket.TAKEN:
                        schedule.taken.append(dose)
                    elif dose.bucket == TimeBucket.SNOOZED:
                        schedule.snoozed.append(dose)
            except Exception as e:
                logger.error(f"Error processing medication {med.id}: {e}")
                continue
        
        # Sort each bucket by time
        schedule.now.sort(key=lambda d: d.scheduled_time)
        schedule.later.sort(key=lambda d: d.scheduled_time)
        schedule.missed.sort(key=lambda d: d.scheduled_time)
        schedule.taken.sort(key=lambda d: d.scheduled_time)
        schedule.snoozed.sort(key=lambda d: d.snooze_until or datetime.min)
        
        logger.info(f"Schedule buckets: NOW={len(schedule.now)}, LATER={len(schedule.later)}, MISSED={len(schedule.missed)}, TAKEN={len(schedule.taken)}")
        
        return schedule
    
    def _create_scheduled_dose(self, med, reminder_time: time, 
                                current_time: time, taken_log, now: datetime) -> ScheduledDose:
        """Create a ScheduledDose with correct bucket assignment"""
        
        display_time = _fmt_time(reminder_time)
        
        # Check if already taken
        if taken_log:
            return ScheduledDose(
                medication_id=med.id,
                name=med.name,
                dosage=med.dosage or "",
                scheduled_time=reminder_time,
                display_time=display_time,
                bucket=TimeBucket.TAKEN,
                is_taken=True,
                taken_at=taken_log.taken_at,
                can_snooze=False
            )
        
        # Check if snoozed
        snooze_until = self._snooze_cache.get(med.id)
        if snooze_until and now < snooze_until:
            return ScheduledDose(
                medication_id=med.id,
                name=med.name,
                dosage=med.dosage or "",
                scheduled_time=reminder_time,
                display_time=display_time,
                bucket=TimeBucket.SNOOZED,
                snooze_until=snooze_until,
                can_snooze=False
            )
        elif snooze_until and now >= snooze_until:
            # Snooze expired - clear it
            del self._snooze_cache[med.id]
        
        # Determine time-based bucket
        bucket = self._determine_time_bucket(reminder_time, current_time)
        
        # Can snooze NOW medications
        can_snooze = (bucket == TimeBucket.NOW)
        
        return ScheduledDose(
            medication_id=med.id,
            name=med.name,
            dosage=med.dosage or "",
            scheduled_time=reminder_time,
            display_time=display_time,
            bucket=bucket,
            can_snooze=can_snooze
        )
    
    def _determine_time_bucket(self, scheduled_time: time, current_time: time) -> TimeBucket:
        """
        Determine which bucket a dose belongs in based on times
        
        NOW: Within +/- NOW_WINDOW_MINUTES of current time
        LATER: Scheduled time is in the future
        MISSED: Scheduled time is in the past by > MISSED_THRESHOLD_MINUTES
        """
        # Convert times to minutes for easier comparison
        scheduled_minutes = scheduled_time.hour * 60 + scheduled_time.minute
        current_minutes = current_time.hour * 60 + current_time.minute
        
        diff_minutes = scheduled_minutes - current_minutes
        
        if abs(diff_minutes) <= self.NOW_WINDOW_MINUTES:
            # Within window of now
            return TimeBucket.NOW
        elif diff_minutes > 0:
            # In the future
            return TimeBucket.LATER
        else:
            # In the past - check if missed
            if abs(diff_minutes) > self.MISSED_THRESHOLD_MINUTES:
                return TimeBucket.MISSED
            else:
                # Just passed but within grace period - still NOW
                return TimeBucket.NOW
    
    def _calculate_now_window(self, current_time: time) -> Dict:
        """Calculate the time window for "NOW" bucket"""
        current_minutes = current_time.hour * 60 + current_time.minute
        
        start_minutes = max(0, current_minutes - self.NOW_WINDOW_MINUTES)
        end_minutes = min(24 * 60 - 1, current_minutes + self.NOW_WINDOW_MINUTES)
        
        return {
            'start': time(start_minutes // 60, start_minutes % 60),
            'end': time(end_minutes // 60, end_minutes % 60)
        }
    
    def snooze(self, medication_id: int, minutes: int = None) -> Optional[datetime]:
        """
        Snooze a medication to be reminded later
        
        Args:
            medication_id: Which medication to snooze
            minutes: How long to snooze (default: 60)
            
        Returns:
            Snooze until datetime, or None if already taken
        """
        if minutes is None:
            minutes = self.DEFAULT_SNOOZE_MINUTES
        
        # Check if already taken today
        from backend.models import MedicationLog
        
        today_start = datetime.combine(date.today(), time.min)
        taken = self.db.query(MedicationLog).filter(
            MedicationLog.medication_id == medication_id,
            MedicationLog.taken_at >= today_start,
            MedicationLog.was_taken == True
        ).first()
        
        if taken:
            return None
        
        snooze_until = datetime.now() + timedelta(minutes=minutes)
        self._snooze_cache[medication_id] = snooze_until
        
        logger.info(f"Snoozed medication {medication_id} until {snooze_until}")
        
        return snooze_until
    
    def unsnooze(self, medication_id: int) -> bool:
        """Remove snooze from a medication"""
        if medication_id in self._snooze_cache:
            del self._snooze_cache[medication_id]
            return True
        return False
    
    def get_snooze_status(self, medication_id: int) -> Optional[Dict]:
        """Get snooze status for a medication"""
        snooze_until = self._snooze_cache.get(medication_id)
        
        if not snooze_until:
            return None
        
        now = datetime.now()
        remaining = snooze_until - now
        
        if remaining.total_seconds() <= 0:
            del self._snooze_cache[medication_id]
            return None
        
        return {
            "medication_id": medication_id,
            "snooze_until": snooze_until.isoformat(),
            "remaining_minutes": int(remaining.total_seconds() / 60)
        }
    
    def get_next_dose(self, medication_id: int) -> Optional[ScheduledDose]:
        """Get the next scheduled dose for a specific medication"""
        schedule = self.get_today_schedule()
        
        for dose in schedule.all_doses:
            if dose.medication_id == medication_id and dose.bucket != TimeBucket.TAKEN:
                return dose
        
        return None
    
    def _get_default_times(self, frequency: str) -> List[time]:
        """Get default reminder times based on frequency"""
        defaults = {
            'once_daily': [time(9, 0)],  # 9 AM
            'twice_daily': [time(9, 0), time(21, 0)],  # 9 AM, 9 PM
            'three_times_daily': [time(8, 0), time(14, 0), time(20, 0)],
            'every_morning': [time(8, 0)],
            'every_night': [time(22, 0)],
        }
        return defaults.get(frequency, [time(9, 0)])
    
    def format_schedule(self, schedule: DailySchedule) -> Dict:
        """Format schedule for JSON response"""
        def format_dose(dose: ScheduledDose) -> Dict:
            result = {
                "medication_id": dose.medication_id,
                "name": dose.name,
                "dosage": dose.dosage,
                "scheduled_time": dose.display_time,
                "can_snooze": dose.can_snooze
            }
            if dose.snooze_until:
                result["snooze_until"] = dose.snooze_until.isoformat()
            if dose.is_taken and dose.taken_at:
                result["taken_at"] = dose.taken_at.isoformat()
            return result
        
        return {
            "date": schedule.date.isoformat(),
            "now_window": {
                "start": _fmt_time(schedule.now_window_start),
                "end": _fmt_time(schedule.now_window_end),
            },
            "now": [format_dose(d) for d in schedule.now],
            "later": [format_dose(d) for d in schedule.later],
            "missed": [format_dose(d) for d in schedule.missed],
            "taken": [format_dose(d) for d in schedule.taken],
            "snoozed": [format_dose(d) for d in schedule.snoozed],
            "pending_count": schedule.pending_count,
            "is_complete": schedule.is_complete
        }
