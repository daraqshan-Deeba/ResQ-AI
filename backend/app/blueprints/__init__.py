from app.blueprints.assessment import bp as assessment_bp
from app.blueprints.chat import bp as chat_bp
from app.blueprints.device import bp as device_bp
from app.blueprints.hospitals import bp as hospitals_bp
from app.blueprints.knowledge import bp as knowledge_bp
from app.blueprints.ml import bp as ml_bp
from app.blueprints.reports import bp as reports_bp
from app.blueprints.shelters import bp as shelters_bp
from app.blueprints.sos import bp as sos_bp
from app.blueprints.traffic import bp as traffic_bp
from app.blueprints.transcribe import bp as transcribe_bp
from app.blueprints.weather import bp as weather_bp

__all__ = [
    "assessment_bp",
    "chat_bp",
    "device_bp",
    "hospitals_bp",
    "knowledge_bp",
    "ml_bp",
    "reports_bp",
    "shelters_bp",
    "sos_bp",
    "traffic_bp",
    "transcribe_bp",
    "weather_bp",
]
