from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import PushSubscription as PushSubscriptionModel, User
from backend.schemas import PushSubscriptionCreate
from backend.services.push_service import is_push_configured, send_push_notification, VAPID_PUBLIC_KEY
from backend.core.security import get_current_user

# vapid-key is intentionally public — the browser needs it before the user
# has logged in, to set up the push subscription object.
router = APIRouter()


@router.get("/push/vapid-key")
def get_vapid_public_key():
    """
    Return the VAPID public key so the browser can create a push subscription.
    Returns 503 if VAPID keys are not configured.
    """
    if not is_push_configured():
        raise HTTPException(
            status_code=503,
            detail="Push notifications not configured. Set VAPID_PRIVATE_KEY and VAPID_PUBLIC_KEY in .env",
        )
    return {"public_key": VAPID_PUBLIC_KEY}


@router.post("/push/subscribe", status_code=201)
def subscribe_push(
    subscription: PushSubscriptionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    existing = (
        db.query(PushSubscriptionModel)
        .filter(PushSubscriptionModel.endpoint == subscription.endpoint)
        .first()
    )

    if existing:
        existing.is_active = True
        existing.user_id = current_user.id
        existing.p256dh_key = subscription.keys.p256dh
        existing.auth_key = subscription.keys.auth
        db.commit()
        return {"success": True, "message": "Subscription updated"}

    db.add(PushSubscriptionModel(
        endpoint=subscription.endpoint,
        p256dh_key=subscription.keys.p256dh,
        auth_key=subscription.keys.auth,
        user_id=current_user.id,
    ))
    db.commit()
    return {"success": True, "message": "Subscribed to push notifications"}


@router.delete("/push/unsubscribe")
def unsubscribe_push(
    endpoint: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    sub = (
        db.query(PushSubscriptionModel)
        .filter(
            PushSubscriptionModel.endpoint == endpoint,
            PushSubscriptionModel.user_id == current_user.id,
        )
        .first()
    )
    if sub:
        sub.is_active = False
        db.commit()
    return {"success": True, "message": "Unsubscribed from push notifications"}
