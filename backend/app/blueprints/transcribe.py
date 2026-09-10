from flask import Blueprint, jsonify, request

from app.services import transcription_service

bp = Blueprint("transcribe", __name__, url_prefix="/api/transcribe")

ALLOWED_MIME_PREFIXES = ("audio/", "video/webm", "application/octet-stream")


@bp.post("")
async def transcribe_audio():
    upload = request.files.get("audio") or request.files.get("file")
    if upload is None:
        return jsonify({"detail": "Missing audio file (field: audio or file)."}), 400

    mime = (upload.mimetype or "").lower()
    if mime and not any(mime.startswith(p) for p in ALLOWED_MIME_PREFIXES):
        return jsonify({"detail": f"Unsupported content type: {mime}"}), 400

    audio_bytes = upload.read()
    language = request.form.get("language") or request.args.get("language")

    result = await transcription_service.transcribe_audio_safe(
        audio_bytes=audio_bytes,
        filename=upload.filename or "audio.webm",
        language=language,
    )

    if result.available and result.data:
        return jsonify(result.data.model_dump())

    status = 503
    if result.error_type == "parse_error":
        status = 400
    elif result.error_type == "auth_error":
        status = 502

    return jsonify(
        {
            "detail": result.detail or "Transcription service unavailable.",
            "error_type": result.error_type,
        }
    ), status
