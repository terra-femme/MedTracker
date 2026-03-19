from datetime import date, time as dt_time
from typing import List

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import Medication as MedicationModel, Reminder as ReminderModel, User
from backend import schemas
from backend.agents.medication_agent import MedicationAgent
from backend.core import state
from backend.core.security import get_current_user

router = APIRouter(dependencies=[Depends(get_current_user)])


@router.get("/medications", response_model=List[schemas.Medication])
def get_medications(
    active_only: bool = False,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        query = db.query(MedicationModel).filter(MedicationModel.user_id == current_user.id)
        if active_only:
            query = query.filter(MedicationModel.is_active == True)
        return query.offset(skip).limit(limit).all()
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/medications/{medication_id}", response_model=schemas.Medication)
def get_medication(
    medication_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    medication = db.query(MedicationModel).filter(
        MedicationModel.id == medication_id,
        MedicationModel.user_id == current_user.id,
    ).first()
    if not medication:
        raise HTTPException(status_code=404, detail="Medication not found")
    return medication


@router.post("/medications", response_model=schemas.Medication, status_code=status.HTTP_201_CREATED)
def create_medication(
    medication: schemas.MedicationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db_medication = MedicationModel(
        user_id=current_user.id,
        name=medication.name,
        rxcui=medication.rxcui,
        form_type=medication.form_type,
        strength=medication.strength,
        strength_unit=medication.strength_unit,
        method_of_intake=medication.method_of_intake,
        dosage=medication.dosage,
        quantity=medication.quantity,
        quantity_unit=medication.quantity_unit,
        when_to_take=medication.when_to_take,
        frequency=medication.frequency,
        start_date=medication.start_date,
        end_date=medication.end_date,
        is_long_term=medication.is_long_term,
        is_active=medication.is_active,
        notes=medication.notes,
        taken_for=medication.taken_for,
    )

    db.add(db_medication)
    db.commit()
    db.refresh(db_medication)

    if medication.reminder_times and len(medication.reminder_times) > 0:
        for time_str in medication.reminder_times:
            try:
                hour, minute = map(int, time_str.split(':'))
                db_reminder = ReminderModel(
                    medication_id=db_medication.id,
                    reminder_time=dt_time(hour=hour, minute=minute),
                    is_sent=False,
                )
                db.add(db_reminder)
            except Exception as e:
                print(f"Warning: Could not create reminder for time {time_str}: {e}")
        db.commit()

    if state.rag_chatbot is not None:
        try:
            state.rag_chatbot.add_medication_to_knowledge_base(db_medication.name)
            state.rag_chatbot.add_user_medications_to_kb([{
                "id": db_medication.id,
                "name": db_medication.name,
                "dosage": db_medication.dosage,
                "frequency": db_medication.frequency,
                "notes": db_medication.notes,
                "is_active": db_medication.is_active,
            }])
        except Exception as e:
            print(f"Warning: Could not add to chatbot KB: {e}")

    return db_medication


@router.put("/medications/{medication_id}", response_model=schemas.Medication)
def update_medication(
    medication_id: int,
    medication: schemas.MedicationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db_medication = db.query(MedicationModel).filter(
        MedicationModel.id == medication_id,
        MedicationModel.user_id == current_user.id,
    ).first()
    if not db_medication:
        raise HTTPException(status_code=404, detail="Medication not found")

    update_data = medication.model_dump(exclude_unset=True)
    reminder_times = update_data.pop('reminder_times', None)

    for field, value in update_data.items():
        setattr(db_medication, field, value)

    if reminder_times is not None:
        db.query(ReminderModel).filter(ReminderModel.medication_id == medication_id).delete()
        for time_str in reminder_times:
            try:
                hour, minute = map(int, time_str.split(':'))
                db.add(ReminderModel(
                    medication_id=medication_id,
                    reminder_time=dt_time(hour=hour, minute=minute),
                    is_sent=False,
                ))
            except Exception as e:
                print(f"Warning: Could not create reminder for time {time_str}: {e}")

    db.commit()
    db.refresh(db_medication)
    return db_medication


@router.delete("/medications/{medication_id}")
def delete_medication(
    medication_id: int,
    permanent: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Ownership check before delete
    med = db.query(MedicationModel).filter(
        MedicationModel.id == medication_id,
        MedicationModel.user_id == current_user.id,
    ).first()
    if not med:
        raise HTTPException(status_code=404, detail="Medication not found")
    agent = MedicationAgent(db, user_id=current_user.id)
    if not agent.delete(medication_id, permanent=permanent):
        raise HTTPException(status_code=404, detail="Medication not found")
    return {
        "message": "Medication permanently deleted" if permanent else "Medication archived",
        "id": medication_id,
        "permanent": permanent,
    }


@router.post("/medications/{medication_id}/restore")
def restore_medication(
    medication_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    med = db.query(MedicationModel).filter(
        MedicationModel.id == medication_id,
        MedicationModel.user_id == current_user.id,
    ).first()
    if not med:
        raise HTTPException(status_code=404, detail="Medication not found")
    agent = MedicationAgent(db, user_id=current_user.id)
    if not agent.restore(medication_id):
        raise HTTPException(status_code=404, detail="Medication not found")
    return {"message": "Medication restored", "id": medication_id}


@router.post("/medications/natural", response_model=dict, status_code=status.HTTP_201_CREATED)
def create_medication_from_natural_language(input_text: dict, db: Session = Depends(get_db)):
    """
    Create medication using natural language input.
    Send: {"text": "Add aspirin 500mg twice daily"}
    """
    text = input_text.get("text", "")
    if not text:
        raise HTTPException(status_code=400, detail="No text provided")

    parsed = state.nlp_parser.parse_medication_input(text)
    if not parsed['name']:
        raise HTTPException(
            status_code=400,
            detail="Could not understand medication name. Try: 'Add [medication name] [dosage] [frequency]'"
        )

    db_medication = MedicationModel(
        name=parsed['name'],
        dosage=parsed['dosage'] or 'as directed',
        frequency=parsed['frequency'] or 'as directed',
        start_date=date.today(),
        is_active=True,
        notes=parsed['notes'],
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
            "notes": db_medication.notes,
        },
        "parsed_from": text,
        "understood_as": parsed,
    }


@router.post("/medications/parse", response_model=dict)
def parse_natural_language_test(input_text: dict):
    """
    Test endpoint: see what the NLP understands before creating.
    Send: {"text": "Add aspirin 500mg twice daily"}
    """
    text = input_text.get("text", "")
    if not text:
        raise HTTPException(status_code=400, detail="No text provided")
    parsed = state.nlp_parser.parse_medication_input(text)
    return {
        "original_text": text,
        "understood_as": parsed,
        "tip": "If this looks correct, use /medications/natural to actually create it!",
    }


@router.get("/medications/lookup/{rxcui}")
def lookup_medication_by_rxcui(rxcui: str):
    """Look up detailed medication information by RxCUI"""
    try:
        return state.medication_kb.get_drug_details(rxcui)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/medications/drug-info/{drug_name}")
def get_drug_information(drug_name: str):
    """Get comprehensive drug information from FDA database"""
    if not drug_name or len(drug_name) < 2:
        raise HTTPException(status_code=400, detail="Drug name must be at least 2 characters")
    try:
        drug_info = state.medication_kb.get_quick_drug_summary(drug_name)
        if drug_info.get('success'):
            return drug_info
        return {
            "success": False,
            "drug_name": drug_name,
            "error": drug_info.get('error', 'Could not find drug information'),
            "message": "Drug not found in FDA database. Try a different spelling.",
            "suggestion": "You can still add this medication - fill in details manually.",
        }
    except Exception as e:
        print(f"Drug info error for {drug_name}: {e}")
        return {"success": False, "drug_name": drug_name, "error": str(e), "message": "Error fetching drug information."}


@router.post("/ocr/extract")
async def extract_medication_from_image(image: UploadFile = File(...)):
    """
    Extract medication information from an image (pill bottle label, prescription).

    PRIVACY-FIRST: Image is processed and immediately discarded — never stored.
    CURRENT: Returns placeholder (Tesseract.js runs client-side).
    FUTURE: LLaVA or DeepEyesV2 integration.
    """
    return {
        "status": "client_side_ocr",
        "message": "For privacy, OCR is performed in your browser using Tesseract.js",
        "privacy_note": "Your medication images never leave your device",
        "future_upgrade": "This endpoint is ready for LLaVA/DeepEyesV2 vision AI integration",
        "instructions": "Use the client-side OCR in the frontend form",
    }


@router.post("/vision/analyze")
async def analyze_medication_image(request: dict):
    """
    FUTURE ENDPOINT: Analyze medication image using vision AI (LLaVA / DeepEyesV2).
    Image should be sent as base64 to avoid file storage.
    """
    return {
        "status": "not_implemented",
        "message": "Vision AI endpoint - coming in Phase 2!",
        "planned_features": [
            "Visual pill identification with LLaVA",
            "Smart medication verification",
            "Drug interaction detection from images",
            "DeepEyesV2 agentic reasoning (Phase 3)",
        ],
        "current_alternative": "Use client-side Tesseract.js OCR for text extraction",
    }
