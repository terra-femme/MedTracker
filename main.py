"""
MedTracker - FastAPI Backend
"""
import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from apscheduler.schedulers.background import BackgroundScheduler

from backend.database import engine, Base, SessionLocal
from backend.models import Reminder as ReminderModel, PushSubscription as PushSubscriptionModel
from backend.agents.schedule_agent import ScheduleAgent
from backend.services.push_service import is_push_configured, send_push_notification

from backend.routers import medications, logs, stats, schedule, reminders, push, chatbot, autocomplete, auth

logger = logging.getLogger(__name__)

Base.metadata.create_all(bind=engine)


# ============================================================================
# BACKGROUND SCHEDULER — Push Notification Jobs
# ============================================================================

_scheduler = BackgroundScheduler(timezone="UTC")


def _check_and_send_notifications() -> None:
    """
    Runs every 60 seconds via APScheduler.
    Finds medications in the NOW bucket and sends a push notification to every
    active browser subscription. Sets Reminder.is_sent=True so we don't
    re-notify for the same dose within the same day.
    """
    if not is_push_configured():
        return

    db = SessionLocal()
    try:
        schedule_agent = ScheduleAgent(db)
        schedule = schedule_agent.get_today_schedule()
        now_doses = schedule.now

        if not now_doses:
            return

        subscriptions = (
            db.query(PushSubscriptionModel)
            .filter(PushSubscriptionModel.is_active == True)
            .all()
        )

        if not subscriptions:
            return

        for dose in now_doses:
            reminder = (
                db.query(ReminderModel)
                .filter(
                    ReminderModel.medication_id == dose.medication_id,
                    ReminderModel.is_active == True,
                )
                .first()
            )

            if reminder and reminder.is_sent:
                continue

            for sub in subscriptions:
                try:
                    send_push_notification(
                        endpoint=sub.endpoint,
                        p256dh=sub.p256dh_key,
                        auth=sub.auth_key,
                        title=f"Time for {dose.name}",
                        body=f"{dose.dosage} — scheduled for {dose.display_time}",
                        tag=f"medtracker-{dose.medication_id}",
                    )
                except Exception:
                    sub.is_active = False
                    db.commit()

            if reminder:
                reminder.is_sent = True
                db.commit()

    except Exception as exc:
        logger.error(f"notification scheduler error: {exc}")
    finally:
        db.close()


def _reset_is_sent_flags() -> None:
    """Runs at 12:01 AM. Resets all Reminder.is_sent flags for the next day."""
    db = SessionLocal()
    try:
        db.query(ReminderModel).update({"is_sent": False})
        db.commit()
        logger.info("midnight reset: Reminder.is_sent flags cleared")
    except Exception as exc:
        logger.error(f"midnight reset error: {exc}")
        db.rollback()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    """FastAPI lifespan: start scheduler on startup, stop on shutdown."""
    _scheduler.add_job(_check_and_send_notifications, "interval", seconds=60,
                       id="notification_check", replace_existing=True)
    _scheduler.add_job(_reset_is_sent_flags, "cron", hour=0, minute=1,
                       id="reset_is_sent", replace_existing=True)
    _scheduler.start()
    logger.info("APScheduler started — push notification jobs registered")
    try:
        yield
    finally:
        try:
            _scheduler.pause()          # stop new jobs from firing immediately
            _scheduler.shutdown(wait=False)
            logger.info("APScheduler stopped")
        except Exception as exc:
            logger.warning(f"APScheduler shutdown error (safe to ignore): {exc}")


# ============================================================================
# APP
# ============================================================================

app = FastAPI(
    title="MedTracker - Medication Reminder",
    description="Smart medication tracking with natural language processing and autocomplete",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

frontend_dir = os.path.join(os.path.dirname(__file__), "frontend")
if os.path.exists(frontend_dir):
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")
else:
    app.mount("/static", StaticFiles(directory="frontend"), name="static")

# Register routers
app.include_router(auth.router)
app.include_router(medications.router)
app.include_router(logs.router)
app.include_router(stats.router)
app.include_router(schedule.router)
app.include_router(reminders.router)
app.include_router(push.router)
app.include_router(chatbot.router)
app.include_router(autocomplete.router)


# ============================================================================
# ROOT & HEALTH
# ============================================================================

@app.get("/")
async def serve_homepage():
    """Serve the main HTML page from frontend folder"""
    possible_paths = [
        os.path.join(os.path.dirname(__file__), "frontend", "index.html"),
        os.path.join("frontend", "index.html"),
        "frontend/index.html",
    ]
    for path in possible_paths:
        if os.path.exists(path):
            return FileResponse(path)
    return {"message": "MedTracker API is running! Add index.html to frontend/ folder"}


@app.get("/sw.js")
async def serve_service_worker():
    """Serve service worker at root scope — required for push notifications to work."""
    possible_paths = [
        os.path.join(os.path.dirname(__file__), "frontend", "sw.js"),
        os.path.join("frontend", "sw.js"),
    ]
    for path in possible_paths:
        if os.path.exists(path):
            return FileResponse(path, media_type="application/javascript")
    from fastapi import HTTPException
    raise HTTPException(status_code=404, detail="sw.js not found")


@app.get("/api/health")
def health_check():
    """Check if API is running"""
    return {
        "status": "healthy",
        "message": "MedTracker API is running",
        "version": "2.0.0",
        "features": [
            "NLP input",
            "Medication tracking",
            "Dose logging",
            "Reminders",
            "Autocomplete with spell-check",
            "OCR-ready architecture",
        ],
    }
