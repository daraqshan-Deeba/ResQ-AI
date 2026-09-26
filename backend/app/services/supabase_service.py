"""Supabase Postgres persistence for shelters, reports, SOS events, and device tokens."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from app.core.config import settings
from app.services import supabase_cache

logger = logging.getLogger("resq.supabase")

try:
    from supabase import Client, create_client
except ImportError:  # pragma: no cover
    Client = Any  # type: ignore[misc, assignment]
    create_client = None  # type: ignore[misc, assignment]

client: Optional[Client] = None
supabase_available: bool = False
supabase_error_detail: Optional[str] = None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_supabase() -> None:
    global client, supabase_available, supabase_error_detail

    if create_client is None:
        supabase_available = False
        supabase_error_detail = "supabase package not installed"
        return

    url = settings.supabase_url.strip()
    key = settings.supabase_service_role_key.strip()
    if not url or not key:
        supabase_available = False
        supabase_error_detail = "Supabase URL or service role key not configured"
        logger.info("Supabase not configured — using Firebase fallback for persistence.")
        return

    try:
        client = create_client(url, key)
        supabase_available = True
        supabase_error_detail = None
        logger.info("Supabase client initialized.")
    except Exception as exc:
        client = None
        supabase_available = False
        supabase_error_detail = f"Supabase initialization failed: {type(exc).__name__}"
        logger.warning("Failed to initialize Supabase (%s).", type(exc).__name__)


init_supabase()


def _table(name: str):
    if not supabase_available or client is None:
        raise RuntimeError("Supabase is unavailable")
    return client.table(name)


def list_shelters() -> list[dict]:
    if not supabase_available:
        return []
    cached = supabase_cache.get(supabase_cache.KEY_SHELTERS)
    if cached is not None:
        return cached
    try:
        response = _table("shelters").select("*").execute()
        rows = response.data or []
        result = [
            {
                "id": str(row["id"]),
                "name": row["name"],
                "address": row.get("address"),
                "lat": row.get("lat"),
                "lon": row.get("lon"),
                "capacity": row.get("capacity", 0),
                "occupied": row.get("occupied", 0),
                "source": "supabase",
            }
            for row in rows
        ]
        supabase_cache.set(supabase_cache.KEY_SHELTERS, result)
        return result
    except Exception as exc:
        logger.warning("list_shelters failed: %s", exc)
        return []


def add_shelter(data: dict) -> str:
    payload = {
        "name": data["name"],
        "address": data.get("address"),
        "lat": data.get("lat"),
        "lon": data.get("lon"),
        "capacity": data.get("capacity", 0),
        "occupied": data.get("occupied", 0),
    }
    response = _table("shelters").insert(payload).execute()
    if not response.data:
        raise RuntimeError("Supabase insert returned no data for shelter")
    supabase_cache.invalidate(supabase_cache.KEY_SHELTERS)
    return str(response.data[0]["id"])


def list_reports() -> list[dict]:
    if not supabase_available:
        return []
    cached = supabase_cache.get(supabase_cache.KEY_REPORTS)
    if cached is not None:
        return cached
    try:
        response = (
            _table("community_reports")
            .select("*")
            .order("created_at", desc=True)
            .execute()
        )
        rows = response.data or []
        result = [_format_report(row) for row in rows]
        supabase_cache.set(supabase_cache.KEY_REPORTS, result)
        return result
    except Exception as exc:
        logger.warning("list_reports failed: %s", exc)
        return []


def add_report(
    area: str,
    message: str,
    reporter_name: str | None = None,
    *,
    user_id: str | None = None,
    attachment_path: str | None = None,
    attachment_url: str | None = None,
    attachment_mime: str | None = None,
    lat: float | None = None,
    lon: float | None = None,
) -> dict:
    payload = {
        "area": area,
        "message": message,
        "reporter_name": reporter_name,
        "verified": False,
        "created_at": _now_iso(),
        "attachment_path": attachment_path,
        "attachment_url": attachment_url,
        "attachment_mime": attachment_mime,
    }
    if user_id:
        payload["user_id"] = user_id
    if lat is not None and lon is not None:
        payload["lat"] = lat
        payload["lon"] = lon
    response = _table("community_reports").insert(payload).execute()
    if not response.data:
        raise RuntimeError("Supabase insert returned no data for report")
    supabase_cache.invalidate(supabase_cache.KEY_REPORTS)
    row = response.data[0]
    return _format_report(row)


def _format_report(row: dict) -> dict:
    return {
        "id": str(row["id"]),
        "area": row["area"],
        "message": row["message"],
        "verified": row.get("verified", False),
        "created_at": row["created_at"],
        "lat": row.get("lat"),
        "lon": row.get("lon"),
        "attachment_url": row.get("attachment_url"),
        "attachment_mime": row.get("attachment_mime"),
    }


def log_emergency(
    description: str,
    emergency_level: str,
    city: str,
    *,
    user_id: str | None = None,
) -> None:
    if not supabase_available:
        return
    try:
        row = {
            "description": description,
            "emergency_level": emergency_level,
            "city": city,
            "created_at": _now_iso(),
        }
        if user_id:
            row["user_id"] = user_id
        _table("emergency_logs").insert(row).execute()
    except Exception as exc:
        logger.warning("log_emergency failed: %s", exc)


def create_sos_record(data: dict) -> str:
    payload = {
        "latitude": data["latitude"],
        "longitude": data["longitude"],
        "situation": data.get("situation"),
        "notification_status": data.get("notification_status", "pending_notification"),
        "message_id": data.get("message_id"),
        "error_detail": data.get("error_detail"),
        "created_at": data.get("created_at", _now_iso()),
        "updated_at": data.get("updated_at", _now_iso()),
    }
    if data.get("user_id"):
        payload["user_id"] = data["user_id"]
    response = _table("sos_events").insert(payload).execute()
    if not response.data:
        raise RuntimeError("Supabase insert returned no data for SOS event")
    return str(response.data[0]["id"])


def update_sos_record(event_id: str, updates: dict) -> None:
    if not supabase_available:
        return
    try:
        payload = dict(updates)
        payload.setdefault("updated_at", _now_iso())
        _table("sos_events").update(payload).eq("id", event_id).execute()
    except Exception as exc:
        logger.warning("update_sos_record failed for %s: %s", event_id, exc)


def register_device(token: str, *, user_id: str | None = None) -> None:
    if not supabase_available:
        return
    try:
        row = {"token": token, "registered_at": _now_iso()}
        if user_id:
            row["user_id"] = user_id
        _table("device_tokens").upsert(row).execute()
    except Exception as exc:
        logger.warning("register_device failed: %s", exc)


def list_device_tokens(*, user_id: str | None = None) -> list[str]:
    if not supabase_available or not user_id:
        return []
    try:
        response = _table("device_tokens").select("token").eq("user_id", user_id).execute()
        return [row["token"] for row in (response.data or []) if row.get("token")]
    except Exception as exc:
        logger.warning("list_device_tokens failed: %s", exc)
        return []


_HOSPITAL_COLUMNS = frozenset(
    {
        "name",
        "address",
        "lat",
        "lon",
        "phone",
        "facility_type",
        "district",
        "source",
        "source_file",
        "ward",
        "circle",
        "zone",
        "hod",
        "object_id",
        "osm_id",
        "osm_type",
    }
)


def _format_hospital(row: dict) -> dict:
    return {
        "id": str(row["id"]),
        "name": row.get("name", "Hospital"),
        "address": row.get("address"),
        "lat": row.get("lat"),
        "lon": row.get("lon"),
        "phone": row.get("phone"),
        "facility_type": row.get("facility_type"),
        "district": row.get("district"),
        "source": row.get("source", "supabase"),
        "source_file": row.get("source_file"),
        "ward": row.get("ward"),
        "circle": row.get("circle"),
        "zone": row.get("zone"),
    }


def list_hospitals() -> list[dict]:
    if not supabase_available:
        return []
    cached = supabase_cache.get(supabase_cache.KEY_HOSPITALS)
    if cached is not None:
        return cached
    try:
        rows: list[dict] = []
        page_size = 1000
        offset = 0
        while True:
            response = (
                _table("hospitals")
                .select("*")
                .range(offset, offset + page_size - 1)
                .execute()
            )
            batch = response.data or []
            rows.extend(_format_hospital(row) for row in batch)
            if len(batch) < page_size:
                break
            offset += page_size
        supabase_cache.set(supabase_cache.KEY_HOSPITALS, rows)
        return rows
    except Exception as exc:
        logger.warning("list_hospitals failed: %s", exc)
        return []


def _hospital_payload(data: dict) -> dict:
    payload = {key: data[key] for key in _HOSPITAL_COLUMNS if key in data and data[key] is not None}
    payload.setdefault("source", "supabase")
    if "name" not in payload or "lat" not in payload or "lon" not in payload:
        raise ValueError("Hospital requires name, lat, and lon")
    return payload


def add_hospital(data: dict) -> str:
    response = _table("hospitals").insert(_hospital_payload(data)).execute()
    if not response.data:
        raise RuntimeError("Supabase insert returned no data for hospital")
    supabase_cache.invalidate(supabase_cache.KEY_HOSPITALS)
    return str(response.data[0]["id"])


def add_hospitals_batch(rows: list[dict], *, chunk_size: int = 200) -> int:
    """Bulk-insert hospitals in chunks. Skips rows that violate the dedupe unique index."""
    if not supabase_available or not rows:
        return 0

    inserted = 0
    for start in range(0, len(rows), chunk_size):
        chunk = [_hospital_payload(row) for row in rows[start : start + chunk_size]]
        try:
            response = _table("hospitals").insert(chunk).execute()
            inserted += len(response.data or chunk)
        except Exception as exc:
            if "duplicate" not in str(exc).lower() and "unique" not in str(exc).lower():
                logger.warning("add_hospitals_batch chunk failed: %s", exc)
            for row in chunk:
                try:
                    _table("hospitals").insert(row).execute()
                    inserted += 1
                except Exception:
                    continue
    if inserted:
        supabase_cache.invalidate(supabase_cache.KEY_HOSPITALS)
    return inserted


def clear_hospitals() -> int:
    if not supabase_available:
        return 0
    try:
        count = count_hospitals()
        if count == 0:
            return 0
        # Delete all rows (neq filter is required when no id is specified).
        _table("hospitals").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
        supabase_cache.invalidate(supabase_cache.KEY_HOSPITALS)
        return count
    except Exception as exc:
        logger.warning("clear_hospitals failed: %s", exc)
        return 0


def count_hospitals() -> int:
    if not supabase_available or client is None:
        return 0
    cached = supabase_cache.get(supabase_cache.KEY_HOSPITALS)
    if isinstance(cached, list):
        return len(cached)
    try:
        response = client.table("hospitals").select("id", count="exact").execute()
        return response.count or len(response.data or [])
    except Exception as exc:
        logger.warning("count_hospitals failed: %s", exc)
        return 0
