from datetime import date, datetime, time

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import Medication as MedicationModel, MedicationLog as LogModel, User
from backend.agents.adherence_agent import AdherenceAgent
from backend.agents.schedule_agent import ScheduleAgent
from backend.agents.streak_agent import StreakAgent
from backend.core.security import get_current_user

router = APIRouter(dependencies=[Depends(get_current_user)])


@router.get("/stats/adherence")
def get_adherence_stats(
    period: str = "weekly",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        adherence_agent = AdherenceAgent(db, user_id=current_user.id)
        report = adherence_agent.calculate_adherence(days=7)
        today = adherence_agent.get_today_summary()
        return {
            'today_taken': today['taken'],
            'today_expected': today['expected'],
            'today_remaining': max(0, today['expected'] - today['taken']),
            'adherence_rate': report.overall_rate,
            'current_streak': report.daily_breakdown[-1].get('rate', 0) if report.daily_breakdown else 0,
            'weekly_breakdown': report.daily_breakdown,
            'by_medication': report.by_medication,
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats/streak")
def get_streak_info(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    adherence_agent = AdherenceAgent(db, user_id=current_user.id)
    streak_agent = StreakAgent(adherence_agent)
    streak_info = streak_agent.get_streak_info()
    return {
        'streak': streak_agent.format_streak_info(streak_info),
        'status': streak_agent.check_streak_status(),
    }


@router.get("/stats/today")
def get_today_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    schedule_agent = ScheduleAgent(db, user_id=current_user.id)
    schedule = schedule_agent.get_today_schedule()
    adherence_agent = AdherenceAgent(db, user_id=current_user.id)
    today = adherence_agent.get_today_summary()
    return {
        'date': today['date'],
        'pending': schedule.now + schedule.later + schedule.missed,
        'taken': schedule.taken,
        'total': len(schedule.all_doses),
        'completed': len(schedule.taken),
        'pending_count': schedule.pending_count,
        'is_complete': schedule.is_complete,
        'adherence': today,
    }


@router.get("/stats/summary")
def get_stats_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    active_count = db.query(MedicationModel).filter(
        MedicationModel.user_id == current_user.id,
        MedicationModel.is_active == True,
    ).count()
    today = date.today()
    today_logs = db.query(LogModel).join(MedicationModel).filter(
        MedicationModel.user_id == current_user.id,
        LogModel.taken_at >= datetime.combine(today, time.min),
        LogModel.taken_at <= datetime.combine(today, time.max),
        LogModel.was_taken == True,
    ).count()
    total_count = db.query(MedicationModel).filter(
        MedicationModel.user_id == current_user.id,
    ).count()
    return {
        "active_medications": active_count,
        "taken_today": today_logs,
        "total_medications": total_count,
        "inactive_medications": total_count - active_count,
    }
