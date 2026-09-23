from flask import Blueprint, jsonify, request

from app.core.config import settings
from app.services.keepalive_service import run_keepalive

bp = Blueprint("keepalive", __name__, url_prefix="/api/cron")


def _authorized() -> bool:
    secret = (settings.keepalive_secret or settings.cron_secret or "").strip()
    if not secret:
        return False
    auth = request.headers.get("Authorization", "")
    return auth == f"Bearer {secret}"


@bp.get("/keepalive")
def keepalive():
    """Ping databases and cache — call from Vercel Cron or an external scheduler."""
    if not _authorized():
        return jsonify({"error": "unauthorized"}), 401

    return jsonify(run_keepalive())
