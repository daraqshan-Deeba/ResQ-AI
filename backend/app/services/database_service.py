"""
Unified persistence facade — prefers Supabase when configured, falls back to Firebase.

Push notifications (FCM) still require Firebase credentials.
"""

from __future__ import annotations

from app.services import firebase_service, supabase_service


def database_available() -> bool:
    return supabase_service.supabase_available or firebase_service.firebase_available


def push_available() -> bool:
    return firebase_service.firebase_available


def list_shelters() -> list[dict]:
    if supabase_service.supabase_available:
        return supabase_service.list_shelters()
    return firebase_service.list_shelters()


def add_shelter(data: dict) -> str:
    if supabase_service.supabase_available:
        return supabase_service.add_shelter(data)
    return firebase_service.add_shelter(data)


def list_reports() -> list[dict]:
    if supabase_service.supabase_available:
        return supabase_service.list_reports()
    return firebase_service.list_reports()


def add_report(
    area: str,
    message: str,
    reporter_name: str | None = None,
    *,
    attachment_path: str | None = None,
    attachment_url: str | None = None,
    attachment_mime: str | None = None,
) -> dict:
    if supabase_service.supabase_available:
        return supabase_service.add_report(
            area,
            message,
            reporter_name,
            attachment_path=attachment_path,
            attachment_url=attachment_url,
            attachment_mime=attachment_mime,
        )
    return firebase_service.add_report(area, message, reporter_name)


def log_emergency(description: str, emergency_level: str, city: str) -> None:
    if supabase_service.supabase_available:
        supabase_service.log_emergency(description, emergency_level, city)
        return
    firebase_service.log_emergency(description, emergency_level, city)


def create_sos_record(data: dict) -> str:
    if supabase_service.supabase_available:
        return supabase_service.create_sos_record(data)
    return firebase_service.create_sos_record(data)


def update_sos_record(event_id: str, updates: dict) -> None:
    if supabase_service.supabase_available:
        supabase_service.update_sos_record(event_id, updates)
        return
    firebase_service.update_sos_record(event_id, updates)


def register_device(token: str, *, user_id: str | None = None) -> None:
    if supabase_service.supabase_available:
        supabase_service.register_device(token, user_id=user_id)
    if firebase_service.firebase_available:
        firebase_service.register_device(token, user_id=user_id)
    elif not supabase_service.supabase_available:
        firebase_service.register_device(token, user_id=user_id)


def list_device_tokens(*, user_id: str | None = None) -> list[str]:
    tokens: list[str] = []
    if supabase_service.supabase_available:
        tokens.extend(supabase_service.list_device_tokens(user_id=user_id))
    if firebase_service.firebase_available:
        tokens.extend(firebase_service.list_device_tokens(user_id=user_id))
    # de-dupe while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for token in tokens:
        if token not in seen:
            seen.add(token)
            unique.append(token)
    return unique


def send_device_push(
    tokens: list[str],
    title: str,
    body: str,
    data: dict | None = None,
) -> str:
    return firebase_service.send_device_push(tokens, title, body, data)


def send_topic_push(title: str, body: str, data: dict | None = None) -> str:
    """Deprecated: public topic must not be used for SOS."""
    return firebase_service.send_topic_push(title, body, data)


def hospitals_directory_available() -> bool:
    """True when a hospital directory backend is configured (Supabase preferred)."""
    return supabase_service.supabase_available or firebase_service.firebase_available


def list_hospitals() -> list[dict]:
    if supabase_service.supabase_available:
        return supabase_service.list_hospitals()
    return firebase_service.list_hospitals()


def add_hospital(data: dict) -> str:
    if supabase_service.supabase_available:
        return supabase_service.add_hospital(data)
    return firebase_service.add_hospital(data)


def add_hospitals_batch(rows: list[dict], *, chunk_size: int = 200) -> int:
    if supabase_service.supabase_available:
        return supabase_service.add_hospitals_batch(rows, chunk_size=chunk_size)
    added = 0
    for row in rows:
        firebase_service.add_hospital(row)
        added += 1
    return added


def clear_hospitals() -> int:
    if supabase_service.supabase_available:
        return supabase_service.clear_hospitals()
    if not firebase_service.firebase_available or firebase_service.db is None:
        return 0
    deleted = 0
    for doc in firebase_service.db.collection("hospitals").stream():
        doc.reference.delete()
        deleted += 1
    return deleted


def count_hospitals() -> int:
    if supabase_service.supabase_available:
        return supabase_service.count_hospitals()
    return len(firebase_service.list_hospitals())
