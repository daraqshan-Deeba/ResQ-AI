from app.core.config import Settings
from app.i18n.languages import (
    GROQ_SMALL_MULTILINGUAL_MODEL,
    groq_language_phrase,
    language_catalog,
    normalize_language,
    whisper_code,
)
from app.main import app
from app.services.transcription_service import resolve_language_code


def test_default_groq_model_is_small_multilingual():
    cfg = Settings(GROQ_API_KEY="", _env_file=None)
    assert cfg.groq_model == GROQ_SMALL_MULTILINGUAL_MODEL


def test_language_catalog_is_core_set():
    catalog = language_catalog()
    names = {item["name"] for item in catalog["languages"]}
    assert catalog["groq_model"] == GROQ_SMALL_MULTILINGUAL_MODEL
    assert names == {"English", "Hindi", "Hinglish", "Telugu", "Urdu"}
    assert normalize_language("te") == "Telugu"
    assert normalize_language("hi-Latn") == "Hinglish"
    assert normalize_language("unknown-lang") == "English"
    assert whisper_code("Hinglish") == "hi"
    assert whisper_code("Urdu") == "ur"
    assert resolve_language_code("Hindi") == "hi"
    assert "Hinglish" in groq_language_phrase("Hinglish")


def test_languages_endpoint():
    client = app.test_client()
    res = client.get("/api/languages")
    assert res.status_code == 200
    data = res.get_json()
    assert data["groq_model"] == GROQ_SMALL_MULTILINGUAL_MODEL
    assert len(data["languages"]) == 5
