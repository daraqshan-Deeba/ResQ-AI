"""Smoke-test Redis Agent Memory using values from .env / ../.env."""

import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings
from app.services.agent_memory_service import agent_memory_service


async def main() -> None:
    if not settings.is_agent_memory_available:
        print(
            "Agent memory not configured. Set REDIS_AGENT_MEMORY_KEY, "
            "REDIS_AGENT_MEMORY_STORE_ID, and REDIS_AGENT_MEMORY_URL."
        )
        return

    session_id = f"verify-{int(time.time())}"
    actor_id = "verify-user"

    await agent_memory_service.record_session_turn(
        session_id=session_id,
        actor_id=actor_id,
        role="user",
        text="What is semantic memory?",
    )

    snippets = await agent_memory_service.search_long_term_context(
        "What is semantic memory?"
    )
    print("Long-term search snippets:", snippets or "(none yet)")
    print("Session recorded:", session_id)
    print("Agent memory OK")


if __name__ == "__main__":
    asyncio.run(main())
