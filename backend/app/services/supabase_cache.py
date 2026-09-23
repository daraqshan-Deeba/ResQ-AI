"""In-process TTL cache for Supabase read queries.

Keeps hospitals / shelters / reports warm between requests so free-tier
Supabase is hit less often. Writes invalidate the matching key.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, TypeVar

from app.core.config import settings

T = TypeVar("T")


@dataclass
class _Entry:
    value: Any
    expires_at: float


_lock = threading.RLock()
_store: dict[str, _Entry] = {}

# Cache key constants
KEY_HOSPITALS = "supabase:hospitals"
KEY_SHELTERS = "supabase:shelters"
KEY_REPORTS = "supabase:reports"


def cache_enabled() -> bool:
    return bool(getattr(settings, "supabase_cache_enabled", True))


def _ttl_for(key: str) -> float:
    if key == KEY_HOSPITALS:
        return float(settings.supabase_cache_ttl_hospitals)
    if key == KEY_SHELTERS:
        return float(settings.supabase_cache_ttl_shelters)
    if key == KEY_REPORTS:
        return float(settings.supabase_cache_ttl_reports)
    return float(settings.supabase_cache_ttl_default)


def get(key: str) -> Any | None:
    if not cache_enabled():
        return None
    now = time.monotonic()
    with _lock:
        entry = _store.get(key)
        if entry is None:
            return None
        if entry.expires_at <= now:
            _store.pop(key, None)
            return None
        return entry.value


def set(key: str, value: Any, *, ttl_seconds: float | None = None) -> None:
    if not cache_enabled():
        return
    ttl = _ttl_for(key) if ttl_seconds is None else ttl_seconds
    with _lock:
        _store[key] = _Entry(value=value, expires_at=time.monotonic() + max(1.0, ttl))


def invalidate(*keys: str) -> None:
    with _lock:
        for key in keys:
            _store.pop(key, None)


def clear() -> None:
    with _lock:
        _store.clear()


def get_or_set(key: str, loader: Callable[[], T], *, ttl_seconds: float | None = None) -> T:
    cached = get(key)
    if cached is not None:
        return cached  # type: ignore[return-value]
    value = loader()
    set(key, value, ttl_seconds=ttl_seconds)
    return value


def stats() -> dict[str, Any]:
    now = time.monotonic()
    with _lock:
        live = {
            key: round(entry.expires_at - now, 1)
            for key, entry in _store.items()
            if entry.expires_at > now
        }
    return {
        "enabled": cache_enabled(),
        "entries": len(live),
        "keys": live,
        "ttl_seconds": {
            "hospitals": settings.supabase_cache_ttl_hospitals,
            "shelters": settings.supabase_cache_ttl_shelters,
            "reports": settings.supabase_cache_ttl_reports,
            "default": settings.supabase_cache_ttl_default,
        },
    }
