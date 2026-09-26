"""Supabase JWT verification and simple in-process rate limiting."""

from __future__ import annotations

import inspect
import time
from functools import wraps
from typing import Callable

import jwt
from flask import g, jsonify, request

from app.core.config import settings

_buckets: dict[str, list[float]] = {}


def reset_rate_limit_buckets() -> None:
    _buckets.clear()


def _client_key() -> str:
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr or "unknown"


def _rate_limited_response():
    return jsonify({"detail": "Too many requests. Call 112 if this is an emergency."}), 429


def _bump_or_block(fn_name: str, max_calls: int, window_sec: float):
    key = f"{fn_name}:{_client_key()}"
    now = time.monotonic()
    stamps = [t for t in _buckets.get(key, []) if now - t < window_sec]
    if len(stamps) >= max_calls:
        return True
    stamps.append(now)
    _buckets[key] = stamps
    return False


def rate_limit(max_calls: int = 20, window_sec: float = 60.0):
    def decorator(fn: Callable):
        if inspect.iscoroutinefunction(fn):
            @wraps(fn)
            async def async_wrapped(*args, **kwargs):
                if _bump_or_block(fn.__name__, max_calls, window_sec):
                    return _rate_limited_response()
                return await fn(*args, **kwargs)

            return async_wrapped

        @wraps(fn)
        def wrapped(*args, **kwargs):
            if _bump_or_block(fn.__name__, max_calls, window_sec):
                return _rate_limited_response()
            return fn(*args, **kwargs)

        return wrapped

    return decorator


def current_user_id() -> str | None:
    return getattr(g, "user_id", None)


def require_write_auth(fn: Callable):
    def _authorize():
        if not settings.api_auth_required:
            return None
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return jsonify({"detail": "Authentication required"}), 401
        token = header[7:].strip()
        secret = settings.supabase_jwt_secret.strip()
        if not secret:
            return jsonify({"detail": "Auth is not configured"}), 503
        try:
            payload = jwt.decode(
                token,
                secret,
                algorithms=["HS256"],
                options={"verify_aud": False},
            )
        except jwt.PyJWTError:
            return jsonify({"detail": "Invalid or expired token"}), 401
        g.user_id = payload.get("sub")
        return None

    if inspect.iscoroutinefunction(fn):
        @wraps(fn)
        async def async_wrapped(*args, **kwargs):
            blocked = _authorize()
            if blocked is not None:
                return blocked
            return await fn(*args, **kwargs)

        return async_wrapped

    @wraps(fn)
    def wrapped(*args, **kwargs):
        blocked = _authorize()
        if blocked is not None:
            return blocked
        return fn(*args, **kwargs)

    return wrapped
