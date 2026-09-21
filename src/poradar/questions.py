"""The question bank: data, not code. Loaded from questions.json (or a user override)."""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from .decisions import Question

BUNDLED = Path(__file__).with_name("questions.json")

SEMANTIC_IDS = (
    "primary_source",
    "manufactured_urgency",
    "one_sided",
    "tribal_signal",
    "genre",
    "technique",
    "nimmo_d",
    "emotional_engineering",
    "verifiability",
    "engineered_likelihood",
    # transcript-derived (NCI worksheet rows and the devil's-advocate check)
    "historical_parallel",
    "cialdini_lever",
    "loss_framing",
    "source_transparency",
    "organic_explanation_strength",
    "undefined_terms",
)
CORE_IDS = SEMANTIC_IDS[:10]


def bank_path() -> Path:
    override = os.environ.get("PORADAR_QUESTIONS")
    if override:
        return Path(override)
    home = Path(os.environ.get("PORADAR_HOME", Path.home() / ".poradar"))
    user = home / "questions.json"
    return user if user.exists() else BUNDLED


@lru_cache(maxsize=4)
def load_bank(path: str | None = None) -> dict[str, Any]:
    p = Path(path) if path else bank_path()
    with open(p, encoding="utf-8") as f:
        data = json.load(f)
    if "questions" not in data or not isinstance(data["questions"], dict):
        raise ValueError(f"{p}: expected a 'questions' object")
    for qid, q in data["questions"].items():
        Question.model_validate(q)  # raises on malformed criteria
        if qid not in SEMANTIC_IDS:
            raise ValueError(f"{p}: unknown question id {qid!r}; fusion knows only {SEMANTIC_IDS}")
    missing = [q for q in CORE_IDS if q not in data["questions"]]
    if missing:
        raise ValueError(f"{p}: missing questions {missing}")
    return data


def questions(path: str | None = None) -> dict[str, Question]:
    return {qid: Question.model_validate(q) for qid, q in load_bank(path)["questions"].items()}


def bank_status(path: str | None = None) -> str:
    v = str(load_bank(path).get("version", ""))
    return "provisional" if "provisional" in v else "reconciled"


def jev_state(title: str, source_domain: str, published: str | None, excerpt: str) -> dict[str, Any]:
    """Evidence only. Never signal numbers, never our verdict (premortem §13.3)."""
    return {
        "title": title,
        "source_domain": source_domain,
        "published": published,
        "excerpt": excerpt[:1500],
    }
