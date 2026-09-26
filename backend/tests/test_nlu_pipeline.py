from unittest.mock import patch

from app.services.nlu_service import parse_nlu_payload, understand_utterance
from app.services.triage_service import classify_free_text, retrieve_similar_examples
from tests.test_step4_triage import _run


def test_parse_nlu_drops_category_authority():
    parsed = parse_nlu_payload('{"canonical": "I fell", "category": "injury", "active_now": true}')
    assert parsed is None


def test_parse_nlu_accepts_restatement():
    parsed = parse_nlu_payload(
        '{"canonical": "I fell while walking. My leg is sprained.", "active_now": true, "facts": ["fell"]}'
    )
    assert parsed is not None
    assert parsed["canonical"].startswith("I fell")
    assert "category" not in parsed


def test_retrieve_similar_examples_returns_hits():
    hits = retrieve_similar_examples("i fell and cannot walk")
    assert hits
    assert "example" in hits[0]
    assert "score" in hits[0]


def test_historical_not_rewritten_by_nlu():
    async def fake_understand(_text: str):
        return {
            "canonical": "I fell and I am unable to walk",
            "active_now": True,
            "facts": ["fell"],
            "source": "llm_restatement",
        }

    with patch("app.services.nlu_service.understand_utterance", new=fake_understand):
        result, meta = _run(classify_free_text("I fell last year"))
    assert result.category == "unclassified"
    assert meta["understood_as"] is None


def test_nlu_restatement_classifies_when_original_is_vague():
    async def fake_understand(_text: str):
        return {
            "canonical": "I fell. My leg is sprained. I cannot walk.",
            "active_now": True,
            "facts": ["fell", "sprained"],
            "source": "llm_restatement",
        }

    with patch("app.services.nlu_service.understand_utterance", new=fake_understand):
        result, meta = _run(classify_free_text("something happened to my limb after a stumble"))
    assert result.category == "injury"
    assert meta["understood_as"]
    assert meta["retrieved"]
