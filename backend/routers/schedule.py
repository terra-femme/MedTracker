from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.agents.schedule_agent import ScheduleAgent

router = APIRouter()


@router.get("/schedule/today")
def get_today_schedule(db: Session = Depends(get_db)):
    """
    Get today's medication schedule organized into time buckets:
    now, later, missed, taken, snoozed
    """
    try:
        schedule_agent = ScheduleAgent(db)
        schedule = schedule_agent.get_today_schedule()
        return schedule_agent.format_schedule(schedule)
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/schedule/snooze/{medication_id}")
def snooze_medication(medication_id: int, minutes: int = 60, db: Session = Depends(get_db)):
    """Snooze a medication for later (default 60 minutes)"""
    schedule_agent = ScheduleAgent(db)
    snooze_until = schedule_agent.snooze(medication_id, minutes)
    if snooze_until is None:
        raise HTTPException(status_code=400, detail="Medication already taken today")
    return {
        'success': True,
        'medication_id': medication_id,
        'snooze_until': snooze_until.isoformat(),
        'message': f'Snoozed for {minutes} minutes',
    }


@router.post("/schedule/unsnooze/{medication_id}")
def unsnooze_medication(medication_id: int, db: Session = Depends(get_db)):
    """Remove snooze from a medication"""
    schedule_agent = ScheduleAgent(db)
    success = schedule_agent.unsnooze(medication_id)
    return {
        'success': success,
        'medication_id': medication_id,
        'message': 'Snooze removed' if success else 'Not snoozed',
    }
