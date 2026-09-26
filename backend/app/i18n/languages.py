"""Languages used with the Groq chat model and the ResQ UI.

For now the product exposes English, Hindi, Urdu, Telugu, and Hinglish.
Groq still receives the human-readable name (plus a Hinglish style note).
Whisper uses ISO-639-1; Hinglish maps to Hindi.
"""

from __future__ import annotations

from typing import Any

GROQ_SMALL_MULTILINGUAL_MODEL = "openai/gpt-oss-20b"

# Whisper ISO-639-1 codes. Name is what the client sends as `language`.
SUPPORTED_LANGUAGES: tuple[dict[str, str], ...] = (
    {"name": "English", "code": "en", "native": "English", "group": "india"},
    {"name": "Hindi", "code": "hi", "native": "हिन्दी", "group": "india"},
    {"name": "Hinglish", "code": "hi-Latn", "native": "Hinglish", "group": "india"},
    {"name": "Telugu", "code": "te", "native": "తెలుగు", "group": "india"},
    {"name": "Urdu", "code": "ur", "native": "اردو", "group": "india"},
)

DEFAULT_LANGUAGE = "English"

_ALIASES = {
    "en-in": "en",
    "eng": "en",
    "hin": "hi",
    "hi-en": "hi-latn",
    "hinglish": "hi-latn",
    "hi-latn": "hi-latn",
    "telugu": "te",
    "urd": "ur",
}

_BY_NAME = {item["name"].lower(): item for item in SUPPORTED_LANGUAGES}
_BY_CODE = {item["code"].lower(): item for item in SUPPORTED_LANGUAGES}


def language_catalog() -> dict[str, Any]:
    return {
        "groq_model": GROQ_SMALL_MULTILINGUAL_MODEL,
        "default_language": DEFAULT_LANGUAGE,
        "languages": [dict(item) for item in SUPPORTED_LANGUAGES],
    }


def _lookup(raw: str) -> dict[str, str] | None:
    key = raw.strip().lower()
    key = _ALIASES.get(key, key)
    return _BY_NAME.get(key) or _BY_CODE.get(key)


def normalize_language(value: str | None) -> str:
    if not value or not str(value).strip():
        return DEFAULT_LANGUAGE
    item = _lookup(str(value))
    return item["name"] if item else DEFAULT_LANGUAGE


def whisper_code(value: str | None) -> str | None:
    if not value:
        return None
    item = _lookup(str(value))
    if not item:
        return None
    code = item["code"].lower()
    if code.startswith("hi"):
        return "hi"
    return item["code"]


def groq_language_phrase(value: str | None) -> str:
    name = normalize_language(value)
    if name == "Hinglish":
        return (
            "Hinglish ONLY — Hindi+English mix in Latin letters "
            "(example: 'Aadmi gadi se gir gaya aur khoon nikal raha hai. Weight mat dalo.'). "
            "Do not write full English sentences. Do not use Devanagari or Urdu script."
        )
    if name == "Hindi":
        return "Hindi only, in Devanagari script. Do not reply in English."
    if name == "Telugu":
        return "Telugu only, in Telugu script. Do not reply in English."
    if name == "Urdu":
        return "Urdu only, in Urdu/Arabic script. Do not reply in English."
    return "English"


def is_english_reply(value: str | None) -> bool:
    return normalize_language(value) == "English"


def language_map() -> dict[str, str]:
    mapping: dict[str, str] = {}
    for item in SUPPORTED_LANGUAGES:
        mapping[item["name"].lower()] = whisper_code(item["name"]) or item["code"]
        mapping[item["code"].lower()] = whisper_code(item["name"]) or item["code"]
    mapping["hinglish"] = "hi"
    mapping["hi-latn"] = "hi"
    return mapping
