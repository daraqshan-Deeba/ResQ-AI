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

from datetime import datetime, timezone

import firebase_admin
from firebase_admin import credentials, firestore, messaging

from app.core.config import settings

_app = firebase_admin.initialize_app(
    credentials.Certificate(settings.firebase_credentials_path)
)
db = firestore.client()

SHELTERS_COLLECTION = "shelters"
REPORTS_COLLECTION = "community_reports"
LOGS_COLLECTION = "emergency_logs"
DEVICES_COLLECTION = "device_tokens"


# ---------- Shelters ----------
def list_shelters() -> list[dict]:
    docs = db.collection(SHELTERS_COLLECTION).stream()
    return [{"id": doc.id, **doc.to_dict()} for doc in docs]


def add_shelter(data: dict) -> str:
    ref = db.collection(SHELTERS_COLLECTION).document()
    ref.set(data)
    return ref.id


# ---------- Community reports ----------
def list_reports() -> list[dict]:
    docs = (
        db.collection(REPORTS_COLLECTION)
        .order_by("created_at", direction=firestore.Query.DESCENDING)
        .stream()
    )
    return [{"id": doc.id, **doc.to_dict()} for doc in docs]


def add_report(area: str, message: str, reporter_name: str | None = None) -> dict:
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
    db.collection(LOGS_COLLECTION).document().set(
        {
            "description": description,
            "emergency_level": emergency_level,
            "city": city,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )


# ---------- Device tokens + push notifications ----------
def register_device(token: str) -> None:
    """Save the token and subscribe it to the shared alert topic, so every
    registered device gets SOS/alert pushes without per-device targeting."""
    db.collection(DEVICES_COLLECTION).document(token).set(
        {"token": token, "registered_at": datetime.now(timezone.utc).isoformat()}
    )
    messaging.subscribe_to_topic([token], settings.firebase_alert_topic)


def send_topic_push(title: str, body: str, data: dict | None = None) -> str:
    message = messaging.Message(
        notification=messaging.Notification(title=title, body=body),
        data={k: str(v) for k, v in (data or {}).items()},
        topic=settings.firebase_alert_topic,
    )
    return messaging.send(message)
