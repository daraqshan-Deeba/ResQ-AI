from __future__ import annotations

from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
MODELS_DIR = DATA_DIR / "models"

TRIAGE_MODEL_PATH = MODELS_DIR / "triage_classifier.joblib"
TRIAGE_TRAINING_JSON = DATA_DIR / "triage_ml_training.json"

REPORT_MODEL_PATH = MODELS_DIR / "report_classifier.joblib"
REPORT_TRAINING_JSON = DATA_DIR / "report_ml_training.json"


def ensure_models_dir() -> Path:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    return MODELS_DIR
