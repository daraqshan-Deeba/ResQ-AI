"""Supabase JWT verification and simple in-process rate limiting."""

from __future__ import annotations

import inspect
import logging
import time
from functools import wraps
from typing import Callable

import jwt
from flask import g, jsonify, request

from app.core.config import settings

logger = logging.getLogger("resq.auth")

_buckets: dict[str, list[float]] = {}
_jwks_client: jwt.PyJWKClient | None = None
_jwks_url: str = ""


def reset_rate_limit_buckets() -> None:
    _buckets.clear()


def reset_jwks_client() -> None:
    global _jwks_client, _jwks_url
    _jwks_client = None
    _jwks_url = ""


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


def _jwks() -> jwt.PyJWKClient:
    global _jwks_client, _jwks_url
    url = settings.supabase_url.rstrip("/") + "/auth/v1/.well-known/jwks.json"
    if _jwks_client is None or _jwks_url != url:
        _jwks_client = jwt.PyJWKClient(url, cache_keys=True)
        _jwks_url = url
    return _jwks_client


def decode_access_token(token: str) -> dict | None:
    """Verify a Supabase access token (legacy HS256 or current ES256 JWKS)."""
    token = (token or "").strip()
    if not token:
        return None
    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError:
        return None
    alg = str(header.get("alg") or "HS256")

    try:
        if alg == "HS256":
            secret = settings.supabase_jwt_secret.strip()
            if not secret:
                return None
            payload = jwt.decode(
                token,
                secret,
                algorithms=["HS256"],
                options={"verify_aud": False},
            )
        elif alg in {"ES256", "RS256"}:
            key = _jwks().get_signing_key_from_jwt(token)
            payload = jwt.decode(
                token,
                key.key,
                algorithms=[alg],
                options={"verify_aud": False},
            )
        else:
            logger.warning("Unsupported JWT alg %s", alg)
            return None
    except jwt.PyJWTError as exc:
        logger.warning("JWT verify failed (%s): %s", alg, type(exc).__name__)
        return None

    return payload if isinstance(payload, dict) else None


def require_write_auth(fn: Callable):
    def _authorize():
        header = request.headers.get("Authorization", "")
        token = header[7:].strip() if header.startswith("Bearer ") else ""
        payload = decode_access_token(token) if token else None
        if payload and payload.get("sub"):
            g.user_id = str(payload["sub"])
            return None
        if settings.api_auth_required:
            if not token:
                return jsonify({"detail": "Authentication required"}), 401
            if not settings.supabase_jwt_secret.strip() and not settings.supabase_url.strip():
                return jsonify({"detail": "Auth is not configured"}), 503
            return jsonify({"detail": "Invalid or expired token"}), 401
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
