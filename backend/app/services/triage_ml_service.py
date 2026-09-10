"""
Multilingual triage ML classifier — delegates to persisted model in app.ml.triage.
"""

from __future__ import annotations

from app.ml.triage import (
    classify_triage,
    load_training_rows,
    reset_triage_model,
    train_triage_model,
    training_stats,
    triage_model_available,
)

# Backward-compatible aliases
classify_ml = classify_triage
ml_classifier_available = triage_model_available
reset_ml_classifier = reset_triage_model
_load_training_rows = load_training_rows

__all__ = [
    "classify_ml",
    "ml_classifier_available",
    "reset_ml_classifier",
    "training_stats",
    "train_triage_model",
    "load_training_rows",
]
