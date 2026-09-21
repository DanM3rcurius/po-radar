"""Deterministic signals layer: always on, zero cost, no network, no model beyond VADER."""

from __future__ import annotations

from .boilerplate import boilerplate_density, is_boilerplate_line, strip_boilerplate
from .cluster import cluster_signals, registrable_domain
from .dedup import cluster_items, jaccard, minhash, shingles, uniformity
from .lexical import (
    absolutism,
    attribution_absence,
    attribution_score,
    authority_words,
    emotional_load,
    lexical_signals,
    shout,
    split_sentences,
    urgency,
    word_count,
)
from .syndication import detect_syndication
from .temporal import burst_ratio

__all__ = [
    "absolutism",
    "attribution_absence",
    "attribution_score",
    "authority_words",
    "boilerplate_density",
    "burst_ratio",
    "cluster_items",
    "cluster_signals",
    "detect_syndication",
    "emotional_load",
    "is_boilerplate_line",
    "jaccard",
    "lexical_signals",
    "minhash",
    "registrable_domain",
    "shingles",
    "shout",
    "split_sentences",
    "strip_boilerplate",
    "uniformity",
    "urgency",
    "word_count",
]
