"""Lightweight pings to keep Supabase, Redis agent memory, and Firebase warm."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.core.config import settings
from app.services import firebase_service, supabase_service
from app.services.agent_memory_service import agent_memory_service

logger = logging.getLogger("resq.keepalive")


def ping_supabase() -> dict[str, Any]:
    if not supabase_service.supabase_available or supabase_service.client is None:
        return {
            "ok": False,
            "configured": False,
            "detail": supabase_service.supabase_error_detail or "not configured",
        }

    try:
        response = (
            supabase_service.client.table("shelters")
            .select("id", count="exact")
            .limit(1)
            .execute()
        )
        count = getattr(response, "count", None)
        return {"ok": True, "configured": True, "shelters_count": count}
    except Exception as exc:
        logger.warning("Supabase keepalive failed: %s", exc)
        return {"ok": False, "configured": True, "detail": type(exc).__name__}


async def _ping_redis_async() -> dict[str, Any]:
    if not agent_memory_service.available:
        return {"ok": False, "configured": False, "detail": "not configured"}

    try:
        await agent_memory_service.search_long_term_context("keepalive", limit=1)
        return {"ok": True, "configured": True}
    except Exception as exc:
        logger.warning("Redis agent memory keepalive failed: %s", exc)
        return {"ok": False, "configured": True, "detail": type(exc).__name__}


def ping_redis() -> dict[str, Any]:
    try:
        return asyncio.run(_ping_redis_async())
    except RuntimeError:
        # Nested event loop (e.g. inside an async test) — run in a fresh loop.
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(_ping_redis_async())
        finally:
            loop.close()


def ping_firebase() -> dict[str, Any]:
    return {
        "ok": firebase_service.firebase_available,
        "configured": bool(
            settings.firebase_project_id.strip()
            or settings.firebase_private_key.strip()
        ),
        "detail": firebase_service.firebase_error_detail,
    }


def run_keepalive() -> dict[str, Any]:
    checks = {
        "supabase": ping_supabase(),
        "redis_agent_memory": ping_redis(),
        "firebase": ping_firebase(),
    }
    configured = [name for name, result in checks.items() if result.get("configured")]
    healthy = [name for name, result in checks.items() if result.get("ok")]
    return {
        "status": "ok" if not configured or len(healthy) == len(configured) else "degraded",
        "configured": configured,
        "healthy": healthy,
        "checks": checks,
    }
