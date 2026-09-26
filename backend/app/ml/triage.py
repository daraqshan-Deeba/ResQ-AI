from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from app.ml.paths import TRIAGE_MODEL_PATH, TRIAGE_TRAINING_JSON
from app.ml.text_classifier import load_model, predict, save_model, train_pipeline
from app.models.schemas import TriageResult

logger = logging.getLogger("resq.ml.triage")

_ML_HIGH_CONFIDENCE = 0.80
_ML_MEDIUM_CONFIDENCE = 0.72
_ML_UNCLASSIFIED_CONFIDENCE = 0.78
_MIN_PROBA = 0.32
_MIN_MARGIN = 0.04

_pipeline = None
_metadata: dict = {}
_available: bool | None = None


def _normalize(text: str) -> str:
    from app.services.triage_service import _normalize as triage_normalize

    return triage_normalize(text)


def load_training_rows() -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    gold_texts: set[str] = set()
    gold_path = Path(__file__).resolve().parents[2] / "data" / "triage_eval_gold.json"
    if gold_path.exists():
        try:
            gold = json.loads(gold_path.read_text(encoding="utf-8"))
            for item in gold.get("cases", gold if isinstance(gold, list) else []):
                if isinstance(item, dict):
                    text = (item.get("text") or "").strip()
                    if text:
                        gold_texts.add(_normalize(text))
        except Exception as exc:
            logger.warning("Could not load gold holdout texts: %s", exc)

    if TRIAGE_TRAINING_JSON.exists():
        payload = json.loads(TRIAGE_TRAINING_JSON.read_text(encoding="utf-8"))
        for item in payload.get("examples", []):
            text = (item.get("text") or "").strip()
            category = (item.get("category") or "").strip()
            if text and category and _normalize(text) not in gold_texts:
                rows.append((text, category))
                if item.get("language") in {"hi", "te"}:
                    rows.append((text, category))

    try:
        from app.services.triage_service import _TIER2_EXAMPLES

        for category, examples in _TIER2_EXAMPLES.items():
            for example in examples:
                rows.append((example, category))
    except Exception as exc:
        logger.warning("Could not load Tier 2 examples for triage training: %s", exc)

    return rows


def train_triage_model(*, force: bool = False) -> Path:
    rows = load_training_rows()
    if len(rows) < 20:
        raise RuntimeError(f"Insufficient triage training rows: {len(rows)}")

    if TRIAGE_MODEL_PATH.exists() and not force:
        return TRIAGE_MODEL_PATH

    texts = [_normalize(text) for text, _ in rows]
    labels = [label for _, label in rows]
    pipeline = train_pipeline(texts, labels)
    classes = list(pipeline.named_steps["clf"].classes_)
    save_model(
        TRIAGE_MODEL_PATH,
        pipeline,
        model_name="triage_classifier",
        training_rows=len(rows),
        classes=classes,
    )
    return TRIAGE_MODEL_PATH


def reset_triage_model() -> None:
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

    loaded = load_model(TRIAGE_MODEL_PATH)
    if loaded is None:
        try:
            train_triage_model(force=True)
            loaded = load_model(TRIAGE_MODEL_PATH)
        except Exception as exc:
            logger.warning("Triage model train/load failed: %s", exc)
            _available = False
            return False

    if loaded is None:
        _available = False
        return False

    _pipeline, _metadata = loaded
    _available = True
    logger.info(
        "Triage model loaded (%s, %d classes).",
        _metadata.get("model_name", "triage"),
        len(_metadata.get("classes", [])),
    )
    return True


def triage_model_available() -> bool:
    return _ensure_model()


def _detect_script_hint(text: str) -> str:
    for char in text:
        code = ord(char)
        if 0x0900 <= code <= 0x097F:
            return "devanagari"
        if 0x0C00 <= code <= 0x0C7F:
            return "telugu"
    if any(token in text for token in ("hai", "raha", "gaya", "mein", "pani")):
        return "hindi_roman"
    if any(token in text for token in ("ayindi", "vastondi", "kadithindi", "neeru")):
        return "telugu_roman"
    return "latin"


def classify_triage(norm_text: str) -> Optional[TriageResult]:
    if not norm_text or not _ensure_model() or _pipeline is None:
        return None

    prediction = predict(
        _pipeline,
        norm_text,
        min_proba=_MIN_PROBA,
        min_margin=_MIN_MARGIN,
    )
    if prediction is None:
        return None

    language_hint = _detect_script_hint(norm_text)
    best_cat = prediction.label
    best_score = prediction.probability
    margin = prediction.margin

    if best_cat == "unclassified":
        return None

    confidence = (
        _ML_HIGH_CONFIDENCE
        if best_score >= 0.55 and margin >= 0.08
        else _ML_MEDIUM_CONFIDENCE
    )
    label = "high" if confidence == _ML_HIGH_CONFIDENCE else "medium"

    return TriageResult(
        category=best_cat,  # type: ignore[arg-type]
        confidence=confidence,
        tier=2,
        matched_rule_or_example=f"ml_classifier:{best_cat}",
        explanation=(
            f"Multilingual ML classifier predicted '{best_cat}' "
            f"(probability: {best_score:.2f}, margin: {margin:.2f}, "
            f"confidence: {label}, script: {language_hint})."
        ),
    )


def training_stats() -> dict:
    rows = load_training_rows()
    by_lang: dict[str, int] = {}
    by_cat: dict[str, int] = {}
    if TRIAGE_TRAINING_JSON.exists():
        payload = json.loads(TRIAGE_TRAINING_JSON.read_text(encoding="utf-8"))
        for item in payload.get("examples", []):
            lang = item.get("language", "unknown")
            cat = item.get("category", "unknown")
            by_lang[lang] = by_lang.get(lang, 0) + 1
            by_cat[cat] = by_cat.get(cat, 0) + 1
    return {
        "total_training_rows": len(rows),
        "ml_available": triage_model_available(),
        "model_path": str(TRIAGE_MODEL_PATH),
        "metadata": _metadata,
        "by_language": by_lang,
        "by_category": by_cat,
        "classes": _metadata.get("classes", []),
    }
