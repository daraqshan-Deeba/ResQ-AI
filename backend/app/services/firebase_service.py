"""
Firebase Admin SDK — Cloud Messaging (FCM) push notifications only.

Hospital directory and other app data live in Supabase when configured.
Firestore hospital CRUD remains as a legacy fallback if Supabase is not set up.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import firebase_admin
from firebase_admin import credentials, firestore, messaging

from app.core.config import settings

logger = logging.getLogger("resq.firebase")

_BACKEND_DIR = Path(__file__).resolve().parents[2]
_ROOT_DIR = _BACKEND_DIR.parent

firebase_app: Optional[firebase_admin.App] = None
db: Optional[firestore.Client] = None
firebase_available: bool = False
firebase_error_detail: Optional[str] = None


def _resolve_credentials_path(path: str) -> str:
    if not path.strip():
        return ""
    candidate = Path(path)
    if candidate.is_absolute() and candidate.exists():
        return str(candidate)
    for base in (_BACKEND_DIR, _ROOT_DIR):
        resolved = base / path
        if resolved.exists():
            return str(resolved)
    return path


def _certificate_from_settings() -> Optional[credentials.Certificate]:
    project_id = settings.firebase_project_id.strip()
    client_email = settings.firebase_client_email.strip()
    private_key = settings.firebase_private_key.strip()

    if project_id and client_email and private_key:
        payload: dict[str, Any] = {
            "type": "service_account",
            "project_id": project_id,
            "private_key": private_key.replace("\\n", "\n"),
            "client_email": client_email,
            "token_uri": "https://oauth2.googleapis.com/token",
        }
        return credentials.Certificate(payload)

    cred_path = _resolve_credentials_path(settings.firebase_credentials_path)
    if cred_path and os.path.exists(cred_path):
        return credentials.Certificate(cred_path)

    return None


def init_firebase() -> None:
    global firebase_app, db, firebase_available, firebase_error_detail

    cert = _certificate_from_settings()
    if cert is None:
        firebase_available = False
        firebase_error_detail = "Firebase credentials not configured"
        logger.info(
            "Firebase not configured. Set FIREBASE_PROJECT_ID, FIREBASE_CLIENT_EMAIL, "
            "and FIREBASE_PRIVATE_KEY in .env (or FIREBASE_CREDENTIALS_PATH)."
        )
        return

    try:
        if not firebase_admin._apps:
            firebase_app = firebase_admin.initialize_app(cert)
        else:
            firebase_app = firebase_admin.get_app()
        db = firestore.client()
        firebase_available = True
        firebase_error_detail = None
        logger.info(
            "Firebase initialized (project=%s).",
            settings.firebase_project_id.strip() or "service-account",
        )
    except Exception as exc:
        firebase_available = False
        firebase_error_detail = f"Firebase initialization failed: {type(exc).__name__}"
        logger.warning(
            "Failed to initialize Firebase (%s). Running without FCM/Firestore.",
            type(exc).__name__,
        )


init_firebase()

SHELTERS_COLLECTION = "shelters"
HOSPITALS_COLLECTION = "hospitals"
REPORTS_COLLECTION = "community_reports"
LOGS_COLLECTION = "emergency_logs"
DEVICES_COLLECTION = "device_tokens"
SOS_EVENTS_COLLECTION = "sos_events"


def list_shelters() -> list[dict]:
    if not firebase_available or db is None:
        logger.warning("list_shelters: Firebase is unavailable, returning empty list.")
        return []
    docs = db.collection(SHELTERS_COLLECTION).stream()
    return [{"id": doc.id, **doc.to_dict()} for doc in docs]


def add_shelter(data: dict) -> str:
    if not firebase_available or db is None:
        raise RuntimeError("Firebase/Firestore is unavailable; cannot add shelter")
    ref = db.collection(SHELTERS_COLLECTION).document()
    ref.set(data)
    return ref.id


def list_hospitals() -> list[dict]:
    if not firebase_available or db is None:
        logger.warning("list_hospitals: Firebase is unavailable, returning empty list.")
        return []
    docs = db.collection(HOSPITALS_COLLECTION).stream()
    return [
        {
            "id": doc.id,
            "name": row.get("name", "Hospital"),
            "address": row.get("address"),
            "lat": row.get("lat"),
            "lon": row.get("lon"),
            "phone": row.get("phone"),
            "facility_type": row.get("facility_type"),
            "district": row.get("district"),
            "source": row.get("source", "firebase"),
        }
        for doc in docs
        for row in [doc.to_dict() or {}]
    ]


def add_hospital(data: dict) -> str:
    if not firebase_available or db is None:
        raise RuntimeError("Firebase/Firestore is unavailable; cannot add hospital")
    ref = db.collection(HOSPITALS_COLLECTION).document()
    ref.set(data)
    return ref.id


def list_reports() -> list[dict]:
    if not firebase_available or db is None:
        return []
    docs = (
        db.collection(REPORTS_COLLECTION)
        .order_by("created_at", direction=firestore.Query.DESCENDING)
        .stream()
    )
    return [{"id": doc.id, **doc.to_dict()} for doc in docs]


def add_report(area: str, message: str, reporter_name: str | None = None) -> dict:
    if not firebase_available or db is None:
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


def log_emergency(description: str, emergency_level: str, city: str) -> None:
    if not firebase_available or db is None:
        return
    db.collection(LOGS_COLLECTION).document().set(
        {
            "description": description,
            "emergency_level": emergency_level,
            "city": city,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )


def create_sos_record(data: dict) -> str:
    if not firebase_available or db is None:
        raise RuntimeError("Firebase/Firestore is unavailable; cannot persist SOS event")
    ref = db.collection(SOS_EVENTS_COLLECTION).document()
    ref.set(data)
    return ref.id


def update_sos_record(event_id: str, updates: dict) -> None:
    if not firebase_available or db is None:
        return
    try:
        db.collection(SOS_EVENTS_COLLECTION).document(event_id).update(updates)
    except Exception as exc:
        logger.warning("update_sos_record failed for %s: %s", event_id, exc)


def register_device(token: str) -> None:
    if not firebase_available or db is None:
        logger.warning("register_device: Firebase is unavailable.")
        return
    db.collection(DEVICES_COLLECTION).document(token).set(
        {"token": token, "registered_at": datetime.now(timezone.utc).isoformat()}
    )
    messaging.subscribe_to_topic([token], settings.firebase_alert_topic)


def send_topic_push(title: str, body: str, data: dict | None = None) -> str:
    if not firebase_available:
        raise RuntimeError("Firebase Cloud Messaging is unavailable")
    message = messaging.Message(
        notification=messaging.Notification(title=title, body=body),
        data={k: str(v) for k, v in (data or {}).items()},
        topic=settings.firebase_alert_topic,
    )
    return messaging.send(message)
