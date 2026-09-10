
"""
Single Firebase project does two jobs here:
  1. Firestore = the database (shelters, community reports, emergency logs,
     registered devices) — no Postgres/SQLAlchemy needed.
  2. Cloud Messaging (FCM) = free push notifications, replacing paid Twilio
     SMS for the SOS button.

Setup (also in README.md):
  1. https://console.firebase.google.com -> create a project
  2. Build > Firestore Database -> Create database (test mode is fine to start)
  3. Build > Cloud Messaging -> enable it
  4. Project settings (gear icon) > Service accounts > Generate new private key
     -> save the JSON as `firebase-service-account.json` in this folder
"""

import logging
import os
from datetime import datetime, timezone
from typing import Optional

import firebase_admin
from firebase_admin import credentials, firestore, messaging

from app.core.config import settings

logger = logging.getLogger("resq.firebase")

firebase_app: Optional[firebase_admin.App] = None
db: Optional[firestore.Client] = None
firebase_available: bool = False
firebase_error_detail: Optional[str] = None


def init_firebase() -> None:
    global firebase_app, db, firebase_available, firebase_error_detail
    cred_path = settings.firebase_credentials_path

    if not cred_path or not os.path.exists(cred_path):
        firebase_available = False
        firebase_error_detail = "Firebase credentials file not found"
        logger.warning(
            "Firebase credentials file '%s' not found. "
            "Running in degraded mode without Firestore/FCM.",
            cred_path,
        )
        return

    try:
        if not firebase_admin._apps:
            firebase_app = firebase_admin.initialize_app(
                credentials.Certificate(cred_path)
            )
        else:
            firebase_app = firebase_admin.get_app()
        db = firestore.client()
        firebase_available = True
        firebase_error_detail = None
        logger.info("Firebase initialized successfully.")
    except Exception as exc:
        firebase_available = False
        firebase_error_detail = f"Firebase initialization failed: {type(exc).__name__}"
        logger.warning(
            "Failed to initialize Firebase (%s). Running in degraded mode without Firestore/FCM.",
            type(exc).__name__,
        )


# Attempt initialization at import time defensively
init_firebase()

# Backward-compatibility alias
_app = firebase_app

SHELTERS_COLLECTION = "shelters"
REPORTS_COLLECTION = "community_reports"
LOGS_COLLECTION = "emergency_logs"
DEVICES_COLLECTION = "device_tokens"
SOS_EVENTS_COLLECTION = "sos_events"


# ---------- Shelters ----------
def list_shelters() -> list[dict]:
    if not firebase_available or db is None:
        logger.warning("list_shelters: Firebase is unavailable, returning empty list.")
        return []
    docs = db.collection(SHELTERS_COLLECTION).stream()
    return [{"id": doc.id, **doc.to_dict()} for doc in docs]


def add_shelter(data: dict) -> str:
    if not firebase_available or db is None:
        logger.warning("add_shelter: Firebase is unavailable, shelter not persisted.")
        raise RuntimeError("Firebase/Firestore is unavailable; cannot add shelter")
    ref = db.collection(SHELTERS_COLLECTION).document()
    ref.set(data)
    return ref.id


# ---------- Community reports ----------
def list_reports() -> list[dict]:
    if not firebase_available or db is None:
        logger.warning("list_reports: Firebase is unavailable, returning empty list.")
        return []
    docs = (
        db.collection(REPORTS_COLLECTION)
        .order_by("created_at", direction=firestore.Query.DESCENDING)
        .stream()
    )
    return [{"id": doc.id, **doc.to_dict()} for doc in docs]


def add_report(area: str, message: str, reporter_name: str | None = None) -> dict:
    if not firebase_available or db is None:
        logger.warning("add_report: Firebase is unavailable, report not persisted.")
        raise RuntimeError("Firebase/Firestore is unavailable; cannot add report")
    data = {
        "area": area,
        "message": message,
        "reporter_name": reporter_name,
        "verified": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    ref = db.collection(REPORTS_COLLECTION).document()
    ref.set(data)
    return {"id": ref.id, **data}


# ---------- Emergency logs ----------
def log_emergency(description: str, emergency_level: str, city: str) -> None:
    if not firebase_available or db is None:
        logger.warning("log_emergency: Firebase is unavailable, emergency log not persisted.")
        return
    db.collection(LOGS_COLLECTION).document().set(
        {
            "description": description,
            "emergency_level": emergency_level,
            "city": city,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )


# ---------- SOS events ----------
def create_sos_record(data: dict) -> str:
    """Persist an initial SOS event record and return the auto-generated event_id.

    Raises RuntimeError if Firestore is unavailable — callers must handle this
    and return a *degraded* response rather than letting the exception propagate.
    """
    if not firebase_available or db is None:
        logger.warning("create_sos_record: Firebase is unavailable; SOS event not persisted.")
        raise RuntimeError("Firebase/Firestore is unavailable; cannot persist SOS event")
    ref = db.collection(SOS_EVENTS_COLLECTION).document()
    ref.set(data)
    return ref.id


def update_sos_record(event_id: str, updates: dict) -> None:
    """Update an existing SOS event record in-place (e.g. notification outcome).

    Failures here are logged but *not* re-raised — the original record is
    already persisted, so an update failure must not shadow the successful
    create or cause the router to return a worse status than warranted.
    """
    if not firebase_available or db is None:
        logger.warning(
            "update_sos_record: Firebase is unavailable; cannot update event %s.", event_id
        )
        return
    try:
        db.collection(SOS_EVENTS_COLLECTION).document(event_id).update(updates)
    except Exception as exc:
        logger.warning(
            "update_sos_record: failed to update event %s (%s: %s); "
            "original record remains intact.",
            event_id,
            type(exc).__name__,
            exc,
        )


# ---------- Device tokens + push notifications ----------
def register_device(token: str) -> None:
    """Save the token and subscribe it to the shared alert topic, so every
    registered device gets SOS/alert pushes without per-device targeting."""
    if not firebase_available or db is None:
        logger.warning("register_device: Firebase is unavailable, device token not registered.")
        return
    db.collection(DEVICES_COLLECTION).document(token).set(
        {"token": token, "registered_at": datetime.now(timezone.utc).isoformat()}
    )
    messaging.subscribe_to_topic([token], settings.firebase_alert_topic)


def send_topic_push(title: str, body: str, data: dict | None = None) -> str:
    if not firebase_available:
        logger.warning("send_topic_push: Firebase/FCM is unavailable.")
        raise RuntimeError("Firebase Cloud Messaging is unavailable")
    message = messaging.Message(
        notification=messaging.Notification(title=title, body=body),
        data={k: str(v) for k, v in (data or {}).items()},
        topic=settings.firebase_alert_topic,
    )
    return messaging.send(message)
