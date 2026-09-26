from flask import Blueprint, jsonify, request
from pydantic import ValidationError

from app.core.config import settings
from app.auth import rate_limit
from app.http_utils import parse_json, validation_error_response
from app.i18n.languages import normalize_language
from app.models.schemas import ChatRequest, ChatResponse
from app.services import groq_service
from app.services.agent_memory_service import agent_memory_service
from app.services.chat_intent import emergency_intent_reply

bp = Blueprint("chat", __name__, url_prefix="/api/chat")


@bp.post("")
@rate_limit(max_calls=30, window_sec=60)
async def chat():
    try:
        payload = parse_json(ChatRequest, request.get_json())
    except ValidationError as exc:
        return validation_error_response(exc)

    guarded = emergency_intent_reply(payload.message)
    if guarded:
        return jsonify(ChatResponse(reply=guarded, session_id=payload.session_id).model_dump())

    city = payload.city or settings.default_city
    history = [turn.model_dump() for turn in payload.history][-12:]
    session_id = payload.session_id
    actor_id = payload.actor_id or "resq-user"

    memory_context = None
    if session_id and agent_memory_service.available:
        memory_context = await agent_memory_service.build_memory_context(payload.message)

    reply = await groq_service.run_chat_reply(
        history,
        payload.message,
        city,
        memory_context=memory_context,
        language=normalize_language(payload.language),
    )

    if session_id and agent_memory_service.available:
        await agent_memory_service.record_session_turn(
            session_id=session_id,
            actor_id=actor_id,
            role="user",
            text=payload.message,
        )
        await agent_memory_service.record_session_turn(
            session_id=session_id,
            actor_id=actor_id,
            role="assistant",
            text=reply,
        )

    return jsonify(ChatResponse(reply=reply, session_id=session_id).model_dump())
