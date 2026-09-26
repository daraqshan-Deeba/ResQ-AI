"""
Triage Classification Service — Step 4

Three-tier cascade:
  Tier 1 (deterministic keyword/rule matching) →
  Tier 2 (TF-IDF embedding cosine similarity, sklearn) →
  Tier 3 (Groq LLM fallback — classification only, no severity) →
  unclassified

Strict architectural rules (Principle 2 & 3):
  • This service determines WHAT TYPE of incident is described.
  • It does NOT determine severity, risk level, or emergency level.
  • Tier 1 and Tier 2 are fully deterministic (same input → same output).
  • Tier 3 confidence is always capped at LOW regardless of what Groq claims.
  • If all tiers fail, returns category="unclassified" with low confidence.

Dependency note:
  Tier 2 uses sklearn TfidfVectorizer + cosine_similarity — already installed
  (sklearn 1.9.0 is present in this environment). No new package is required.
  If sklearn is not importable (e.g., stripped environment), Tier 2 is skipped
  gracefully and the cascade continues to Tier 3.

Startup safety:
  The Tier-2 vectorizer/matrix is built lazily on first call. A failure during
  that lazy init is caught and permanently disables Tier 2 for the lifetime of
  the process — the rest of the backend never crashes.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from typing import Optional

from app.models.schemas import EmergencyCategory, TriageResult
from app.services.severity import category_base_level, LEVEL_RANK

logger = logging.getLogger("resq.triage")

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

_HIGH_CONFIDENCE: float = 0.93
_TIER2_HIGH_CONFIDENCE: float = 0.82
_TIER2_MEDIUM_CONFIDENCE: float = 0.72
_TIER3_CONFIDENCE: float = 0.35  # always capped at low
_UNCLASSIFIED_CONFIDENCE: float = 0.20

_TIER2_HIGH_THRESHOLD: float = 0.78
_TIER2_MEDIUM_THRESHOLD: float = 0.68
_TIER2_MARGIN_REQUIRED: float = 0.08

# ─────────────────────────────────────────────────────────────────────────────
# Step 4K — Normalization
# ─────────────────────────────────────────────────────────────────────────────

def _normalize(text: str) -> str:
    """Return a safely normalized version of the input for matching.

    Applies: Unicode NFC, lowercase, whitespace collapse, hyphen/punctuation
    normalization. Does NOT mutate the original string and does NOT do
    aggressive stemming that could create false positives.
    """
    if not text:
        return ""
    # Unicode normalization
    text = unicodedata.normalize("NFC", text)
    # Lowercase
    text = text.lower()
    # Replace hyphens/en-dashes with spaces so "snake-bite" → "snake bite"
    text = re.sub(r"[-–—]", " ", text)
    # Collapse repeated whitespace / newlines
    text = re.sub(r"\s+", " ", text)
    # Strip leading/trailing whitespace
    text = text.strip()
    return text


# ─────────────────────────────────────────────────────────────────────────────
# Step 4D — Tier 1: Keyword / phrase rule set
# ─────────────────────────────────────────────────────────────────────────────
# Design notes:
#  • Phrases are matched as whole-word sequences using \b word boundaries.
#  • Multi-word phrases are preferred over single tokens to avoid false positives
#    (e.g., "wire" alone does not trigger electrocution — "live wire" does).
#  • Each category has a tuple of (rule_label, regex_pattern) pairs.
#  • Regexes use re.IGNORECASE (normalization already lowercases, but belt+braces).
# ─────────────────────────────────────────────────────────────────────────────

_TIER1_RULES: dict[str, list[tuple[str, re.Pattern]]] = {}

def _phrase(label: str, *phrases: str) -> tuple[str, re.Pattern]:
    """Create a (label, compiled_regex) pair for a set of alternative phrases."""
    alternatives = "|".join(
        r"\b" + re.escape(p) + r"\b" for p in phrases
    )
    return (label, re.compile(alternatives, re.IGNORECASE))


_TIER1_RULES["flooding"] = [
    _phrase("flood + rising water (multilingual)",
            "ghar mein pani", "pani aa raha hai", "pani badh raha hai", "pani tez badh raha hai",
            "intlo neeru", "neeru vastondi", "water enter avutundi",
            "sadak pani mein doob"),
    _phrase("flood + rising water",
            "flood water", "floodwater", "flooding", "flash flood",
            "water entering", "water entering my house", "water entering the house",
            "water is entering", "rising water", "water level rising",
            "water is rising", "water has risen", "street underwater",
            "street is underwater", "street is flooded", "road is flooded", "roads flooded",
            "trapped in water", "trapped by floodwater", "submerged", "inundated",
            "heavy flooding", "severe flooding", "waterlogged street", "waterlogged",
            "house is flooding", "drain overflowing"),
    # Extra guard: require "water" with "level" or "rising/entered" rather than
    # bare "water" — prevents "water bottle" from matching.
    _phrase("water level",
            "water level", "water levels"),
]

_TIER1_RULES["electrocution"] = [
    _phrase("electric shock (multilingual)",
            "bijli ka jhatka", "current lag gaya", "current shock ayindi",
            "live wire padipoyindi"),
    _phrase("electric shock",
            "electric shock", "electrocuted", "electrocution",
            "live wire", "live wire down", "exposed wire", "live electrical wire",
            "exposed electrical wire", "electric current",
            "sparks from wire", "wire sparking", "power line down",
            "power line fell", "downed power line", "downed power cable",
            "fallen power line", "exposed wiring", "smell of burning wires",
            "burning wires", "shocked by appliance",
            "electric pole fell", "electricity shock", "transformer sparking"),
    # Negative guard: "wire transfer" and "barbed wire" should NOT match.
    # Implemented by using multi-word phrases above (no bare "wire" rule).
]

_TIER1_RULES["injury"] = [
    _phrase("injury (multilingual)",
            "bahut bleeding", "haddi toot gayi", "khoon bah raha hai",
            "chala bleeding avutundi", "bone break ayyindi"),
    _phrase("injury + bleeding",
            "deep cut", "severe cut", "serious cut",
            "bleeding badly", "bleeding heavily", "heavy bleeding", "severe bleeding",
            "someone is bleeding", "broken bone", "fracture", "fractured",
            "severe wound", "serious wound",
            "unconscious", "unconscious person", "not breathing", "stopped breathing",
            "fell and injured", "fell and is hurt", "someone fell and is hurt",
            "seriously injured", "badly injured", "person not responding",
            "lost a lot of blood",
            "head injury", "spinal injury", "internal bleeding",
            "bone sticking out", "compound fracture"),
    _phrase("injury (general)",
            "injured and bleeding", "injured badly", "badly hurt",
            "critical injury", "severe injury"),
]

_TIER1_RULES["snakebite"] = [
    _phrase("snake bite (multilingual)",
            "saanp ne kaat", "paamu kadithindi", "snake bite ho gaya",
            "snake bite ayyindi"),
    _phrase("snake bite",
            "snake bite", "snakebite", "bitten by a snake",
            "bitten by snake", "snake bit", "snake has bitten",
            "snake attack", "snake attacked", "venomous snake", "viper bite",
            "cobra bite", "krait bite", "need antivenom", "fang marks"),
    # "snake plant" has no bite/bit/attack → will not match any pattern above.
]

_TIER1_RULES["cyclone"] = [
    _phrase("cyclone (multilingual)",
            "tufan aa raha hai", "tez hawa chal rahi hai", "gali tez ga vistundi",
            "cyclone warning vachindi"),
    _phrase("cyclone",
            "cyclone", "cyclonic storm", "severe cyclone",
            "hurricane", "super cyclone", "tropical cyclone",
            "storm surge", "cyclone warning", "cyclone alert", "cyclone alert issued",
            "severe storm approaching", "strong cyclonic winds",
            "roof blown off", "strong winds approaching", "trees falling due to wind",
            "extreme wind speed", "wind damage to house", "storm approaching fast",
            "storm approaching"),
]

_TIER1_RULES["structural_damage"] = [
    _phrase("structural damage (multilingual)",
            "building gir gayi", "building collapse ayyindi", "chhat gir gayi"),
    _phrase("building collapse",
            "building collapse", "building collapsed", "building has collapsed",
            "building have collapsed", "building had collapsed",
            "building is collapsing", "building falling", "building is falling",
            "wall collapse", "wall collapsed", "wall has collapsed",
            "wall have collapsed", "wall had collapsed",
            "wall is collapsing", "wall caved in",
            "roof collapse", "roof collapsed", "roof has collapsed",
            "roof have collapsed", "roof had collapsed",
            "roof is collapsing", "roof caved in", "roof fell in",
            "house collapse", "house collapsed", "house has collapsed",
            "house had collapsed", "house is collapsing",
            "structure collapsed", "structure collapse",
            "structural damage", "cracked building",
            "ceiling collapsed", "ceiling has collapsed", "ceiling fell",
            "ceiling caved in", "ceiling is collapsing",
            "floor collapsed", "floor has collapsed", "floor caved in",
            "slab fell", "pillar collapsed", "pillar has collapsed",
            "people trapped under rubble", "trapped under rubble",
            "trapped under debris", "buried under rubble",
            "wall came down", "structure is unstable",
            "debris blocking the door", "trapped inside damaged building",
            "wall crack spreading", "wall crack"),
]


_TIER1_RULES["accident"] = [
    _phrase("car accident (multilingual)",
            "car accident ho gaya", "road accident ayyindi",
            "road pe accident", "bike accident ho gaya"),
    _phrase("car accident",
            "car accident", "road accident", "vehicle accident",
            "traffic accident", "bike accident",
            "motorbike accident", "motorcycle accident",
            "truck accident", "bus accident",
            "collision", "vehicle collision", "head on collision",
            "rear end collision",
            "hit by a car", "hit by a vehicle", "pedestrian hit by vehicle",
            "run over", "multi-car crash", "multi car crash", "accident on the highway",
            "vehicle overturned", "met with an accident"),
    # "accident last year" is caught by the temporal guard below.
]

# Temporal guard patterns: if the description contains strong past-tense
# temporal markers the incident is likely historical, not active.
# We reduce tier-1 confidence and let Tier 2/3 handle it.
_TEMPORAL_PAST_PATTERNS: list[re.Pattern] = [
    re.compile(r"\blast\s+(year|month|week)\b", re.IGNORECASE),
    re.compile(r"\byears?\s+ago\b", re.IGNORECASE),
    re.compile(r"\bmonths?\s+ago\b", re.IGNORECASE),
    re.compile(r"\bweeks?\s+ago\b", re.IGNORECASE),
    re.compile(r"\bused\s+to\b", re.IGNORECASE),
]

_PRESENT_TENSE_MARKERS: list[re.Pattern] = [
    re.compile(r"\b(now|currently|right now|still)\b", re.IGNORECASE),
    re.compile(r"\b(cannot breathe|can't breathe|not breathing)\b", re.IGNORECASE),
]

_QUESTION_FORM = re.compile(
    r"^\s*(is this|is it|could this be|do i have|should i)\b",
    re.IGNORECASE,
)

_NEGATION_BY_CATEGORY: dict[str, re.Pattern] = {
    "flooding": re.compile(r"\b(no|not a|not an|without|isn't any)\s+(flood|flooding|floodwater)\b", re.I),
    "accident": re.compile(r"\b(no|not a|not an)\s+(accident|crash|collision)\b", re.I),
    "snakebite": re.compile(r"\b(no|not a)\s+snake\s*(bite)?\b", re.I),
    "fire": re.compile(r"\b(no|not a)\s+fire\b", re.I),
}


def _is_likely_historical(norm_text: str) -> bool:
    """Return True if temporal markers suggest this is a past/historical report."""
    return any(p.search(norm_text) for p in _TEMPORAL_PAST_PATTERNS)


def _is_present_danger(norm_text: str) -> bool:
    return any(p.search(norm_text) for p in _PRESENT_TENSE_MARKERS)


def _category_negated(category: str, norm_text: str) -> bool:
    pattern = _NEGATION_BY_CATEGORY.get(category)
    return bool(pattern and pattern.search(norm_text))


def _pick_primary_category(categories: list[str]) -> str:
    return max(categories, key=lambda c: LEVEL_RANK.get(category_base_level(c), 0))


# ─────────────────────────────────────────────────────────────────────────────
# Step 4D — Tier 1 runner
# ─────────────────────────────────────────────────────────────────────────────

def _tier1_classify(norm_text: str) -> TriageResult | None:
    """
    Run keyword rules against normalized text.

    Returns TriageResult if exactly one category matches (and the description
    is not clearly historical). Returns None if zero or multiple categories
    match — caller must proceed to Tier 2.

    Step 4E: conflicting rules → not high-confidence Tier 1 → return None.
    """
    if not norm_text:
        return None

    matched_categories: list[tuple[str, str]] = []  # (category, rule_label)

    for category, rule_list in _TIER1_RULES.items():
        for rule_label, pattern in rule_list:
            if pattern.search(norm_text):
                matched_categories.append((category, rule_label))
                break  # one match per category is enough

    # Deduplicate categories (a category may have multiple rule groups)
    unique_categories = list(dict.fromkeys(c for c, _ in matched_categories))

    if len(unique_categories) == 0:
        return None  # no match → proceed to Tier 2

    unique_categories = [c for c in unique_categories if not _category_negated(c, norm_text)]
    if not unique_categories:
        return None

    if _QUESTION_FORM.search(norm_text) and not _is_present_danger(norm_text):
        return None

    category = _pick_primary_category(unique_categories)
    rule_label = next(label for cat, label in matched_categories if cat == category)

    if _is_likely_historical(norm_text) and not _is_present_danger(norm_text):
        logger.debug("Tier1: matched '%s' but temporal markers suggest historical.", category)
        return None

    confidence = _HIGH_CONFIDENCE if len(unique_categories) == 1 else 0.82
    extra = ""
    if len(unique_categories) > 1:
        extra = f" Multiple hazards matched ({', '.join(unique_categories)}); using highest-severity category."

    return TriageResult(
        category=category,  # type: ignore[arg-type]
        confidence=confidence,
        tier=1,
        matched_rule_or_example=rule_label,
        candidate_categories=unique_categories,
        explanation=(
            f"Keyword rule matched '{rule_label}' in the description. "
            f"Category determined deterministically as '{category}'."
            + extra
        ),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Step 4G — Tier 2: TF-IDF embedding + cosine similarity
# ─────────────────────────────────────────────────────────────────────────────
# Uses sklearn.feature_extraction.text.TfidfVectorizer (already installed).
# This is locally deterministic — same input always gives same embedding.
# No model download, no network dependency, zero startup cost.
#
# Architecture alignment:
#   • The vectorizer is fit once on the canonical examples at first call.
#   • Per request: transform input → cosine_similarity → threshold + margin.
#   • If sklearn is unavailable, _TIER2_AVAILABLE = False and we fall through.
# ─────────────────────────────────────────────────────────────────────────────

# Canonical examples — authored natural-language sentences per category.
_TIER2_EXAMPLES: dict[str, list[str]] = {
    "flooding": [
        "water is entering my house",
        "flood water is rising outside",
        "I am trapped in flood water",
        "the streets are completely submerged",
        "there is a flash flood in our area",
        "our ground floor is under water",
        "the river has overflowed into the neighbourhood",
        "water came in through the door during the storm",
        "the entire road is flooded and we cannot get out",
        "heavy rain has caused severe flooding",
    ],
    "electrocution": [
        "someone got an electric shock",
        "there is a live exposed wire on the road",
        "a person was electrocuted by a fallen power line",
        "sparks are coming from a broken wire",
        "an electric pole has fallen in the street",
        "I see exposed electrical wires after the storm",
        "the transformer is sparking dangerously",
        "a child touched an exposed live wire and collapsed",
    ],
    "injury": [
        "a person is badly injured and bleeding",
        "someone has a deep cut and cannot stop bleeding",
        "there is a person with a broken bone who needs help",
        "someone fell from a height and is seriously hurt",
        "my friend slipped and fractured their leg",
        "a person is unconscious and not responding",
        "the victim has severe head injuries",
        "someone is bleeding very heavily from a wound",
    ],
    "snakebite": [
        "a snake bit someone",
        "my brother was bitten by a snake",
        "there is a snakebite victim who needs antivenom",
        "a person was attacked by a cobra",
        "a venomous snake bit a child in the garden",
        "someone stepped on a snake and got bitten",
        "a snake bit my dog in the yard",
    ],
    "cyclone": [
        "a cyclone is approaching our area",
        "a severe cyclonic storm is near the coast",
        "strong cyclone winds are tearing off rooftops",
        "there is a cyclone warning and we need to evacuate",
        "the tropical storm is intensifying rapidly",
        "the hurricane is expected to make landfall tonight",
        "cyclone storm surge is flooding coastal areas",
    ],
    "structural_damage": [
        "the building has partially collapsed",
        "the roof of our house fell in",
        "a wall in the building has crumbled",
        "the ceiling caved in on us",
        "the structure is collapsing and people are trapped",
        "a nearby building came down after the earthquake",
        "our house has severe cracks and may collapse",
        "there are people trapped under building rubble",
    ],
    "accident": [
        "there was a road collision near the market",
        "a car accident happened on the highway",
        "two vehicles have crashed into each other",
        "a pedestrian was hit by a speeding car",
        "multiple vehicles are involved in a road accident",
        "there is a serious crash on the main road",
        "a motorbike rider was thrown off in a collision",
        "the bus lost control and hit another vehicle",
    ],
    "unclassified": [
        "I need general emergency help",
        "something happened and I am scared",
        "I am not sure what is going on but I need help",
        "please send someone to help me",
        "there is an emergency situation here",
    ],
}

# Flat list of (category, example_text) for vectorizer
_EXAMPLE_PAIRS: list[tuple[str, str]] = [
    (cat, ex) for cat, exs in _TIER2_EXAMPLES.items() for ex in exs
]
_EXAMPLE_CATEGORIES: list[str] = [cat for cat, _ in _EXAMPLE_PAIRS]
_EXAMPLE_TEXTS: list[str] = [ex for _, ex in _EXAMPLE_PAIRS]

# Lazy-initialized state
_tier2_vectorizer = None
_tier2_matrix = None
_TIER2_AVAILABLE: bool | None = None  # None = not yet initialized


def _ensure_tier2() -> bool:
    """Lazily build the TF-IDF vectorizer on first call.
    Returns True if Tier 2 is ready, False if it is (permanently) unavailable.
    """
    global _tier2_vectorizer, _tier2_matrix, _TIER2_AVAILABLE

    if _TIER2_AVAILABLE is True:
        return True
    if _TIER2_AVAILABLE is False:
        return False

    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity as _cos  # noqa: F401

        vectorizer = TfidfVectorizer(ngram_range=(1, 3), min_df=1)
        matrix = vectorizer.fit_transform(_EXAMPLE_TEXTS)
        _tier2_vectorizer = vectorizer
        _tier2_matrix = matrix
        _TIER2_AVAILABLE = True
        logger.info("Tier2: TF-IDF vectorizer initialised with %d examples.", len(_EXAMPLE_TEXTS))
        return True
    except Exception as exc:
        _TIER2_AVAILABLE = False
        logger.warning("Tier2: Failed to initialise TF-IDF vectorizer (%s). Tier 2 disabled.", exc)
        return False


def _tier2_classify(norm_text: str) -> TriageResult | None:
    """
    Compute cosine similarity between input and canonical examples.

    Returns TriageResult on high/medium hit, None on insufficient
    similarity/margin or if the embedding layer is unavailable.
    """
    if not norm_text or not _ensure_tier2():
        return None

    try:
        from sklearn.metrics.pairwise import cosine_similarity
        vec = _tier2_vectorizer.transform([norm_text])
        sims = cosine_similarity(vec, _tier2_matrix)[0]

        # Sort descending
        sorted_idx = sims.argsort()[::-1]
        s1_idx = sorted_idx[0]
        s1 = float(sims[s1_idx])
        best_category = _EXAMPLE_CATEGORIES[s1_idx]
        best_example = _EXAMPLE_TEXTS[s1_idx]

        # Second-best score across all examples (including different examples of the same category)
        s2 = float(sims[sorted_idx[1]]) if len(sorted_idx) > 1 else 0.0
        margin = s1 - s2

        logger.debug(
            "Tier2: best_cat=%s s1=%.3f s2=%.3f margin=%.3f", best_category, s1, s2, margin
        )

        # Skip unclassified-examples being the best match — let Tier 3 handle truly ambiguous
        if best_category == "unclassified":
            return None

        if s1 >= _TIER2_HIGH_THRESHOLD and margin >= _TIER2_MARGIN_REQUIRED:
            confidence = _TIER2_HIGH_CONFIDENCE
            confidence_label = "high"
        elif s1 >= _TIER2_MEDIUM_THRESHOLD and margin >= _TIER2_MARGIN_REQUIRED:
            confidence = _TIER2_MEDIUM_CONFIDENCE
            confidence_label = "medium"
        else:
            return None  # insufficient similarity or margin → Tier 3

        return TriageResult(
            category=best_category,
            confidence=confidence,
            tier=2,
            matched_rule_or_example=best_example,
            explanation=(
                f"Embedding similarity matched '{best_example}' "
                f"(category: {best_category}, similarity: {s1:.2f}, "
                f"margin: {margin:.2f}, confidence: {confidence_label})."
            ),
        )
    except Exception as exc:
        logger.warning("Tier2: Unexpected error during similarity computation: %s", exc)
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Step 4I — Tier 3: Groq LLM fallback (classification only)
# ─────────────────────────────────────────────────────────────────────────────

_VALID_GROQ_CATEGORIES: set[str] = {
    "flooding", "electrocution", "injury", "snakebite",
    "cyclone", "structural_damage", "accident", "unclassified",
}

_TIER3_SYSTEM_PROMPT = """You are a triage classification assistant for ResQ AI, an emergency response system.
Your task is ONLY to classify the emergency type described by the user.

Respond with EXACTLY one line in this format:
CATEGORY: <category>

The category MUST be one of these exact values (lowercase, no spaces except underscores):
flooding, electrocution, injury, snakebite, cyclone, structural_damage, accident, unclassified

Use "unclassified" if the description does not clearly match any of the above categories.

IMPORTANT RULES:
- Do NOT determine severity, risk level, or emergency seriousness.
- Do NOT generate first aid advice, guidance, or any instructions.
- Do NOT include any other text, explanation, or commentary.
- Respond with exactly one line starting with "CATEGORY: "."""


async def _tier3_classify(original_text: str) -> TriageResult:
    """
    Ask Groq to classify the category — for ambiguous inputs only.

    Confidence is ALWAYS capped at _TIER3_CONFIDENCE (low) regardless
    of what Groq claims. Groq never determines severity.

    Returns an explicit unclassified TriageResult on any failure.
    """
    _unclassified = TriageResult(
        category="unclassified",
        confidence=_UNCLASSIFIED_CONFIDENCE,
        tier=3,
        matched_rule_or_example=None,
        explanation="Could not confidently map the description to a supported emergency category.",
    )

    try:
        from app.services.groq_service import call_groq_safe
    except ImportError:
        logger.warning("Tier3: groq_service not importable; returning unclassified.")
        return _unclassified

    messages = [
        {"role": "system", "content": _TIER3_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"Emergency description: {original_text[:500]}",  # cap length
        },
    ]

    result = await call_groq_safe(messages, temperature=0.0)

    if not result.available or not result.data:
        logger.info(
            "Tier3: Groq unavailable (%s). Returning unclassified.", result.error_type
        )
        return _unclassified

    raw = result.data.strip()

    # Parse "CATEGORY: <value>"
    match = re.search(r"\bCATEGORY\s*:\s*(\w+)", raw, re.IGNORECASE)
    if not match:
        logger.warning("Tier3: Could not parse category from Groq output (truncated for safety).")
        return _unclassified

    category_raw = match.group(1).lower().strip()

    if category_raw not in _VALID_GROQ_CATEGORIES:
        logger.warning(
            "Tier3: Groq returned unknown category '%s'; treating as unclassified.",
            category_raw,
        )
        return _unclassified

    return TriageResult(
        category=category_raw,  # type: ignore[arg-type]
        confidence=_TIER3_CONFIDENCE,  # always capped at low
        tier=3,
        matched_rule_or_example=None,
        explanation=(
            f"LLM fallback (Tier 3) classified this as '{category_raw}'. "
            "Confidence is capped at low per architectural safety rules."
        ),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────────────

async def classify(description: str, *, skip_llm: bool = False) -> TriageResult:
    """Classify an emergency description via the three-tier cascade.

    Tier 1 (deterministic keyword rules) →
    Tier 2 (TF-IDF cosine similarity) →
    Tier 3 (Groq LLM, classification only) →
    unclassified (explicit, low confidence)

    Args:
        description: Raw user-provided emergency description.

    Returns:
        TriageResult — always. Never raises.
    """
    _unclassified_default = TriageResult(
        category="unclassified",
        confidence=_UNCLASSIFIED_CONFIDENCE,
        tier=3,
        matched_rule_or_example=None,
        explanation="Could not confidently map the description to a supported emergency category.",
    )

    if not description or not description.strip():
        return TriageResult(
            category="unclassified",
            confidence=_UNCLASSIFIED_CONFIDENCE,
            tier=3,
            matched_rule_or_example=None,
            explanation="Empty or blank description provided; cannot classify.",
        )

    # Truncate very long inputs to prevent resource exhaustion
    safe_description = description[:2000]
    norm_text = _normalize(safe_description)

    # Historical / past-tense reports are not active emergencies — skip
    # keyword/embedding/ML tiers that would over-fit on lexical overlap
    # (e.g. "years ago I had a car accident" → accident).
    if _is_likely_historical(norm_text) and not _is_present_danger(norm_text):
        logger.debug("Triage: temporal markers suggest historical report.")
        return TriageResult(
            category="unclassified",
            confidence=_UNCLASSIFIED_CONFIDENCE,
            tier=3,
            matched_rule_or_example=None,
            explanation=(
                "Description contains past-tense temporal markers "
                "(e.g. 'years ago', 'last year'); treated as historical, not active."
            ),
        )

    # ── Tier 1 ──────────────────────────────────────────────────────────────
    try:
        t1 = _tier1_classify(norm_text)
        if t1 is not None:
            logger.debug("Triage resolved at Tier 1: %s (%.2f)", t1.category, t1.confidence)
            return t1
    except Exception as exc:
        logger.warning("Tier1: Unexpected error: %s. Continuing to Tier 2.", exc)

    # ── Tier 2 ──────────────────────────────────────────────────────────────
    try:
        t2 = _tier2_classify(norm_text)
        if t2 is not None:
            logger.debug("Triage resolved at Tier 2: %s (%.2f)", t2.category, t2.confidence)
            return t2
    except Exception as exc:
        logger.warning("Tier2: Unexpected error: %s. Continuing to ML tier.", exc)

    # ── Tier 2.5 — Multilingual ML classifier ─────────────────────────────
    try:
        from app.core.config import settings
        from app.services.triage_ml_service import classify_ml

        if settings.triage_ml_enabled:
            t2ml = classify_ml(norm_text)
            if t2ml is not None and t2ml.category != "unclassified":
                logger.debug(
                    "Triage resolved at ML tier: %s (%.2f)", t2ml.category, t2ml.confidence
                )
                return t2ml
    except Exception as exc:
        logger.warning("Triage ML: Unexpected error: %s. Continuing to Tier 3.", exc)

    # ── Tier 3 ──────────────────────────────────────────────────────────────
    if skip_llm:
        return _unclassified_default

    try:
        t3 = await _tier3_classify(safe_description)
        logger.debug("Triage resolved at Tier 3: %s (%.2f)", t3.category, t3.confidence)
        return t3
    except Exception as exc:
        logger.warning("Tier3: Unexpected error: %s. Returning unclassified.", exc)
        return _unclassified_default
