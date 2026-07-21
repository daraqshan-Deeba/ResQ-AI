from fastapi import APIRouter

from app.core.config import settings
from app.models.schemas import ChatRequest, ChatResponse
from app.services import groq_service

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def chat(payload: ChatRequest):
    city = payload.city or settings.default_city
    history = [turn.model_dump() for turn in payload.history]
    reply = await groq_service.run_chat_reply(history, payload.message, city)
    return ChatResponse(reply=reply)
