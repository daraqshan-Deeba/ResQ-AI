"""Redis Agent Memory — session turns + semantic long-term recall for the chat assistant."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)

try:
    from redis_agent_memory import AgentMemory, models
except ImportError:  # pragma: no cover - optional at install time
    AgentMemory = None  # type: ignore[misc, assignment]
    models = None  # type: ignore[misc, assignment]


def _now() -> datetime:
    return datetime.now(timezone.utc)


class AgentMemoryService:
    def __init__(self) -> None:
        self._client: Any | None = None

    @property
    def available(self) -> bool:
        return (
            AgentMemory is not None
            and settings.is_agent_memory_available
        )

    def _client_instance(self) -> Any:
        if not self.available:
            raise RuntimeError("Redis Agent Memory is not configured")
        if self._client is None:
            self._client = AgentMemory(
                settings.redis_agent_memory_url,
                store_id=settings.redis_agent_memory_store_id,
                api_key=settings.redis_agent_memory_api_key,
            )
        return self._client

    async def search_long_term_context(self, query: str, limit: int = 3) -> list[str]:
        if not self.available or not query.strip():
            return []

        try:
            client = self._client_instance()
            response = await client.search_long_term_memory_async(
                request={"text": query, "limit": limit},
            )
        except Exception as exc:
            logger.warning("Agent memory search failed: %s", exc)
            return []

        snippets: list[str] = []
        for item in getattr(response, "items", None) or []:
            text = getattr(item, "text", None)
            if text:
                snippets.append(str(text))
        return snippets

    async def record_session_turn(
        self,
        *,
        session_id: str,
        actor_id: str,
        role: str,
        text: str,
    ) -> None:
        if not self.available or not session_id or not text.strip():
            return

        message_role = (
            models.MessageRole.USER
            if role == "user"
            else models.MessageRole.ASSISTANT
        )

        try:
            client = self._client_instance()
            await client.add_session_event_async(
                session_id=session_id,
                actor_id=actor_id,
                role=message_role,
                content=[{"text": text}],
                created_at=_now(),
            )
        except Exception as exc:
            logger.warning("Agent memory session write failed: %s", exc)

    async def build_memory_context(self, query: str) -> str:
        snippets = await self.search_long_term_context(query)
        if not snippets:
            return ""
        joined = "\n".join(f"- {s}" for s in snippets)
        return (
            "Relevant facts from long-term memory (use if helpful, do not invent beyond this):\n"
            f"{joined}"
        )


agent_memory_service = AgentMemoryService()
