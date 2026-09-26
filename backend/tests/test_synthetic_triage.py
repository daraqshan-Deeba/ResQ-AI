import json

from app.ml.synthetic_triage import (
    CATEGORIES,
    MIN_PARAMS_1M,
    expected_parameter_count,
    generate_dataset,
    iter_unique_records,
    load_gold_normalized,
    train_hashed_model,
)
from app.services.triage_service import _normalize


def test_synthetic_rows_are_unique_and_holdout_safe(tmp_path):
    gold = load_gold_normalized()
    rows = list(iter_unique_records(count=4000, seed=7, gold=gold))
    assert len(rows) == 4000
    texts = [_normalize(row["text"]) for row in rows]
    assert len(set(texts)) == 4000
    assert gold.isdisjoint(set(texts))
    assert {row["category"] for row in rows} == set(CATEGORIES)
    assert {row["tier"] for row in rows} == {1, 2, 3}
    assert {row["language"] for row in rows} <= {"en", "hi", "te"}
    assert not any(
        row["category"] == "injury" and "bus accident" in row["text"].lower()
        for row in rows
    )


def test_generate_dataset_writes_jsonl(tmp_path):
    out = tmp_path / "mini.jsonl"
    result = generate_dataset(count=500, seed=1, output=out, sample_size=20)
    assert result.count == 500
    lines = out.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 500
    first = json.loads(lines[0])
    assert first["category"] in CATEGORIES
    assert first["tier"] in (1, 2, 3)


def test_expected_params_meet_one_million():
    assert expected_parameter_count(8) >= MIN_PARAMS_1M
    assert expected_parameter_count(3) >= MIN_PARAMS_1M


def test_hashed_model_has_at_least_one_million_parameters(tmp_path):
    data = tmp_path / "rows.jsonl"
    result = generate_dataset(count=400, seed=3, output=data, sample_size=10)
    assert result.count == 400
    summary = train_hashed_model(
        data_path=data,
        label_field="category",
        limit=None,
        batch_size=128,
        min_params=MIN_PARAMS_1M,
        model_path=tmp_path / "model.joblib",
    )
    assert summary["parameter_count"] >= MIN_PARAMS_1M
