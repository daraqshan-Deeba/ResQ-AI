from __future__ import annotations

from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
MODELS_DIR = DATA_DIR / "models"

TRIAGE_MODEL_PATH = MODELS_DIR / "triage_classifier.joblib"
TRIAGE_TRAINING_JSON = DATA_DIR / "triage_ml_training.json"

REPORT_MODEL_PATH = MODELS_DIR / "report_classifier.joblib"
REPORT_TRAINING_JSON = DATA_DIR / "report_ml_training.json"

SYNTHETIC_DIR = DATA_DIR / "synthetic"
SYNTHETIC_TRIAGE_JSONL = SYNTHETIC_DIR / "triage_synthetic.jsonl.gz"
SYNTHETIC_TRIAGE_MANIFEST = SYNTHETIC_DIR / "triage_synthetic_manifest.json"
SYNTHETIC_TRIAGE_SAMPLE = SYNTHETIC_DIR / "triage_synthetic_sample.jsonl"
SYNTHETIC_TRIAGE_MODEL_PATH = MODELS_DIR / "triage_classifier_synthetic.joblib"


def ensure_models_dir() -> Path:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    return MODELS_DIR
