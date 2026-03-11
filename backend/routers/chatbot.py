from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import Medication as MedicationModel
from backend.core import state
from backend.medication_langgraph import LANGGRAPH_AVAILABLE

router = APIRouter()


# ============================================================================
# RAG CHATBOT
# ============================================================================

@router.post("/chatbot/initialize")
def initialize_chatbot(config: dict, db: Session = Depends(get_db)):
    """Initialize the RAG chatbot with Ollama"""
    try:
        from backend.medication_rag_chatbot import MedicationRAGChatbot

        medications = db.query(MedicationModel).filter(MedicationModel.is_active == True).all()
        med_dicts = [
            {"name": m.name, "dosage": m.dosage, "frequency": m.frequency, "notes": m.notes}
            for m in medications
        ]

        state.rag_chatbot = MedicationRAGChatbot(model_name="llama3", user_medications=med_dicts)

        return {
            "success": True,
            "message": "Chatbot initialized with Ollama!",
            "medications_loaded": len(medications),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to initialize chatbot: {str(e)}")


@router.get("/chatbot/status")
def chatbot_status():
    """Check if chatbot is initialized"""
    if state.rag_chatbot is None:
        return {"initialized": False, "message": "Chatbot not initialized. Call /chatbot/initialize first."}
    return {"initialized": True, "message": "Chatbot is ready!"}


@router.post("/chatbot/ask", response_model=dict)
def ask_chatbot(request: dict):
    """Ask the RAG chatbot a question"""
    if state.rag_chatbot is None:
        raise HTTPException(status_code=400, detail="Chatbot not initialized. Call /chatbot/initialize first.")

    question = request.get("question", "")
    if not question:
        raise HTTPException(status_code=400, detail="Question is required")

    try:
        answer = state.rag_chatbot.ask_question(question)
        return {
            "success": True,
            "question": question,
            "answer": answer,
            "source": "RAG (Retrieval Augmented Generation)",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error answering question: {str(e)}")


# ============================================================================
# LANGGRAPH CHATBOT
# ============================================================================

@router.post("/chatbot/langgraph/initialize")
def initialize_langgraph_chatbot(config: dict, db: Session = Depends(get_db)):
    """
    Initialize the LangGraph chatbot with stateful workflow.
    Features: conditional routing, drug interaction checking, emergency detection, audit logging.
    """
    try:
        from backend.medication_langgraph import MedTrackerLangGraphV2

        if not LANGGRAPH_AVAILABLE:
            raise HTTPException(
                status_code=500,
                detail="LangGraph not installed. Run: pip install langgraph",
            )

        medications = db.query(MedicationModel).filter(MedicationModel.is_active == True).all()
        med_dicts = [
            {
                "id": m.id, "name": m.name, "dosage": m.dosage,
                "frequency": m.frequency, "notes": m.notes, "taken_for": m.taken_for,
            }
            for m in medications
        ]

        state.langgraph_chatbot = MedTrackerLangGraphV2(
            model_name=config.get("model", "llama3"),
            user_medications=med_dicts,
            db_path="./chroma_db",
        )

        return {
            "success": True,
            "message": "LangGraph chatbot initialized!",
            "medications_loaded": len(med_dicts),
            "features": [
                "Question classification & routing",
                "Drug interaction detection",
                "Emergency handling",
                "Full audit logging",
            ],
        }
    except ImportError:
        raise HTTPException(status_code=500, detail="medication_langgraph.py not found in backend/")
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Initialization failed: {str(e)}")


@router.get("/chatbot/langgraph/status")
def langgraph_status():
    """Check if LangGraph chatbot is ready"""
    if state.langgraph_chatbot is None:
        return {"initialized": False, "message": "Call /chatbot/langgraph/initialize first"}
    return {
        "initialized": True,
        "message": "LangGraph chatbot ready!",
        "thread_id": state.langgraph_chatbot.thread_id,
        "conversation_count": len(state.langgraph_chatbot.get_conversation_history()),
    }


@router.post("/chatbot/langgraph/ask")
def ask_langgraph(request: dict):
    """
    Ask the LangGraph chatbot. The graph classifies the question, routes it,
    checks interactions if needed, and adds safety disclaimers.
    """
    if state.langgraph_chatbot is None:
        raise HTTPException(status_code=400, detail="Initialize chatbot first: /chatbot/langgraph/initialize")

    question = request.get("question", "")
    if not question:
        raise HTTPException(status_code=400, detail="Question required")

    try:
        answer = state.langgraph_chatbot.ask(question)
        history = state.langgraph_chatbot.get_conversation_history()
        last = history[-1] if history else {}
        return {
            "success": True,
            "question": question,
            "answer": answer,
            "question_type": last.get("question_type", "unknown"),
            "safety_flags": last.get("safety_flags", []),
            "source": "LangGraph",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/chatbot/langgraph/audit")
def get_audit_log():
    """Get audit log for compliance (HIPAA / healthcare quality assurance)"""
    if state.langgraph_chatbot is None:
        raise HTTPException(status_code=400, detail="Chatbot not initialized")
    return {
        "thread_id": state.langgraph_chatbot.thread_id,
        "conversation_history": state.langgraph_chatbot.get_conversation_history(),
        "audit_log": state.langgraph_chatbot.get_audit_log(),
    }


@router.post("/chatbot/langgraph/update-medications")
def update_langgraph_meds(db: Session = Depends(get_db)):
    """Sync active medications with the LangGraph chatbot"""
    if state.langgraph_chatbot is None:
        raise HTTPException(status_code=400, detail="Chatbot not initialized")

    medications = db.query(MedicationModel).filter(MedicationModel.is_active == True).all()
    med_dicts = [
        {"id": m.id, "name": m.name, "dosage": m.dosage, "frequency": m.frequency, "notes": m.notes}
        for m in medications
    ]
    state.langgraph_chatbot.update_medications(med_dicts)
    return {"success": True, "medications_updated": len(med_dicts)}
