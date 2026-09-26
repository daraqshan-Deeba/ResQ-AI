"""TTL cache for Supabase read queries.

Uses Redis Cloud when REDIS_URL is set, plus a small in-process L1 so a single
process does not round-trip Redis on every hospital lookup. Writes invalidate
both layers. Redis failures fall back to memory only.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, TypeVar

from app.core.config import settings

T = TypeVar("T")

logger = logging.getLogger("resq.cache")

_KEY_PREFIX = "resq:cache:"

KEY_HOSPITALS = "supabase:hospitals"
KEY_SHELTERS = "supabase:shelters"
KEY_REPORTS = "supabase:reports"


@dataclass
class _Entry:
    value: Any
    expires_at: float


_lock = threading.RLock()
_store: dict[str, _Entry] = {}
_redis_client: Any = None
_redis_ready: bool | None = None


def cache_enabled() -> bool:
    return bool(getattr(settings, "supabase_cache_enabled", True))


def reset_clients() -> None:
    global _redis_client, _redis_ready
    with _lock:
        _redis_client = None
        _redis_ready = None
        _store.clear()


def _ttl_for(key: str) -> float:
    if key == KEY_HOSPITALS:
        return float(settings.supabase_cache_ttl_hospitals)
    if key == KEY_SHELTERS:
        return float(settings.supabase_cache_ttl_shelters)
    if key == KEY_REPORTS:
        return float(settings.supabase_cache_ttl_reports)
    return float(settings.supabase_cache_ttl_default)


def _redis_key(key: str) -> str:
    return f"{_KEY_PREFIX}{key}"


def _connect_redis():
    import redis

    url = (settings.redis_url or "").strip()
    if not url:
        return None
    candidates = [url]
    if url.startswith("redis://"):
        candidates.append("rediss://" + url[len("redis://") :])
    last_error: Exception | None = None
    for candidate in candidates:
        try:
            client = redis.Redis.from_url(
                candidate,
                socket_connect_timeout=3,
                socket_timeout=5,
                decode_responses=True,
            )
            client.ping()
            logger.info("Redis cache connected.")
            return client
        except Exception as exc:
            last_error = exc
            continue
    logger.warning("Redis cache unavailable (%s). Using in-process cache.", type(last_error).__name__)
    return None


def _redis():
    global _redis_client, _redis_ready
    if _redis_ready is False:
        return None
    if _redis_client is not None:
        return _redis_client
    with _lock:
        if _redis_ready is False:
            return None
        if _redis_client is not None:
            return _redis_client
        client = _connect_redis()
        _redis_client = client
        _redis_ready = client is not None
        return _redis_client


def redis_available() -> bool:
    return _redis() is not None


def ping_redis_cache() -> dict[str, Any]:
    if not (settings.redis_url or "").strip():
        return {"ok": False, "configured": False, "detail": "REDIS_URL not set"}
    client = _redis()
    if client is None:
        return {"ok": False, "configured": True, "detail": "connection failed"}
    try:
        client.ping()
        return {"ok": True, "configured": True, "backend": "redis"}
    except Exception as exc:
        return {"ok": False, "configured": True, "detail": type(exc).__name__}


def _memory_get(key: str) -> Any | None:
    now = time.monotonic()
    with _lock:
        entry = _store.get(key)
        if entry is None:
            return None
        if entry.expires_at <= now:
            _store.pop(key, None)
            return None
        return entry.value


def _memory_set(key: str, value: Any, ttl: float) -> None:
    with _lock:
        _store[key] = _Entry(value=value, expires_at=time.monotonic() + max(1.0, ttl))


def _memory_invalidate(keys: tuple[str, ...]) -> None:
    with _lock:
        for key in keys:
            _store.pop(key, None)


def get(key: str) -> Any | None:
    if not cache_enabled():
        return None
    local = _memory_get(key)
    if local is not None:
        return local
    client = _redis()
    if client is None:
        return None
    try:
        raw = client.get(_redis_key(key))
        if not raw:
            return None
        value = json.loads(raw)
        _memory_set(key, value, _ttl_for(key))
        return value
    except Exception as exc:
        logger.warning("Redis cache get failed (%s).", type(exc).__name__)
        return None


def set(key: str, value: Any, *, ttl_seconds: float | None = None) -> None:
    if not cache_enabled():
        return
    ttl = _ttl_for(key) if ttl_seconds is None else ttl_seconds
    _memory_set(key, value, ttl)
    client = _redis()
    if client is None:
        return
    try:
        client.setex(_redis_key(key), int(max(1.0, ttl)), json.dumps(value, default=str))
    except Exception as exc:
        logger.warning("Redis cache set failed (%s).", type(exc).__name__)


def invalidate(*keys: str) -> None:
    _memory_invalidate(keys)
    client = _redis()
    if client is None:
        return
    try:
        if keys:
            client.delete(*(_redis_key(key) for key in keys))
    except Exception as exc:
        logger.warning("Redis cache invalidate failed (%s).", type(exc).__name__)


def clear() -> None:
    with _lock:
        _store.clear()
    client = _redis()
    if client is None:
        return
    try:
        found = list(client.scan_iter(match=f"{_KEY_PREFIX}*", count=100))
        if found:
            client.delete(*found)
    except Exception as exc:
        logger.warning("Redis cache clear failed (%s).", type(exc).__name__)


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
        "backend": "redis" if redis_available() else "memory",
        "redis_configured": bool((settings.redis_url or "").strip()),
        "entries": len(live),
        "keys": live,
        "ttl_seconds": {
            "hospitals": settings.supabase_cache_ttl_hospitals,
            "shelters": settings.supabase_cache_ttl_shelters,
            "reports": settings.supabase_cache_ttl_reports,
            "default": settings.supabase_cache_ttl_default,
        },
    }
