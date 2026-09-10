from flask import Blueprint, jsonify

from app.services.report_ml_service import training_stats as report_stats
from app.services.triage_ml_service import training_stats as triage_stats

bp = Blueprint("ml", __name__, url_prefix="/api/ml")


@bp.get("/status")
def ml_status():
    return jsonify(
        {
            "triage_classifier": triage_stats(),
            "report_classifier": report_stats(),
        }
    )
