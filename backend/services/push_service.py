"""
Push Notification Service
=========================
Sends Web Push Protocol notifications to subscribed browsers using VAPID auth.

Configuration (set in .env):
    VAPID_PRIVATE_KEY  — PEM-encoded private key (generated once, never change)
    VAPID_PUBLIC_KEY   — URL-safe base64 public key (sent to browser on subscribe)
    VAPID_EMAIL        — Contact email included in VAPID claims

To generate keys (run once in terminal):
    python -c "
    from py_vapid import Vapid
    v = Vapid()
    v.generate_keys()
    print('Private:', v.private_pem().decode())
    print('Public:', v.public_key.public_bytes_raw().hex())
    "
"""

import os
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

VAPID_PRIVATE_KEY: Optional[str] = os.environ.get("VAPID_PRIVATE_KEY")
VAPID_PUBLIC_KEY: Optional[str] = os.environ.get("VAPID_PUBLIC_KEY")
VAPID_EMAIL: str = os.environ.get("VAPID_EMAIL", "mailto:admin@medtracker.local")


def is_push_configured() -> bool:
    """Return True if VAPID keys are available in the environment."""
    return bool(VAPID_PRIVATE_KEY and VAPID_PUBLIC_KEY)


def send_push_notification(
    endpoint: str,
    p256dh: str,
    auth: str,
    title: str,
    body: str,
    icon: str = "/static/icon-192.png",
    badge: str = "/static/icon-72.png",
    tag: str = "medtracker-dose",
) -> bool:
    """
    Send a single Web Push notification to one browser subscription.

    Args:
        endpoint: The push service URL from the browser subscription
        p256dh:   Browser's ECDH public key (base64url)
        auth:     Auth secret (base64url)
        title:    Notification title (e.g., "Time for Lisinopril")
        body:     Notification body (e.g., "10 mg — scheduled for 8:00 am")
        icon:     URL to notification icon image
        badge:    URL to small badge icon (Android)
        tag:      Notification tag — same tag replaces previous notification

    Returns:
        True on success. False on non-fatal failure.

    Raises:
        WebPushException with status 410 when the subscription has expired.
        Caller must delete the subscription from the DB on 410.
    """
    if not is_push_configured():
        logger.warning("push_service: VAPID keys not configured — notification skipped")
        return False

    try:
        from pywebpush import webpush, WebPushException
    except ImportError:
        logger.error("push_service: pywebpush not installed — run: pip install pywebpush")
        return False

    payload = json.dumps({
        "title": title,
        "body": body,
        "icon": icon,
        "badge": badge,
        "tag": tag,
    })

    try:
        webpush(
            subscription_info={
                "endpoint": endpoint,
                "keys": {"p256dh": p256dh, "auth": auth},
            },
            data=payload,
            vapid_private_key=VAPID_PRIVATE_KEY,
            vapid_claims={"sub": VAPID_EMAIL},
            ttl=3600,  # Notification stays queued for 1 hour if browser is offline
        )
        logger.info(f"push_service: notification sent — tag={tag}")
        return True

    except Exception as e:
        # Import here so the module still loads if pywebpush is missing
        from pywebpush import WebPushException  # noqa: F811

        if isinstance(e, WebPushException) and e.response is not None:
            if e.response.status_code == 410:
                # 410 Gone — subscription is permanently expired
                logger.info(f"push_service: subscription expired (410) for endpoint {endpoint[:50]}...")
                raise  # Caller handles by deactivating the DB row
            logger.error(f"push_service: WebPush error {e.response.status_code}: {e}")
        else:
            logger.error(f"push_service: unexpected error: {e}")

        return False
