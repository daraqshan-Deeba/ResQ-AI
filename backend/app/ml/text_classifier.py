from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("resq.ml")


@dataclass
class Prediction:
    label: str
    probability: float
    margin: float
    probabilities: dict[str, float]


def build_text_pipeline() -> Any:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import FeatureUnion, Pipeline

    vectorizer = FeatureUnion(
        [
            (
                "word",
                TfidfVectorizer(
                    analyzer="word",
                    ngram_range=(1, 2),
                    min_df=1,
                    sublinear_tf=True,
                ),
            ),
            (
                "char",
                TfidfVectorizer(
                    analyzer="char_wb",
                    ngram_range=(3, 5),
                    min_df=1,
                    sublinear_tf=True,
                ),
            ),
        ]
    )
    return Pipeline(
        [
            ("tfidf", vectorizer),
            (
                "clf",
                LogisticRegression(
                    max_iter=3000,
                    class_weight="balanced",
                    solver="lbfgs",
                ),
            ),
        ]
    )


def train_pipeline(texts: list[str], labels: list[str]) -> Any:
    pipeline = build_text_pipeline()
    pipeline.fit(texts, labels)
    return pipeline


def save_model(
    path: Path,
    pipeline: Any,
    *,
    model_name: str,
    training_rows: int,
    classes: list[str],
    extra: dict[str, Any] | None = None,
) -> None:
    import joblib

    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "pipeline": pipeline,
        "metadata": {
            "model_name": model_name,
            "trained_at": datetime.now(timezone.utc).isoformat(),
            "training_rows": training_rows,
            "classes": classes,
            **(extra or {}),
        },
    }
    joblib.dump(payload, path)
    logger.info("Saved %s → %s (%d rows)", model_name, path, training_rows)


def load_model(path: Path) -> tuple[Any, dict[str, Any]] | None:
    if not path.exists():
        return None
    try:
        import joblib

        payload = joblib.load(path)
        return payload["pipeline"], payload.get("metadata", {})
    except Exception as exc:
        logger.warning("Failed to load model %s: %s", path, exc)
        return None


def predict(
    pipeline: Any,
    text: str,
    *,
    min_proba: float = 0.32,
    min_margin: float = 0.04,
) -> Prediction | None:
    if not text.strip():
        return None

    proba = pipeline.predict_proba([text])[0]
    classes = list(pipeline.named_steps["clf"].classes_)
    ranked = sorted(zip(classes, proba), key=lambda x: x[1], reverse=True)
    best_label, best_score = ranked[0]
    second_score = ranked[1][1] if len(ranked) > 1 else 0.0
    margin = float(best_score - second_score)

    if best_score < min_proba or margin < min_margin:
        return None

    return Prediction(
        label=best_label,
        probability=float(best_score),
        margin=margin,
        probabilities={label: float(score) for label, score in zip(classes, proba)},
    )
