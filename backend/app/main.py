from flask import Flask, jsonify
from flask_cors import CORS

from app.blueprints import (
    assessment_bp,
    chat_bp,
    device_bp,
    hospitals_bp,
    keepalive_bp,
    knowledge_bp,
    ml_bp,
    reports_bp,
    shelters_bp,
    sos_bp,
    traffic_bp,
    transcribe_bp,
    weather_bp,
)
from app.core.config import settings
# Importing this triggers firebase_admin.initialize_app(...) once, at startup.
from app.i18n.languages import language_catalog
from app.services import firebase_service, supabase_service  # noqa: F401


def create_app() -> Flask:
    app = Flask(__name__)

    CORS(
        app,
        resources={r"/*": {"origins": "*"}},
        supports_credentials=False,
        send_wildcard=True,
        always_send=True,
        allow_headers="*",
        expose_headers="*",
        methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
    )

    app.register_blueprint(assessment_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(weather_bp)
    app.register_blueprint(hospitals_bp)
    app.register_blueprint(shelters_bp)
    app.register_blueprint(keepalive_bp)
    app.register_blueprint(knowledge_bp)
    app.register_blueprint(ml_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(sos_bp)
    app.register_blueprint(traffic_bp)
    app.register_blueprint(transcribe_bp)
    app.register_blueprint(device_bp)

    @app.get("/health")
    def health():
        return jsonify(
            {
                "status": "ok",
                "groq_model": settings.groq_model,
                "groq_configured": settings.is_groq_available,
                "openweather_configured": bool(settings.openweather_api_key.strip()),
                "firebase_available": firebase_service.firebase_available,
            }
        )

    @app.get("/api/languages")
    def languages():
        return jsonify(language_catalog())

    return app


app = create_app()
