from datetime import time
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import Medication as MedicationModel, Reminder as ReminderModel

router = APIRouter()


@router.get("/reminders", response_model=List[dict])
def get_reminders(medication_id: Optional[int] = None, db: Session = Depends(get_db)):
    """Get all reminders, optionally filtered by medication"""
    query = db.query(ReminderModel)
    if medication_id:
        query = query.filter(ReminderModel.medication_id == medication_id)
    reminders = query.all()
    return [
        {
            "id": r.id,
            "medication_id": r.medication_id,
            "reminder_time": str(r.reminder_time),
            "is_sent": r.is_sent,
        }
        for r in reminders
    ]


@router.post("/reminders", response_model=dict, status_code=status.HTTP_201_CREATED)
def create_reminder(reminder_data: dict, db: Session = Depends(get_db)):
    """Create a reminder for a medication"""
    medication_id = reminder_data.get("medication_id")
    reminder_time_str = reminder_data.get("reminder_time")

    if not medication_id or not reminder_time_str:
        raise HTTPException(status_code=400, detail="medication_id and reminder_time required")

    if not db.query(MedicationModel).filter(MedicationModel.id == medication_id).first():
        raise HTTPException(status_code=404, detail="Medication not found")

    try:
        parts = reminder_time_str.split(":")
        reminder_time = time(int(parts[0]), int(parts[1]), int(parts[2]) if len(parts) > 2 else 0)
    except (ValueError, IndexError):
        raise HTTPException(status_code=400, detail="Invalid time format. Use HH:MM or HH:MM:SS")

    db_reminder = ReminderModel(medication_id=medication_id, reminder_time=reminder_time, is_sent=False)
    db.add(db_reminder)
    db.commit()
    db.refresh(db_reminder)

    return {
        "success": True,
        "message": "Reminder created",
        "reminder": {
            "id": db_reminder.id,
            "medication_id": db_reminder.medication_id,
            "reminder_time": str(db_reminder.reminder_time),
        },
    }


@router.delete("/reminders/{reminder_id}")
def delete_reminder(reminder_id: int, db: Session = Depends(get_db)):
    """Delete a reminder"""
    db_reminder = db.query(ReminderModel).filter(ReminderModel.id == reminder_id).first()
    if not db_reminder:
        raise HTTPException(status_code=404, detail="Reminder not found")
    db.delete(db_reminder)
    db.commit()
    return {"success": True, "message": "Reminder deleted", "id": reminder_id}
