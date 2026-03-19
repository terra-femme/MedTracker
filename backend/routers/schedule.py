from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import User
from backend.agents.schedule_agent import ScheduleAgent
from backend.core.security import get_current_user

router = APIRouter(dependencies=[Depends(get_current_user)])


@router.get("/schedule/today")
def get_today_schedule(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        schedule_agent = ScheduleAgent(db, user_id=current_user.id)
        schedule = schedule_agent.get_today_schedule()
        return schedule_agent.format_schedule(schedule)
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/schedule/snooze/{medication_id}")
def snooze_medication(
    medication_id: int,
    minutes: int = 60,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    schedule_agent = ScheduleAgent(db, user_id=current_user.id)
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
def unsnooze_medication(
    medication_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    schedule_agent = ScheduleAgent(db, user_id=current_user.id)
    success = schedule_agent.unsnooze(medication_id)
    return {
        'success': success,
        'medication_id': medication_id,
        'message': 'Snooze removed' if success else 'Not snoozed',
    }
