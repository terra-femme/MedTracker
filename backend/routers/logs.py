from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import MedicationLog as LogModel
from backend.agents.dose_agent import DoseAgent
from backend.agents.schedule_agent import ScheduleAgent

router = APIRouter()


@router.get("/logs", response_model=List[dict])
def get_logs(
    medication_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    """Get medication logs"""
    query = db.query(LogModel)
    if medication_id:
        query = query.filter(LogModel.medication_id == medication_id)
    logs = query.order_by(LogModel.taken_at.desc()).offset(skip).limit(limit).all()
    return [
        {
            "id": log.id,
            "medication_id": log.medication_id,
            "taken_at": log.taken_at.isoformat(),
            "was_taken": log.was_taken,
            "notes": log.notes,
        }
        for log in logs
    ]


@router.post("/logs", response_model=dict, status_code=status.HTTP_201_CREATED)
def create_log(log_data: dict, db: Session = Depends(get_db)):
    """Create a medication log entry using DoseAgent"""
    medication_id = log_data.get("medication_id")
    was_taken = log_data.get("status") != "missed"
    notes = log_data.get("notes", "")

    if not medication_id:
        raise HTTPException(status_code=400, detail="medication_id is required")

    dose_agent = DoseAgent(db)
    dose_log = dose_agent.log_dose(medication_id=medication_id, taken=was_taken, notes=notes)

    ScheduleAgent(db).unsnooze(medication_id)

    return {
        "success": True,
        "already_logged": dose_log.already_logged,
        "message": (
            "You've already logged this medication today."
            if dose_log.already_logged
            else f"Dose {'taken' if was_taken else 'missed'} logged successfully"
        ),
        "log": {
            "id": dose_log.log_id,
            "medication_id": dose_log.medication_id,
            "taken_at": dose_log.taken_at.isoformat(),
            "was_taken": dose_log.was_taken,
        },
    }


@router.post("/logs/quick", response_model=dict, status_code=status.HTTP_201_CREATED)
def quick_log_dose(log_data: dict, db: Session = Depends(get_db)):
    """
    Quickly log that a dose was taken.
    Send: {"medication_id": 1, "was_taken": true, "timestamp": "2025-10-21T10:30:00" (optional)}
    """
    medication_id = log_data.get("medication_id")
    was_taken = log_data.get("was_taken", True)
    timestamp_str = log_data.get("timestamp")
    notes = log_data.get("notes")

    if not medication_id:
        raise HTTPException(status_code=400, detail="medication_id is required")

    taken_at = (
        datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        if timestamp_str
        else datetime.now()
    )

    dose_agent = DoseAgent(db)
    dose_log = dose_agent.log_dose(
        medication_id=medication_id,
        taken=was_taken,
        taken_at=taken_at,
        notes=notes,
    )

    if was_taken:
        ScheduleAgent(db).unsnooze(medication_id)

    return {
        "success": True,
        "already_logged": dose_log.already_logged,
        "message": (
            "You've already logged this medication today."
            if dose_log.already_logged
            else f"Dose {'taken' if was_taken else 'missed'} logged successfully"
        ),
        "log": {
            "id": dose_log.log_id,
            "medication_id": dose_log.medication_id,
            "taken_at": dose_log.taken_at.isoformat(),
            "was_taken": dose_log.was_taken,
        },
    }


@router.post("/logs/undo/{medication_id}", response_model=dict)
def undo_dose(medication_id: int, db: Session = Depends(get_db)):
    """Undo the most recent dose for a medication"""
    try:
        dose_agent = DoseAgent(db)
        if dose_agent.undo_last_dose(medication_id):
            return {
                "success": True,
                "message": "Last dose entry removed - medication is now pending again",
                "medication_id": medication_id,
            }
        raise HTTPException(status_code=404, detail="No log entry found to undo for this medication")
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
