from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Literal, Optional

from app.ml.paths import REPORT_MODEL_PATH, REPORT_TRAINING_JSON
from app.ml.text_classifier import load_model, predict, save_model, train_pipeline

logger = logging.getLogger("resq.ml.reports")

ReportCategory = Literal["accident", "construction", "congestion", "flooding", "other"]

_MIN_PROBA = 0.35
_MIN_MARGIN = 0.05

_pipeline = None
_metadata: dict = {}
_available: bool | None = None


def _normalize(text: str) -> str:
    from app.services.triage_service import _normalize as triage_normalize

    return triage_normalize(text)


def load_training_rows() -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []

    if REPORT_TRAINING_JSON.exists():
        payload = json.loads(REPORT_TRAINING_JSON.read_text(encoding="utf-8"))
        for item in payload.get("examples", []):
            text = (item.get("text") or "").strip()
            category = (item.get("category") or "").strip()
            if text and category:
                rows.append((text, category))
                if item.get("language") in {"hi", "te"}:
                    rows.append((text, category))

    community_json = REPORT_TRAINING_JSON.parent / "community_reports.json"
    if community_json.exists():
        for item in json.loads(community_json.read_text(encoding="utf-8")):
            message = (item.get("message") or "").strip()
            if not message:
                continue
            label = _label_from_keywords(message)
            if label:
                rows.append((message, label))

    return rows


def _label_from_keywords(message: str) -> Optional[str]:
    from app.services.traffic_service import (
        ACCIDENT_PATTERN,
        CONSTRUCTION_PATTERN,
        CONGESTION_PATTERN,
    )

    lower = message.lower()
    if any(w in lower for w in ("flood", "waterlog", "underwater", "submerged", "drain overflow")):
        return "flooding"
    if ACCIDENT_PATTERN.search(message):
        return "accident"
    if CONSTRUCTION_PATTERN.search(message):
        return "construction"
    if CONGESTION_PATTERN.search(message):
        return "congestion"
    return "other"


def train_report_model(*, force: bool = False) -> Path:
    rows = load_training_rows()
    if len(rows) < 15:
        raise RuntimeError(f"Insufficient report training rows: {len(rows)}")

    if REPORT_MODEL_PATH.exists() and not force:
        return REPORT_MODEL_PATH

    texts = [_normalize(text) for text, _ in rows]
    labels = [label for _, label in rows]
    pipeline = train_pipeline(texts, labels)
    classes = list(pipeline.named_steps["clf"].classes_)
    save_model(
        REPORT_MODEL_PATH,
        pipeline,
        model_name="report_classifier",
        training_rows=len(rows),
        classes=classes,
    )
    return REPORT_MODEL_PATH


def reset_report_model() -> None:
    global _pipeline, _metadata, _available
    _pipeline = None
    _metadata = {}
    _available = None


def _ensure_model() -> bool:
    global _pipeline, _metadata, _available

    if _available is True:
        return True
    if _available is False:
        return False

    loaded = load_model(REPORT_MODEL_PATH)
    if loaded is None:
        try:
            train_report_model(force=True)
            loaded = load_model(REPORT_MODEL_PATH)
        except Exception as exc:
            logger.warning("Report model train/load failed: %s", exc)
            _available = False
            return False

    if loaded is None:
        _available = False
        return False

    _pipeline, _metadata = loaded
    _available = True
    return True


def report_model_available() -> bool:
    return _ensure_model()


def classify_report(message: str) -> Optional[ReportCategory]:
    """Classify a community report for traffic/incident routing."""
    if not message.strip():
        return None

    norm = _normalize(message)
    if _ensure_model() and _pipeline is not None:
        prediction = predict(
            _pipeline,
            norm,
            min_proba=_MIN_PROBA,
            min_margin=_MIN_MARGIN,
        )
        if prediction and prediction.label != "other":
            return prediction.label  # type: ignore[return-value]
        if prediction and prediction.label == "other":
            return None

    keyword = _label_from_keywords(message)
    if keyword and keyword != "other":
        return keyword  # type: ignore[return-value]
    return None


def training_stats() -> dict:
    rows = load_training_rows()
    return {
        "total_training_rows": len(rows),
        "model_available": report_model_available(),
        "model_path": str(REPORT_MODEL_PATH),
        "metadata": _metadata,
        "classes": _metadata.get("classes", []),
    }
