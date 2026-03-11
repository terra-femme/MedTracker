import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import MedicationLog as LogModel
from backend.agents.autocomplete_agent import AutocompleteAgent
from backend.agents.dose_agent import DoseAgent
from backend.agents.schedule_agent import ScheduleAgent
from backend.agents.adherence_agent import AdherenceAgent
from backend.agents.medication_agent import MedicationAgent
from backend.core import state

router = APIRouter()


@router.get("/autocomplete/medications")
def autocomplete_medications(q: str, limit: int = 6, debug: bool = False):
    """
    Autocomplete medication names using AutocompleteAgent.
    Example: GET /autocomplete/medications?q=advil
    """
    if not q or len(q) < 2:
        return {"query": q, "suggestions": [], "spelling_suggestions": []}

    try:
        agent = AutocompleteAgent(state.medication_kb)
        result = agent.search(q, limit=limit)
        if not debug:
            result.pop("debug", None)
        return result
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"query": q, "suggestions": [], "spelling_suggestions": [], "error": str(e)}


@router.get("/autocomplete/spelling")
def get_spelling_suggestions(q: str):
    """
    Get spelling suggestions for a potentially misspelled drug name.
    Example: GET /autocomplete/spelling?q=asprin
    """
    if not q or len(q) < 2:
        return {"original": q, "suggestions": []}
    try:
        return {
            "original": q,
            "suggestions": state.medication_kb.get_spelling_suggestions(q),
            "source": "RxNorm",
        }
    except Exception as e:
        return {"original": q, "suggestions": [], "error": str(e)}


@router.get("/debug/autocomplete/{query}")
def debug_autocomplete(query: str):
    """Debug endpoint to inspect autocomplete results"""
    raw_results = state.medication_kb.get_approximate_matches(query, limit=10)
    filtered_results = state.medication_kb.autocomplete(query, limit=8)
    return {
        "query": query,
        "raw_count": len(raw_results),
        "filtered_count": len(filtered_results),
        "raw_results": [{"name": r["name"], "score": r.get("score")} for r in raw_results[:5]],
        "filtered_results": filtered_results,
        "spelling": state.medication_kb.get_spelling_suggestions(query),
    }


@router.get("/debug/fda-lookup/{drug_name}")
def debug_fda_lookup(drug_name: str):
    """Debug endpoint to test FDA lookup directly"""
    logging.basicConfig(level=logging.DEBUG)
    old_debug = state.medication_kb.debug
    state.medication_kb.debug = True
    result = state.medication_kb.get_quick_drug_summary(drug_name)
    state.medication_kb.debug = old_debug
    return result


@router.post("/debug/clear-logs")
def clear_all_logs(db: Session = Depends(get_db)):
    """DEBUG: Clear all medication logs (for testing)"""
    try:
        count = db.query(LogModel).delete()
        db.commit()
        return {"success": True, "message": f"Cleared {count} log entries", "cleared_count": count}
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}


@router.get("/debug/agents")
def debug_agents(db: Session = Depends(get_db)):
    """Debug endpoint to test all agents"""
    results = {}

    try:
        med_agent = MedicationAgent(db)
        meds = med_agent.get_all(include_archived=True)
        results['medication_agent'] = {
            'status': 'ok',
            'count': len(meds),
            'medications': [{'id': m.id, 'name': m.name, 'active': m.is_active} for m in meds[:3]],
        }
    except Exception as e:
        results['medication_agent'] = {'status': 'error', 'error': str(e)}

    try:
        today_logs = DoseAgent(db).get_today_logs()
        results['dose_agent'] = {'status': 'ok', 'today_logs_count': len(today_logs)}
    except Exception as e:
        results['dose_agent'] = {'status': 'error', 'error': str(e)}

    try:
        schedule = ScheduleAgent(db).get_today_schedule()
        results['schedule_agent'] = {
            'status': 'ok',
            'now_count': len(schedule.now),
            'later_count': len(schedule.later),
            'missed_count': len(schedule.missed),
            'taken_count': len(schedule.taken),
        }
    except Exception as e:
        results['schedule_agent'] = {'status': 'error', 'error': str(e)}

    try:
        today = AdherenceAgent(db).get_today_summary()
        results['adherence_agent'] = {'status': 'ok', 'today_summary': today}
    except Exception as e:
        results['adherence_agent'] = {'status': 'error', 'error': str(e)}

    return results
