"""
Medication Tracker - Complete FastAPI Backend
This connects your database, models, and NLP parser together
"""

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, date, time
import os

# Import database setup from backend folder
from backend.database import engine, get_db, Base

# Import models (database tables) from backend folder
from backend.models import Medication as MedicationModel
from backend.models import MedicationLog as LogModel
from backend.models import Reminder as ReminderModel

# Import schemas (data validation) from backend folder
from backend import schemas

# Import NLP parser from backend folder
from backend.med_nlp_parser import MedicationNLPParser

# Create all database tables
Base.metadata.create_all(bind=engine)

# Initialize the app
app = FastAPI(
    title="MedTracker - Medication Reminder",
    description="Smart medication tracking with natural language processing",
    version="1.0.0"
)

# Initialize NLP parser
nlp_parser = MedicationNLPParser()

# Setup CORS (allows your HTML to talk to the API)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, change to your specific domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files (your HTML, CSS, JS) from frontend folder
if os.path.exists("frontend"):
    app.mount("/static", StaticFiles(directory="frontend"), name="static")

# ============================================================================
# ROOT & INFO ENDPOINTS
# ============================================================================

@app.get("/")
async def serve_homepage():
    """Serve the main HTML page from frontend folder"""
    if os.path.exists("frontend/index.html"):
        return FileResponse("frontend/index.html")
    return {"message": "MedTracker API is running! Add index.html to frontend/ folder"}

@app.get("/api/health")
def health_check():
    """Check if API is running"""
    return {
        "status": "healthy",
        "message": "MedTracker API is running",
        "features": ["NLP input", "Medication tracking", "Dose logging", "Reminders"]
    }

# ============================================================================
# MEDICATION ENDPOINTS (Standard CRUD)
# ============================================================================

@app.get("/medications", response_model=List[schemas.Medication])
def get_medications(
    active_only: bool = False,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    Get all medications
    - active_only: if True, only return active medications
    - skip: pagination offset
    - limit: max number to return
    """
    query = db.query(MedicationModel)
    
    if active_only:
        query = query.filter(MedicationModel.is_active == True)
    
    medications = query.offset(skip).limit(limit).all()
    return medications

@app.get("/medications/{medication_id}", response_model=schemas.Medication)
def get_medication(medication_id: int, db: Session = Depends(get_db)):
    """Get a specific medication by ID"""
    medication = db.query(MedicationModel).filter(MedicationModel.id == medication_id).first()
    
    if not medication:
        raise HTTPException(status_code=404, detail="Medication not found")
    
    return medication

@app.post("/medications", response_model=schemas.Medication, status_code=status.HTTP_201_CREATED)
def create_medication(medication: schemas.MedicationCreate, db: Session = Depends(get_db)):
    """
    Create a new medication (traditional structured way)
    Requires: name, dosage, frequency, start_date
    """
    # Create new medication object
    db_medication = MedicationModel(
        name=medication.name,
        dosage=medication.dosage,
        frequency=medication.frequency,
        start_date=medication.start_date,
        end_date=medication.end_date,
        is_active=medication.is_active,
        notes=medication.notes
    )
    
    db.add(db_medication)
    db.commit()
    db.refresh(db_medication)
    
    return db_medication

@app.put("/medications/{medication_id}", response_model=schemas.Medication)
def update_medication(
    medication_id: int,
    medication: schemas.MedicationUpdate,
    db: Session = Depends(get_db)
):
    """Update an existing medication"""
    db_medication = db.query(MedicationModel).filter(MedicationModel.id == medication_id).first()
    
    if not db_medication:
        raise HTTPException(status_code=404, detail="Medication not found")
    
    # Update only fields that were provided
    update_data = medication.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_medication, field, value)
    
    db.commit()
    db.refresh(db_medication)
    
    return db_medication

@app.delete("/medications/{medication_id}")
def delete_medication(medication_id: int, db: Session = Depends(get_db)):
    """Delete a medication (actually just marks it as inactive)"""
    db_medication = db.query(MedicationModel).filter(MedicationModel.id == medication_id).first()
    
    if not db_medication:
        raise HTTPException(status_code=404, detail="Medication not found")
    
    # Mark as inactive instead of deleting
    db_medication.is_active = False
    db.commit()
    
    return {"message": "Medication marked as inactive", "id": medication_id}

# ============================================================================
# NLP ENDPOINTS (Natural Language Processing) 🎯
# ============================================================================

@app.post("/medications/natural", response_model=dict, status_code=status.HTTP_201_CREATED)
def create_medication_from_natural_language(
    input_text: dict,
    db: Session = Depends(get_db)
):
    """
    🌟 CREATE MEDICATION USING NATURAL LANGUAGE! 🌟
    
    Examples:
    - "Add aspirin 500mg twice daily"
    - "Take vitamin D 1000 IU every morning"
    - "Use inhaler 2 puffs as needed"
    
    Send: {"text": "Add aspirin 500mg twice daily"}
    """
    text = input_text.get("text", "")
    
    if not text:
        raise HTTPException(status_code=400, detail="No text provided")
    
    # Use NLP to parse the text
    parsed = nlp_parser.parse_medication_input(text)
    
    # Check if we got a valid medication name
    if not parsed['name']:
        raise HTTPException(
            status_code=400,
            detail="Could not understand medication name. Try: 'Add [medication name] [dosage] [frequency]'"
        )
    
    # Create medication in database
    db_medication = MedicationModel(
        name=parsed['name'],
        dosage=parsed['dosage'] or 'as directed',
        frequency=parsed['frequency'] or 'as directed',
        start_date=date.today(),
        is_active=True,
        notes=parsed['notes']
    )
    
    db.add(db_medication)
    db.commit()
    db.refresh(db_medication)
    
    return {
        "success": True,
        "message": "Medication added successfully!",
        "medication": {
            "id": db_medication.id,
            "name": db_medication.name,
            "dosage": db_medication.dosage,
            "frequency": db_medication.frequency,
            "notes": db_medication.notes
        },
        "parsed_from": text,
        "understood_as": parsed
    }

@app.post("/medications/parse", response_model=dict)
def parse_natural_language_test(input_text: dict):
    """
    🧪 TEST ENDPOINT: See what the NLP understands
    
    Use this to test what the parser understands BEFORE creating a medication
    Send: {"text": "Add aspirin 500mg twice daily"}
    """
    text = input_text.get("text", "")
    
    if not text:
        raise HTTPException(status_code=400, detail="No text provided")
    
    parsed = nlp_parser.parse_medication_input(text)
    
    return {
        "original_text": text,
        "understood_as": parsed,
        "tip": "If this looks correct, use /medications/natural to actually create it!"
    }

# ============================================================================
# MEDICATION LOG ENDPOINTS (Tracking when doses are taken)
# ============================================================================

@app.get("/logs", response_model=List[dict])
def get_logs(
    medication_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    Get medication logs
    - medication_id: filter by specific medication (optional)
    """
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
            "notes": log.notes
        }
        for log in logs
    ]

@app.post("/logs/quick", response_model=dict, status_code=status.HTTP_201_CREATED)
def quick_log_dose(log_data: dict, db: Session = Depends(get_db)):
    """
    Quickly log that a dose was taken
    
    Send: {
        "medication_id": 1,
        "was_taken": true,
        "timestamp": "2025-10-21T10:30:00" (optional, defaults to now)
    }
    """
    medication_id = log_data.get("medication_id")
    was_taken = log_data.get("was_taken", True)
    timestamp_str = log_data.get("timestamp")
    notes = log_data.get("notes")
    
    if not medication_id:
        raise HTTPException(status_code=400, detail="medication_id is required")
    
    # Verify medication exists
    medication = db.query(MedicationModel).filter(MedicationModel.id == medication_id).first()
    if not medication:
        raise HTTPException(status_code=404, detail="Medication not found")
    
    # Parse timestamp or use current time
    if timestamp_str:
        taken_at = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
    else:
        taken_at = datetime.now()
    
    # Create log entry
    db_log = LogModel(
        medication_id=medication_id,
        taken_at=taken_at,
        was_taken=was_taken,
        notes=notes
    )
    
    db.add(db_log)
    db.commit()
    db.refresh(db_log)
    
    return {
        "success": True,
        "message": f"Dose {'taken' if was_taken else 'missed'} logged successfully",
        "log": {
            "id": db_log.id,
            "medication_id": db_log.medication_id,
            "taken_at": db_log.taken_at.isoformat(),
            "was_taken": db_log.was_taken
        }
    }

# ============================================================================
# REMINDER ENDPOINTS
# ============================================================================

@app.get("/reminders", response_model=List[dict])
def get_reminders(
    medication_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """Get all reminders, optionally filtered by medication"""
    query = db.query(ReminderModel)
    
    if medication_id:
        query = query.filter(ReminderModel.medication_id == medication_id)
    
    reminders = query.all()
    
    return [
        {
            "id": reminder.id,
            "medication_id": reminder.medication_id,
            "reminder_time": str(reminder.reminder_time),
            "is_sent": reminder.is_sent
        }
        for reminder in reminders
    ]

@app.post("/reminders", response_model=dict, status_code=status.HTTP_201_CREATED)
def create_reminder(reminder_data: dict, db: Session = Depends(get_db)):
    """
    Create a reminder for a medication
    
    Send: {
        "medication_id": 1,
        "reminder_time": "08:00:00"
    }
    """
    medication_id = reminder_data.get("medication_id")
    reminder_time_str = reminder_data.get("reminder_time")
    
    if not medication_id or not reminder_time_str:
        raise HTTPException(status_code=400, detail="medication_id and reminder_time required")
    
    # Verify medication exists
    medication = db.query(MedicationModel).filter(MedicationModel.id == medication_id).first()
    if not medication:
        raise HTTPException(status_code=404, detail="Medication not found")
    
    # Parse time (format: "HH:MM:SS" or "HH:MM")
    try:
        time_parts = reminder_time_str.split(":")
        hour = int(time_parts[0])
        minute = int(time_parts[1])
        second = int(time_parts[2]) if len(time_parts) > 2 else 0
        reminder_time = time(hour, minute, second)
    except (ValueError, IndexError):
        raise HTTPException(status_code=400, detail="Invalid time format. Use HH:MM:SS or HH:MM")
    
    # Create reminder
    db_reminder = ReminderModel(
        medication_id=medication_id,
        reminder_time=reminder_time,
        is_sent=False
    )
    
    db.add(db_reminder)
    db.commit()
    db.refresh(db_reminder)
    
    return {
        "success": True,
        "message": "Reminder created",
        "reminder": {
            "id": db_reminder.id,
            "medication_id": db_reminder.medication_id,
            "reminder_time": str(db_reminder.reminder_time)
        }
    }

# ============================================================================
# STATISTICS ENDPOINTS
# ============================================================================

@app.get("/stats/summary")
def get_stats_summary(db: Session = Depends(get_db)):
    """Get summary statistics for the dashboard"""
    
    # Count active medications
    active_count = db.query(MedicationModel).filter(MedicationModel.is_active == True).count()
    
    # Count doses taken today
    today = date.today()
    today_logs = db.query(LogModel).filter(
        LogModel.taken_at >= datetime.combine(today, time.min),
        LogModel.taken_at <= datetime.combine(today, time.max),
        LogModel.was_taken == True
    ).count()
    
    # Count total medications
    total_count = db.query(MedicationModel).count()
    
    return {
        "active_medications": active_count,
        "taken_today": today_logs,
        "total_medications": total_count,
        "inactive_medications": total_count - active_count
    }

# ============================================================================
# RUN THE APP
# ============================================================================
# Run with: uvicorn main:app --reload