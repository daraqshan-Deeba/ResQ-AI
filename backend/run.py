import logging
import os

from app.core.config import settings
from app.main import app
from app.services import firebase_service

logger = logging.getLogger("resq.startup")

if __name__ == "__main__":
    # Disable the file watcher: fastembed downloads to cache during requests and
    # triggers a reload that crashes the dev server on Windows (WinError 10038).
    os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
    logging.basicConfig(level=logging.INFO)
    logger.info("Groq model: %s (configured: %s)", settings.groq_model, settings.is_groq_available)
    logger.info(
        "OpenWeather configured: %s",
        bool(settings.openweather_api_key and settings.openweather_api_key.strip()),
    )
    logger.info(
        "Firebase available: %s%s",
        firebase_service.firebase_available,
        f" ({firebase_service.firebase_error_detail})" if firebase_service.firebase_error_detail else "",
    )
    logger.info("Redis cache configured: %s", settings.is_redis_cache_available)
    # Default 8001: port 8000 is often left occupied by stale Flask processes on Windows.
    port = int(os.environ.get("PORT", "8001"))
    try:
        app.run(host="0.0.0.0", port=port, debug=True, use_reloader=False)
    except OSError as exc:
        logger.error(
            "Could not bind to port %s (%s). Another stale backend may still be running — "
            "stop all python run.py processes and try again.",
            port,
            exc,
        )
        raise