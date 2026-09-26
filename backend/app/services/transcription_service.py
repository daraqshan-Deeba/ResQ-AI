"""
Audio transcription via Groq Whisper (OpenAI-compatible audio API).
"""

import logging
from typing import Optional

import httpx

from app.core.config import settings
from app.i18n.languages import language_map, whisper_code
from app.models.schemas import ServiceResult, TranscriptionResult

logger = logging.getLogger("resq.transcription")

GROQ_TRANSCRIPTIONS_URL = "https://api.groq.com/openai/v1/audio/transcriptions"

LANGUAGE_MAP = language_map()

MAX_AUDIO_BYTES = 25 * 1024 * 1024  # Groq limit for whisper-large-v3


def resolve_language_code(language: Optional[str]) -> Optional[str]:
    if not language:
        return None
    return whisper_code(language) or LANGUAGE_MAP.get(language.strip().lower())


async def transcribe_audio_safe(
    audio_bytes: bytes,
    filename: str,
    language: Optional[str] = None,
) -> ServiceResult[TranscriptionResult]:
    api_key = settings.groq_api_key
    if not api_key or not api_key.strip():
        return ServiceResult(
            available=False,
            error_type="service_disabled",
            detail="Transcription service is not configured.",
        )

    if not audio_bytes:
        return ServiceResult(
            available=False,
            error_type="parse_error",
            detail="No audio data received.",
        )

    if len(audio_bytes) > MAX_AUDIO_BYTES:
        return ServiceResult(
            available=False,
            error_type="parse_error",
            detail="Audio file is too large (max 25 MB).",
        )

    lang_code = resolve_language_code(language)
    form_data = {
        "model": settings.groq_whisper_model,
        "response_format": "json",
    }
    if lang_code:
        form_data["language"] = lang_code

    headers = {"Authorization": f"Bearer {api_key.strip()}"}
    files = {"file": (filename or "audio.webm", audio_bytes, "application/octet-stream")}

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                GROQ_TRANSCRIPTIONS_URL,
                headers=headers,
                files=files,
                data=form_data,
            )
            resp.raise_for_status()
            payload = resp.json()

        text = str(payload.get("text", "")).strip()
        if not text:
            return ServiceResult(
                available=False,
                error_type="parse_error",
                detail="Transcription returned empty text.",
            )

        return ServiceResult(
            available=True,
            data=TranscriptionResult(
                text=text,
                language=lang_code,
                model=settings.groq_whisper_model,
            ),
        )

    except httpx.TimeoutException:
        logger.warning("Timeout while connecting to Groq transcription API.")
        return ServiceResult(
            available=False,
            error_type="timeout",
            detail="Transcription service timed out.",
        )
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        detail = exc.response.text[:300]
        if status in (401, 403):
            error_type = "auth_error"
        elif status == 429:
            error_type = "rate_limited"
        elif status >= 500:
            error_type = "server_error"
        else:
            error_type = "server_error"
        logger.warning("Groq transcription HTTP %s: %s", status, detail)
        return ServiceResult(available=False, error_type=error_type, detail=detail)
    except httpx.RequestError as exc:
        logger.warning("Network error during transcription: %s", exc)
        return ServiceResult(
            available=False,
            error_type="network_error",
            detail="Could not reach transcription service.",
        )
    except (ValueError, KeyError, TypeError) as exc:
        logger.warning("Failed to parse transcription response: %s", exc)
        return ServiceResult(
            available=False,
            error_type="parse_error",
            detail="Invalid transcription response.",
        )
