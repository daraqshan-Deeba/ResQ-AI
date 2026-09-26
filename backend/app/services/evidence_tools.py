"""Optional Groq evidence tool loop — evidence fetch only."""

from __future__ import annotations

import json
import logging
from typing import Any

from app.core.config import settings
from app.services import database_service, maps_service, weather_service
from app.services.evidence_map import EVIDENCE_TOOL_NAMES, GROQ_EVIDENCE_TOOLS
from app.services.groq_service import call_groq_safe

logger = logging.getLogger("resq.evidence_tools")


def allowed_tool_names() -> tuple[str, ...]:
    return EVIDENCE_TOOL_NAMES


async def run_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    if name not in EVIDENCE_TOOL_NAMES:
        return {"error": "tool not allowed"}
    try:
        if name == "fetch_weather":
            res = await weather_service.get_weather_safe(float(arguments["lat"]), float(arguments["lon"]))
            if not res.available or not res.data:
                return {"ok": False, "status": res.error_type}
            return {"ok": True, "weather": res.data.model_dump()}
        if name == "fetch_hospitals":
            res = await maps_service.get_nearby_hospitals_safe(float(arguments["lat"]), float(arguments["lon"]))
            if not res.available:
                return {"ok": False, "status": res.error_type or "search_failed"}
            return {"ok": True, "hospitals": [h.model_dump() for h in (res.data or [])]}
        if name == "search_reports":
            query = str(arguments.get("query") or "")
            area = str(arguments.get("area") or "")
            matches = []
            for report in database_service.list_reports():
                blob = f"{report.get('area','')} {report.get('message','')}".lower()
                if query.lower() in blob or (area and area.lower() in blob):
                    matches.append(
                        {
                            "id": report.get("id"),
                            "area": report.get("area"),
                            "message": report.get("message"),
                            "verified": bool(report.get("verified")),
                        }
                    )
            return {"ok": True, "reports": matches[:5], "note": "Unverified community reports"}
    except Exception as exc:
        logger.warning("evidence tool %s failed: %s", name, exc)
        return {"ok": False, "error": type(exc).__name__}
    return {"error": "unknown tool"}


async def maybe_run_llm_evidence_tools(user_description: str) -> dict[str, Any] | None:
    if not getattr(settings, "llm_evidence_tools_enabled", False):
        return None
    messages = [
        {
            "role": "system",
            "content": (
                "You may only call fetch_weather, fetch_hospitals, or search_reports. "
                "Never decide severity, protocols, SOS, or phone numbers."
            ),
        },
        {"role": "user", "content": user_description[:500]},
    ]
    result = await call_groq_safe(messages, temperature=0.0, tools=GROQ_EVIDENCE_TOOLS)
    if not result.available:
        return None
    return {"raw": result.data}
