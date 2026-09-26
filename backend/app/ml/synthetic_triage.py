"""Combinatorial synthetic triage utterances (category + cascade-tier labels).

The production cascade still trains on ``triage_ml_training.json`` + Tier 2 examples.
This corpus is a separate, gold-holdout-safe set for larger experiments.

``tier`` is expected cascade *difficulty*, not a replacement for category:
  1 — lexicon-like (Tier 1 rules would usually fire)
  2 — paraphrase (meant for TF-IDF / sklearn)
  3 — hard / underspecified (often Groq or unclassified)

Labels never copy gold eval texts. Bare ``bus`` / ``RTC`` are not injury tokens.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import random
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterator

from app.ml.paths import DATA_DIR, SYNTHETIC_TRIAGE_JSONL

CATEGORIES = (
    "flooding",
    "electrocution",
    "injury",
    "snakebite",
    "cyclone",
    "structural_damage",
    "accident",
    "unclassified",
)

LANGUAGES = ("en", "hi", "te")
MIN_PARAMS_1M = 1_000_000

# Hashing union: 65_536 + 65_536 = 131_072 features × 8 classes = 1_048_576 weights.
# 2 branches × this width × n_classes + intercepts ≥ 1e6 for 8-way category.
HASH_FEATURES_PER_BRANCH = 65_536

Recipe = Callable[[random.Random], dict]


def _normalize(text: str) -> str:
    from app.services.triage_service import _normalize as triage_normalize

    return triage_normalize(text)


def load_gold_normalized() -> set[str]:
    gold_path = DATA_DIR / "triage_eval_gold.json"
    texts: set[str] = set()
    if not gold_path.exists():
        return texts
    payload = json.loads(gold_path.read_text(encoding="utf-8"))
    for item in payload.get("cases", []):
        text = (item.get("text") or "").strip()
        if text:
            texts.add(_normalize(text))
    return texts


def _text_key(text: str) -> str:
    return hashlib.sha1(_normalize(text).encode("utf-8")).hexdigest()


PLACES = [
    "Hyderabad", "Secunderabad", "Vijayawada", "Guntur", "Warangal", "Visakhapatnam",
    "Khammam", "Nizamabad", "Karimnagar", "Tirupati", "Kakinada", "Rajahmundry",
    "Nellore", "Anantapur", "Kurnool", "Ongole", "Eluru", "Machilipatnam",
    "Ameerpet", "Kukatpally", "Gachibowli", "Madhapur", "Uppal", "Miyapur",
    "Dilsukhnagar", "LB Nagar", "Charminar", "Nampally", "Begumpet", "Lingampally",
    "Shamshabad", "Patancheru", "Kompally", "Alwal", "Malkajgiri", "Kapra",
    "Tarnaka", "Habsiguda", "Nacharam", "Uppal stadium area", "Hitec City",
    "Financial District", "Kondapur", "Manikonda", "Narsingi", "Tellapur",
    "Banjara Hills", "Jubilee Hills", "Somajiguda", "Punjagutta", "Khairatabad",
    "Lakdikapul", "Abids", "Koti", "Sultan Bazar", "Malakpet", "Santoshnagar",
    "Chandrayangutta", "Falaknuma", "Tolichowki", "Mehdipatnam", "Attapur",
    "Rajendranagar", "Chevella", "Shamirpet", "Medchal", "Quthbullapur",
    "Bhongir", "Suryapet", "Nalgonda", "Mahabubnagar", "Wanaparthy",
    "Adilabad", "Nirmal", "Mancherial", "Peddapalli", "Jagtial",
    "Srikakulam", "Vizianagaram", "Anakapalle", "Tuni", "Samalkot",
    "Tenali", "Bapatla", "Chirala", "Narasaraopet", "Piduguralla",
    "Proddatur", "Kadapa", "Madanapalle", "Chittoor", "Srikalahasti",
    "ward 3", "ward 12", "ward 27", "old city lane", "canal road",
    "river bank colony", "hillside colony", "market road", "station road",
]

LANDMARKS = [
    "the bus stand", "the railway station", "the metro pillar", "the flyover",
    "the hospital gate", "the school compound", "the apartment basement",
    "the temple steps", "the market lane", "the drainage canal",
    "the construction site", "the parking lot", "platform 2", "platform 4",
    "the footbridge", "the underpass", "the lake bund", "the nala",
]

PEOPLE = [
    "I", "my mother", "my father", "my brother", "my sister", "my uncle",
    "my aunt", "my grandmother", "my child", "a neighbour", "an elderly man",
    "an elderly woman", "a passenger", "a worker", "a student", "a shopkeeper",
    "the driver", "a pedestrian", "a toddler", "my cousin",
]

NUMBERS = [str(n) for n in range(1, 81)]
HOURS = [f"{h:02d}:{m:02d}" for h in range(5, 23) for m in (0, 15, 30, 45)]
WEATHER = [
    "heavy rain", "overnight rain", "a cloudburst", "continuous drizzle",
    "a thunderstorm", "monsoon rain", "sudden downpour",
]
BODY = ["leg", "ankle", "back", "arm", "shoulder", "knee", "hip", "wrist"]
VEHICLES = ["car", "bike", "scooter", "lorry", "auto", "van", "tractor", "tempo"]
SNAKES = ["snake", "cobra", "viper", "krait", "saw-scaled viper"]
STRUCTURES = ["building", "wall", "roof", "ceiling", "slab", "balcony", "compound wall"]


def _who_en(rng: random.Random) -> str:
    who = rng.choice(PEOPLE)
    return "I" if who == "I" else who


def _house(rng: random.Random) -> str:
    return f"house {rng.choice(NUMBERS)}"


def _rec(text: str, category: str, language: str, tier: int) -> dict:
    return {
        "text": " ".join(text.split()),
        "category": category,
        "language": language,
        "tier": tier,
    }


def _recipes() -> list[Recipe]:
    def flood_en_t1(rng: random.Random) -> dict:
        return _rec(
            f"flood water is rising in {rng.choice(PLACES)} near {rng.choice(LANDMARKS)} "
            f"around {rng.choice(HOURS)} at {_house(rng)}",
            "flooding", "en", 1,
        )

    def flood_en_t2(rng: random.Random) -> dict:
        who = _who_en(rng)
        verb = "am trapped" if who == "I" else "is trapped"
        return _rec(
            f"{who} {verb} as the ground floor in {rng.choice(PLACES)} went under water "
            f"after {rng.choice(WEATHER)} by the {rng.choice(LANDMARKS)}",
            "flooding", "en", 2,
        )

    def flood_en_t3(rng: random.Random) -> dict:
        return _rec(
            f"water came up to the steps of {_house(rng)} in {rng.choice(PLACES)} "
            f"and we cannot get the two-wheeler out of the {rng.choice(LANDMARKS)}",
            "flooding", "en", 3,
        )

    def flood_hi(rng: random.Random) -> dict:
        return _rec(
            f"{rng.choice(PLACES)} mein ghar mein pani aa raha hai "
            f"{rng.choice(LANDMARKS)} ke paas {_house(rng)}",
            "flooding", "hi", 1,
        )

    def flood_te(rng: random.Random) -> dict:
        return _rec(
            f"{rng.choice(PLACES)} lo intlo neeru vastondi "
            f"{rng.choice(LANDMARKS)} daggara house {rng.choice(NUMBERS)}",
            "flooding", "te", 1,
        )

    def elec_en_t1(rng: random.Random) -> dict:
        return _rec(
            f"a live wire is down near {rng.choice(LANDMARKS)} in {rng.choice(PLACES)} "
            f"after {rng.choice(WEATHER)} at {rng.choice(HOURS)}",
            "electrocution", "en", 1,
        )

    def elec_en_t2(rng: random.Random) -> dict:
        who = _who_en(rng)
        got = "got" if who == "I" else "got"
        return _rec(
            f"{who} {got} an electric shock from a fallen power line beside "
            f"{rng.choice(LANDMARKS)} in {rng.choice(PLACES)}",
            "electrocution", "en", 2,
        )

    def elec_hi(rng: random.Random) -> dict:
        return _rec(
            f"{rng.choice(PLACES)} mein bijli ka jhatka laga live wire "
            f"{rng.choice(LANDMARKS)} ke paas",
            "electrocution", "hi", 1,
        )

    def elec_te(rng: random.Random) -> dict:
        return _rec(
            f"{rng.choice(PLACES)} lo current shock ayindi live wire "
            f"{rng.choice(LANDMARKS)} daggara",
            "electrocution", "te", 1,
        )

    def inj_en_t1(rng: random.Random) -> dict:
        variants = [
            f"I fell down near {rng.choice(LANDMARKS)} in {rng.choice(PLACES)} "
            f"and I am unable to walk after {rng.choice(HOURS)}",
            f"I slipped and cannot walk outside {_house(rng)} in {rng.choice(PLACES)}",
            f"I hurt my {rng.choice(BODY)} and cannot stand at {rng.choice(LANDMARKS)}",
            f"someone has a deep cut and is bleeding badly near {rng.choice(LANDMARKS)} "
            f"in {rng.choice(PLACES)}",
        ]
        return _rec(rng.choice(variants), "injury", "en", 1)

    def inj_en_t2(rng: random.Random) -> dict:
        who = _who_en(rng)
        return _rec(
            f"{who} twisted an ankle on the steps at {rng.choice(LANDMARKS)} in "
            f"{rng.choice(PLACES)} and cannot get to {_house(rng)}",
            "injury", "en", 2,
        )

    def inj_en_travel(rng: random.Random) -> dict:
        # Travel context without a bare bus/RTC injury keyword.
        return _rec(
            f"after getting off at {rng.choice(LANDMARKS)} in {rng.choice(PLACES)} "
            f"I fell and I am unable to walk toward {_house(rng)}",
            "injury", "en", 2,
        )

    def inj_hi(rng: random.Random) -> dict:
        return _rec(
            f"main gir gaya hoon {rng.choice(PLACES)} mein chal nahi pa raha "
            f"{rng.choice(LANDMARKS)} ke paas",
            "injury", "hi", 1,
        )

    def inj_te(rng: random.Random) -> dict:
        return _rec(
            f"{rng.choice(PLACES)} lo padipoyanu nadavaledu "
            f"{rng.choice(LANDMARKS)} daggara",
            "injury", "te", 1,
        )

    def snake_en_t1(rng: random.Random) -> dict:
        return _rec(
            f"a {rng.choice(SNAKES)} bit {rng.choice(PEOPLE).replace('I', 'me')} "
            f"near {rng.choice(LANDMARKS)} in {rng.choice(PLACES)} at {rng.choice(HOURS)}",
            "snakebite", "en", 1,
        )

    def snake_en_t2(rng: random.Random) -> dict:
        return _rec(
            f"fang marks are swelling on the {rng.choice(BODY)} after a {rng.choice(SNAKES)} "
            f"strike beside {rng.choice(LANDMARKS)} in {rng.choice(PLACES)}",
            "snakebite", "en", 2,
        )

    def snake_hi(rng: random.Random) -> dict:
        return _rec(
            f"{rng.choice(PLACES)} mein saanp ne kaat liya {rng.choice(LANDMARKS)} ke paas",
            "snakebite", "hi", 1,
        )

    def snake_te(rng: random.Random) -> dict:
        return _rec(
            f"{rng.choice(PLACES)} lo paamu kadithindi {rng.choice(LANDMARKS)} daggara",
            "snakebite", "te", 1,
        )

    def cyc_en_t1(rng: random.Random) -> dict:
        return _rec(
            f"a cyclone warning is active for {rng.choice(PLACES)} and strong winds "
            f"are hitting {rng.choice(LANDMARKS)} at {rng.choice(HOURS)}",
            "cyclone", "en", 1,
        )

    def cyc_en_t2(rng: random.Random) -> dict:
        return _rec(
            f"storm surge water is pushing into {_house(rng)} in {rng.choice(PLACES)} "
            f"while cyclonic wind tears sheets near {rng.choice(LANDMARKS)}",
            "cyclone", "en", 2,
        )

    def cyc_hi(rng: random.Random) -> dict:
        return _rec(
            f"{rng.choice(PLACES)} mein tufan aa raha hai tez hawa chal rahi hai "
            f"{rng.choice(LANDMARKS)} ke paas",
            "cyclone", "hi", 1,
        )

    def cyc_te(rng: random.Random) -> dict:
        return _rec(
            f"{rng.choice(PLACES)} lo cyclone warning vachindi gali tez ga vistundi",
            "cyclone", "te", 1,
        )

    def str_en_t1(rng: random.Random) -> dict:
        return _rec(
            f"the {rng.choice(STRUCTURES)} collapsed near {rng.choice(LANDMARKS)} in "
            f"{rng.choice(PLACES)} and people are trapped under rubble at {rng.choice(HOURS)}",
            "structural_damage", "en", 1,
        )

    def str_en_t2(rng: random.Random) -> dict:
        return _rec(
            f"{_house(rng)} in {rng.choice(PLACES)} has a spreading wall crack and the "
            f"{rng.choice(STRUCTURES)} looks ready to come down beside {rng.choice(LANDMARKS)}",
            "structural_damage", "en", 2,
        )

    def str_hi(rng: random.Random) -> dict:
        return _rec(
            f"{rng.choice(PLACES)} mein building gir gayi {rng.choice(LANDMARKS)} ke paas",
            "structural_damage", "hi", 1,
        )

    def str_te(rng: random.Random) -> dict:
        return _rec(
            f"{rng.choice(PLACES)} lo building collapse ayyindi {rng.choice(LANDMARKS)} daggara",
            "structural_damage", "te", 1,
        )

    def acc_en_t1(rng: random.Random) -> dict:
        vehicle = rng.choice(VEHICLES)
        return _rec(
            f"a {vehicle} accident on the highway near {rng.choice(PLACES)} "
            f"by {rng.choice(LANDMARKS)} at {rng.choice(HOURS)}",
            "accident", "en", 1,
        )

    def acc_en_bus(rng: random.Random) -> dict:
        return _rec(
            f"bus accident on the highway near {rng.choice(PLACES)} "
            f"close to {rng.choice(LANDMARKS)} at km {rng.choice(NUMBERS)}",
            "accident", "en", 1,
        )

    def acc_en_t2(rng: random.Random) -> dict:
        return _rec(
            f"a {rng.choice(VEHICLES)} hit a pedestrian near {rng.choice(LANDMARKS)} "
            f"in {rng.choice(PLACES)} and the vehicle overturned",
            "accident", "en", 2,
        )

    def acc_hi(rng: random.Random) -> dict:
        return _rec(
            f"{rng.choice(PLACES)} mein road pe accident ho gaya "
            f"{rng.choice(LANDMARKS)} ke paas",
            "accident", "hi", 1,
        )

    def acc_te(rng: random.Random) -> dict:
        return _rec(
            f"{rng.choice(PLACES)} lo road accident ayyindi {rng.choice(LANDMARKS)} daggara",
            "accident", "te", 1,
        )

    def unc_hist(rng: random.Random) -> dict:
        return _rec(
            f"I fell last year near {rng.choice(LANDMARKS)} in {rng.choice(PLACES)} "
            f"and it healed months ago",
            "unclassified", "en", 3,
        )

    def unc_travel(rng: random.Random) -> dict:
        return _rec(
            f"I was travelling from RTC BUS to {rng.choice(PLACES)} and looking for "
            f"{rng.choice(LANDMARKS)} around {rng.choice(HOURS)}",
            "unclassified", "en", 3,
        )

    def unc_water(rng: random.Random) -> dict:
        return _rec(
            f"please bring a water bottle to {_house(rng)} in {rng.choice(PLACES)} "
            f"near {rng.choice(LANDMARKS)}",
            "unclassified", "en", 3,
        )

    def unc_news(rng: random.Random) -> dict:
        return _rec(
            f"I saw news last week about a flood in another state not in {rng.choice(PLACES)}",
            "unclassified", "en", 3,
        )

    def unc_question(rng: random.Random) -> dict:
        return _rec(
            f"is this an emergency if my {rng.choice(BODY)} ached after walking in "
            f"{rng.choice(PLACES)} last month",
            "unclassified", "en", 3,
        )

    def unc_hi(rng: random.Random) -> dict:
        return _rec(
            f"{rng.choice(PLACES)} mein app test kar raha hoon koi accident nahi hai",
            "unclassified", "hi", 3,
        )

    def unc_te(rng: random.Random) -> dict:
        return _rec(
            f"{rng.choice(PLACES)} lo app test chestunna emergency kadu",
            "unclassified", "te", 3,
        )

    def flood_hi_t2(rng: random.Random) -> dict:
        return _rec(
            f"sadak pani mein doob gayi {rng.choice(PLACES)} mein "
            f"{rng.choice(WEATHER)} ke baad {_house(rng)}",
            "flooding", "hi", 2,
        )

    def flood_te_t2(rng: random.Random) -> dict:
        return _rec(
            f"road water lo munigindi {rng.choice(PLACES)} lo "
            f"house {rng.choice(NUMBERS)} daggara",
            "flooding", "te", 2,
        )

    def inj_hi_t2(rng: random.Random) -> dict:
        return _rec(
            f"taang mein dard hai {rng.choice(PLACES)} mein gir gaya hoon "
            f"{rng.choice(LANDMARKS)} ke paas",
            "injury", "hi", 2,
        )

    def inj_te_t2(rng: random.Random) -> dict:
        return _rec(
            f"{rng.choice(PLACES)} lo leg pain undi padipoyanu "
            f"{rng.choice(LANDMARKS)} daggara walk cheyalenu",
            "injury", "te", 2,
        )

    return [
        flood_en_t1, flood_en_t2, flood_en_t3, flood_hi, flood_te, flood_hi_t2, flood_te_t2,
        elec_en_t1, elec_en_t2, elec_hi, elec_te,
        inj_en_t1, inj_en_t2, inj_en_travel, inj_hi, inj_te, inj_hi_t2, inj_te_t2,
        snake_en_t1, snake_en_t2, snake_hi, snake_te,
        cyc_en_t1, cyc_en_t2, cyc_hi, cyc_te,
        str_en_t1, str_en_t2, str_hi, str_te,
        acc_en_t1, acc_en_bus, acc_en_t2, acc_hi, acc_te,
        unc_hist, unc_travel, unc_water, unc_news, unc_question, unc_hi, unc_te,
    ]


@dataclass
class GenerateResult:
    count: int
    path: Path
    sample_path: Path
    manifest_path: Path
    by_category: dict[str, int]
    by_language: dict[str, int]
    by_tier: dict[str, int]
    skipped_gold: int
    skipped_dup: int


def iter_unique_records(
    *,
    count: int,
    seed: int = 42,
    gold: set[str] | None = None,
) -> Iterator[dict]:
    gold = gold if gold is not None else load_gold_normalized()
    rng = random.Random(seed)
    recipes = _recipes()
    seen: set[str] = set()
    produced = 0
    attempts = 0
    max_attempts = count * 20
    while produced < count and attempts < max_attempts:
        attempts += 1
        rec = rng.choice(recipes)(rng)
        text = rec["text"]
        if rec["category"] not in CATEGORIES:
            continue
        if rec["language"] not in LANGUAGES:
            continue
        if rec["tier"] not in (1, 2, 3):
            continue
        norm = _normalize(text)
        if not norm or norm in gold:
            continue
        key = _text_key(text)
        if key in seen:
            continue
        seen.add(key)
        rec["id"] = f"syn-{produced + 1:07d}"
        produced += 1
        yield rec


def generate_dataset(
    *,
    count: int = 1_000_000,
    seed: int = 42,
    output: Path | None = None,
    sample_size: int = 200,
) -> GenerateResult:
    output = output or SYNTHETIC_TRIAGE_JSONL
    output.parent.mkdir(parents=True, exist_ok=True)
    sample_path = output.parent / "triage_synthetic_sample.jsonl"
    manifest_path = output.parent / "triage_synthetic_manifest.json"
    gold = load_gold_normalized()
    by_cat: Counter[str] = Counter()
    by_lang: Counter[str] = Counter()
    by_tier: Counter[str] = Counter()
    sample: list[dict] = []
    written = 0

    opener = gzip.open if str(output).endswith(".gz") else open
    with opener(output, "wt", encoding="utf-8") as handle:
        for rec in iter_unique_records(count=count, seed=seed, gold=gold):
            handle.write(json.dumps(rec, ensure_ascii=False) + "\n")
            by_cat[rec["category"]] += 1
            by_lang[rec["language"]] += 1
            by_tier[str(rec["tier"])] += 1
            if len(sample) < sample_size:
                sample.append(rec)
            written += 1

    if written < count:
        raise RuntimeError(f"Only produced {written} unique rows (requested {count})")

    sample_path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in sample),
        encoding="utf-8",
    )
    manifest = {
        "count": written,
        "seed": seed,
        "path": str(output),
        "label_fields": ["category", "tier"],
        "categories": CATEGORIES,
        "by_category": dict(by_cat),
        "by_language": dict(by_lang),
        "by_tier": dict(by_tier),
        "gold_holdout_excluded": True,
        "notes": (
            "Train category for the cascade ML head. "
            "tier is cascade-band metadata (1 lexicon, 2 paraphrase, 3 hard). "
            "Do not merge this file into triage_ml_training.json."
        ),
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return GenerateResult(
        count=written,
        path=output,
        sample_path=sample_path,
        manifest_path=manifest_path,
        by_category=dict(by_cat),
        by_language=dict(by_lang),
        by_tier=dict(by_tier),
        skipped_gold=0,
        skipped_dup=0,
    )


def hash_features_per_branch(n_classes: int, min_params: int = MIN_PARAMS_1M) -> int:
    """Width per hashing branch so 2-branch LR/SGD weights meet min_params."""
    if n_classes < 2:
        raise ValueError("n_classes must be >= 2")
    needed = (min_params - n_classes + (2 * n_classes) - 1) // (2 * n_classes)
    width = 1
    while width < needed:
        width *= 2
    return max(width, HASH_FEATURES_PER_BRANCH if n_classes >= 8 else width)


def hashing_feature_union(n_classes: int, min_params: int = MIN_PARAMS_1M):
    from sklearn.feature_extraction.text import HashingVectorizer
    from sklearn.pipeline import FeatureUnion

    n_features = hash_features_per_branch(n_classes, min_params)
    return FeatureUnion(
        [
            (
                "word",
                HashingVectorizer(
                    analyzer="word",
                    ngram_range=(1, 2),
                    n_features=n_features,
                    alternate_sign=False,
                    norm="l2",
                ),
            ),
            (
                "char",
                HashingVectorizer(
                    analyzer="char_wb",
                    ngram_range=(3, 5),
                    n_features=n_features,
                    alternate_sign=False,
                    norm="l2",
                ),
            ),
        ]
    )


def linear_parameter_count(clf) -> int:
    return int(clf.coef_.size + clf.intercept_.size)


def expected_parameter_count(n_classes: int, min_params: int = MIN_PARAMS_1M) -> int:
    width = hash_features_per_branch(n_classes, min_params)
    return width * 2 * n_classes + n_classes


def iter_labeled_rows(path: Path, label_field: str, limit: int | None):
    from app.services.triage_service import _normalize

    allowed = {"1", "2", "3"} if label_field == "tier" else set(CATEGORIES)
    opener = gzip.open if str(path).endswith(".gz") else open
    n = 0
    with opener(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            text = _normalize(row.get("text") or "")
            label = str(row.get(label_field) or "").strip()
            if not text or label not in allowed:
                continue
            yield text, label
            n += 1
            if limit is not None and n >= limit:
                return


def train_hashed_model(
    *,
    data_path: Path,
    label_field: str = "category",
    limit: int | None = None,
    batch_size: int = 8192,
    min_params: int = MIN_PARAMS_1M,
    model_path: Path | None = None,
) -> dict:
    import numpy as np
    from sklearn.linear_model import SGDClassifier
    from sklearn.pipeline import Pipeline
    from sklearn.utils.class_weight import compute_class_weight

    from app.ml.paths import SYNTHETIC_TRIAGE_MODEL_PATH
    from app.ml.text_classifier import save_model

    rows = list(iter_labeled_rows(data_path, label_field, limit))
    if len(rows) < 100:
        raise RuntimeError(f"Need at least 100 labeled rows, got {len(rows)}")

    labels = sorted({label for _, label in rows})
    n_classes = len(labels)
    y_all = [label for _, label in rows]
    class_names = np.array(labels)
    weights = compute_class_weight("balanced", classes=class_names, y=y_all)
    class_weight = {label: float(weight) for label, weight in zip(labels, weights)}
    union = hashing_feature_union(n_classes, min_params)
    union.fit([text for text, _ in rows[:8]])

    clf = SGDClassifier(
        loss="log_loss",
        class_weight=class_weight,
        max_iter=1,
        learning_rate="optimal",
        random_state=42,
    )
    for start in range(0, len(rows), batch_size):
        batch = rows[start : start + batch_size]
        texts = [text for text, _ in batch]
        y = [label for _, label in batch]
        X = union.transform(texts)
        if start == 0:
            clf.partial_fit(X, y, classes=labels)
        else:
            clf.partial_fit(X, y)

    params = linear_parameter_count(clf)
    if params < min_params:
        raise RuntimeError(f"Model has {params} parameters; required {min_params}")

    dest = model_path or SYNTHETIC_TRIAGE_MODEL_PATH
    dest.parent.mkdir(parents=True, exist_ok=True)
    pipeline = Pipeline([("tfidf", union), ("clf", clf)])
    save_model(
        dest,
        pipeline,
        model_name="triage_classifier_synthetic",
        training_rows=len(rows),
        classes=labels,
        extra={
            "label_field": label_field,
            "parameter_count": params,
            "expected_parameter_count": expected_parameter_count(n_classes, min_params),
            "source": str(data_path),
            "replaces_production_cascade": False,
        },
    )
    return {
        "path": str(dest),
        "training_rows": len(rows),
        "classes": labels,
        "parameter_count": params,
        "label_field": label_field,
    }
