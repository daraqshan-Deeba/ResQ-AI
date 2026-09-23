"""Supabase Storage helpers for report images and emergency documents."""

from __future__ import annotations

import logging
import mimetypes
import uuid
from pathlib import PurePosixPath
from typing import Optional

from app.core.config import settings
from app.services import supabase_service

logger = logging.getLogger("resq.storage")

ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
    "text/plain",
    "text/markdown",
    "application/pdf",
}


def storage_available() -> bool:
    return supabase_service.supabase_available


def _bucket() -> str:
    return settings.supabase_storage_bucket.strip() or "resq-assets"


def _guess_mime(filename: str, fallback: str = "application/octet-stream") -> str:
    guessed, _ = mimetypes.guess_type(filename)
    return guessed or fallback


def _public_url(storage_path: str) -> str:
    base = settings.supabase_url.rstrip("/")
    return f"{base}/storage/v1/object/public/{_bucket()}/{storage_path}"


def upload_bytes(
    data: bytes,
    filename: str,
    *,
    folder: str = "uploads",
    content_type: Optional[str] = None,
) -> dict:
    """Upload raw bytes to Supabase Storage and return path + public URL."""
    if not supabase_service.supabase_available or supabase_service.client is None:
        raise RuntimeError("Supabase Storage is unavailable")

    if len(data) > settings.supabase_max_upload_bytes:
        raise ValueError(
            f"File exceeds maximum size of {settings.supabase_max_upload_bytes} bytes"
        )

    mime = content_type or _guess_mime(filename)
    if mime not in ALLOWED_MIME_TYPES:
        raise ValueError(f"Unsupported file type: {mime}")

    safe_name = PurePosixPath(filename).name.replace(" ", "_") or "upload.bin"
    storage_path = f"{folder}/{uuid.uuid4().hex}_{safe_name}"

    # cacheControl (seconds) enables CDN/browser caching for public objects
    supabase_service.client.storage.from_(_bucket()).upload(
        path=storage_path,
        file=data,
        file_options={
            "content-type": mime,
            "upsert": "false",
            "cacheControl": "3600",
        },
    )

    return {
        "storage_path": storage_path,
        "storage_url": _public_url(storage_path),
        "mime_type": mime,
        "size_bytes": len(data),
    }


def extract_text_content(data: bytes, mime_type: str, filename: str) -> str:
    """Best-effort text extraction for embedding (plain text / markdown only)."""
    if mime_type in {"text/plain", "text/markdown"}:
        try:
            return data.decode("utf-8").strip()
        except UnicodeDecodeError:
            return data.decode("utf-8", errors="replace").strip()
    return ""
