"""Shared data contract for Psyop Radar. Every module speaks these shapes."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

DISCLAIMER = "Signals to investigate, not an attribution of intent or actor."

Band = Literal["quiet", "watch", "dense", "saturated"]
Mode = Literal["lexical-only", "semantic", "semantic-partial"]
Origin = Literal["stdin", "file", "url", "feed"]


class Item(BaseModel):
    """One ingested text: an article, post, or pasted document."""

    id: str
    title: str = ""
    text: str
    source_domain: str = ""
    url: str | None = None
    published: datetime | None = None
    fetched: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    origin: Origin = "file"
    ingest_rejected: bool = False
    ingest_reason: str | None = None

    @property
    def excerpt(self) -> str:
        return self.text[:1500]


class LexicalSignals(BaseModel):
    """Per-item deterministic signals, each normalized to [0, 1]."""

    emotional_load: float = 0.0
    absolutism: float = 0.0
    urgency: float = 0.0
    shout: float = 0.0
    attribution_absence: float = 0.0
    authority_words: float = 0.0
    attributed_syndication: bool = False
    syndication_source: str | None = None
    word_count: int = 0

    @property
    def composite(self) -> float:
        vals = [
            self.emotional_load,
            self.absolutism,
            self.urgency,
            self.shout,
            self.attribution_absence,
            self.authority_words,
        ]
        return sum(vals) / len(vals)


class ClusterSignals(BaseModel):
    """Per-narrative deterministic signals, each in [0, 1]. Absent for single items."""

    uniformity: float = 0.0
    source_diversity: float = 1.0
    burst: float = 0.0
    item_count: int = 1
    unattributed_count: int = 1


class SemanticAnswer(BaseModel):
    """One gated answer from a decision provider."""

    qid: str
    type: Literal["noul", "choice", "score"]
    value: float | str
    confidence: float
    gate: Literal["accept", "uncertain", "reject"]
    probabilities: dict[str, float] = Field(default_factory=dict)
    label: str | None = None


class SemanticResult(BaseModel):
    provider: str
    answers: dict[str, SemanticAnswer] = Field(default_factory=dict)
    egress: str = "none"
    latency_ms: int = 0
    cached: bool = False


class Evidence(BaseModel):
    signal: str
    value: float | str
    note: str
    quote: str | None = None  # the receipt: the sentence or datum this rests on


class WorksheetRow(BaseModel):
    """One NCI-style category: 1 = not present, 5 = overwhelmingly present."""

    n: int
    category: str
    score: int = Field(ge=1, le=5)
    basis: Literal["deterministic", "semantic", "human"]
    receipt: str
    lower_it: str  # what evidence would drop this row toward 1


class Worksheet(BaseModel):
    """20 categories x 1..5 = 20..100, rescaled to 0..100 so 'all absent' reads 0 (NCI v8.3 shape)."""

    rows: list[WorksheetRow]
    total: int = Field(ge=0, le=100)
    reading: str
    auto_rows: int
    human_rows: int


class RadarResult(BaseModel):
    """The only shape that leaves the pipeline. Fails closed without evidence and falsifiers."""

    item_id: str
    narrative_id: str
    title: str
    ers: float = Field(ge=0.0, le=100.0)
    band: Band
    mode: Mode
    bank: Literal["provisional", "reconciled"] = "provisional"
    evidence: list[Evidence]
    falsifiers: list[str]
    lexical: LexicalSignals
    cluster: ClusterSignals
    semantic: SemanticResult | None = None
    needs_review: bool = False
    brief: str | None = None
    worksheet: Worksheet | None = None
    nci_reading: str = ""
    define_first: list[str] = Field(default_factory=list)  # Deep Truth Mode: terms to define before arguing
    disclaimer: str = DISCLAIMER
    generated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @model_validator(mode="after")
    def _fail_closed(self) -> "RadarResult":
        if not self.evidence:
            raise ValueError("a result must carry evidence")
        if not self.falsifiers:
            raise ValueError("a result must carry falsifiers")
        if self.disclaimer != DISCLAIMER:
            raise ValueError("the disclaimer is not optional")
        if not self.nci_reading:
            self.nci_reading = NCI_READINGS[self.band]
        return self

    def to_json_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


NCI_READINGS: dict[Band, str] = {
    "quiet": "0-25: low probability of an engineered operation; likely organic",
    "watch": "26-50: moderate; consistent with ordinary media sensationalism or spin",
    "dense": "51-75: strong engineered elements; anomalies too frequent to be coincidental",
    "saturated": "76-100: overwhelming coordination indicator; verify with conflicting sources before acting",
}


def band_for(ers: float) -> Band:
    if ers <= 25:
        return "quiet"
    if ers <= 50:
        return "watch"
    if ers <= 75:
        return "dense"
    return "saturated"
