"""Engineered Reality Score. Deterministic; code owns every weight and cap.

Premortem rules (spec §13.4): rejected semantic weight redistributes only among
semantic terms that answered; with no accepted semantic answer the band is capped
at "watch" and the result is labeled lexical-only. Results fail closed without
evidence and falsifiers.
"""

from __future__ import annotations

from dataclasses import dataclass

from .models import (
    ClusterSignals,
    Evidence,
    LexicalSignals,
    RadarResult,
    SemanticResult,
    band_for,
)

SEMANTIC_WEIGHTS = {
    "engineered_likelihood": 0.20,
    "emotional_engineering": 0.12,
    "verifiability": 0.12,
    "pressure": 0.12,  # mean of manufactured_urgency, one_sided, tribal_signal
    "primary_source": 0.06,
}
DETERMINISTIC_WEIGHTS = {
    "uniformity": 0.14,
    "source_diversity": 0.06,
    "burst": 0.06,
    "lexical": 0.12,
}
SEMANTIC_TOTAL = sum(SEMANTIC_WEIGHTS.values())  # 0.62
DETERMINISTIC_TOTAL = sum(DETERMINISTIC_WEIGHTS.values())  # 0.38
LEXICAL_ONLY_CAP = 49.0
OPINION_CAP = 60.0
GATE_FACTOR = {"accept": 1.0, "uncertain": 0.5, "reject": 0.0}


@dataclass
class Term:
    name: str
    value: float  # normalized 0..1, higher = more engineered
    weight: float
    factor: float
    note: str


def _semantic_terms(sem: SemanticResult | None) -> list[Term]:
    if sem is None:
        return []
    a = sem.answers
    terms: list[Term] = []

    def f(qid: str) -> float:
        return GATE_FACTOR[a[qid].gate] if qid in a else 0.0

    if "engineered_likelihood" in a:
        terms.append(Term("engineered_likelihood", float(a["engineered_likelihood"].value) / 4,
                          SEMANTIC_WEIGHTS["engineered_likelihood"], f("engineered_likelihood"),
                          f"engineered_likelihood={a['engineered_likelihood'].label}"))
    if "emotional_engineering" in a:
        terms.append(Term("emotional_engineering", float(a["emotional_engineering"].value) / 4,
                          SEMANTIC_WEIGHTS["emotional_engineering"], f("emotional_engineering"),
                          f"emotional_engineering={a['emotional_engineering'].label}"))
    if "verifiability" in a:
        terms.append(Term("verifiability", 1 - float(a["verifiability"].value) / 4,
                          SEMANTIC_WEIGHTS["verifiability"], f("verifiability"),
                          f"verifiability={a['verifiability'].label}"))
    pressure_ids = [q for q in ("manufactured_urgency", "one_sided", "tribal_signal") if q in a]
    if pressure_ids:
        tot = sum(GATE_FACTOR[a[q].gate] for q in pressure_ids)
        if tot > 0:
            val = sum(float(a[q].value) * GATE_FACTOR[a[q].gate] for q in pressure_ids) / tot
        else:
            val = 0.0
        terms.append(Term("pressure", val, SEMANTIC_WEIGHTS["pressure"], tot / len(pressure_ids),
                          "pressure=" + ", ".join(f"{q}:{float(a[q].value):.2f}" for q in pressure_ids)))
    if "primary_source" in a:
        terms.append(Term("primary_source", 1 - float(a["primary_source"].value),
                          SEMANTIC_WEIGHTS["primary_source"], f("primary_source"),
                          f"primary_source p={float(a['primary_source'].value):.2f}"))
    return terms


def _deterministic_terms(lex: LexicalSignals, clu: ClusterSignals) -> list[Term]:
    return [
        Term("uniformity", clu.uniformity, DETERMINISTIC_WEIGHTS["uniformity"], 1.0,
             f"cross-source phrasing uniformity {clu.uniformity:.2f} over {clu.unattributed_count} unattributed items"),
        Term("source_diversity", 1 - clu.source_diversity, DETERMINISTIC_WEIGHTS["source_diversity"], 1.0,
             f"source diversity {clu.source_diversity:.2f}"),
        Term("burst", min(clu.burst, 1.0), DETERMINISTIC_WEIGHTS["burst"], 1.0, f"burst {clu.burst:.2f}"),
        Term("lexical", lex.composite, DETERMINISTIC_WEIGHTS["lexical"], 1.0,
             "lexical composite {:.2f} (emotion {:.2f}, absolutism {:.2f}, urgency {:.2f}, shout {:.2f}, "
             "attribution absence {:.2f}, anonymous authority {:.2f})".format(
                 lex.composite, lex.emotional_load, lex.absolutism, lex.urgency, lex.shout,
                 lex.attribution_absence, lex.authority_words)),
    ]


def _falsifiers(lex: LexicalSignals, clu: ClusterSignals, sem: SemanticResult | None) -> list[str]:
    out: list[str] = []
    if lex.attribution_absence > 0.4 or (sem and "primary_source" in sem.answers and float(sem.answers["primary_source"].value) < 0.5):
        out.append("a named primary document, record, or on-record witness would lower this")
    if clu.uniformity > 0.4:
        out.append("independent outlets using their own phrasing would lower this")
    if clu.burst > 0.5:
        out.append("a slower, organic spread across days would lower this")
    if lex.authority_words > 0.3:
        out.append("naming the experts or officials would lower this")
    if lex.urgency > 0.3 or (sem and "manufactured_urgency" in sem.answers and float(sem.answers["manufactured_urgency"].value) > 0.5):
        out.append("a stated reason why action is time-critical would lower this")
    if sem and "one_sided" in sem.answers and float(sem.answers["one_sided"].value) > 0.5:
        out.append("engaging the strongest counter-explanation would lower this")
    if not out:
        out.append("nothing specific fired; a higher score would need loaded phrasing, missing sources, or cross-outlet uniformity")
    return out


def fuse(
    *,
    item_id: str,
    narrative_id: str,
    title: str,
    lexical: LexicalSignals,
    cluster: ClusterSignals,
    semantic: SemanticResult | None,
    bank: str = "provisional",
    brief: str | None = None,
) -> RadarResult:
    sem_terms = _semantic_terms(semantic)
    det_terms = _deterministic_terms(lexical, cluster)

    sem_mass = sum(t.weight * t.factor for t in sem_terms)
    accepted = [t for t in sem_terms if t.factor >= 1.0]
    answered = [t for t in sem_terms if t.factor > 0]
    uncertain = [t for t in sem_terms if 0 < t.factor < 1.0]

    # A single item has no cluster evidence at all (not "zero uniformity"), so the deterministic
    # block renormalizes over the terms that exist; otherwise the lexical block is silently diluted.
    if cluster.item_count <= 1:
        det_live = [t for t in det_terms if t.name == "lexical"]
    else:
        det_live = det_terms
    det_score = sum(t.weight * t.value for t in det_live) / sum(t.weight for t in det_live)  # 0..1

    evidence: list[Evidence] = []
    if not accepted:
        mode = "lexical-only"
        # lexical-only: the deterministic block is all we have; scale it to its own total, cap at watch
        ers = min(100 * det_score, LEXICAL_ONLY_CAP)
        evidence.append(Evidence(signal="mode", value="lexical-only",
                                 note="no semantic answer passed the confidence gate; score capped at 'watch'"))
    else:
        sem_score = sum(t.weight * t.factor * t.value for t in sem_terms) / sem_mass  # 0..1, redistributed
        ers = 100 * (SEMANTIC_TOTAL * sem_score + DETERMINISTIC_TOTAL * det_score)
        mode = "semantic" if len(accepted) == len(sem_terms) else "semantic-partial"

    for t in det_terms:
        if t.value >= 0.25:
            evidence.append(Evidence(signal=t.name, value=round(t.value, 3), note=t.note))
    for t in answered:
        if t.value >= 0.25:
            evidence.append(Evidence(signal=t.name, value=round(t.value, 3),
                                     note=t.note + (" (uncertain, half weight)" if t.factor < 1 else "")))
    if semantic:
        for qid in ("genre", "technique", "nimmo_d"):
            if qid in semantic.answers and semantic.answers[qid].gate != "reject":
                ans = semantic.answers[qid]
                if ans.value not in ("none", "reporting", "other"):
                    evidence.append(Evidence(signal=qid, value=str(ans.value),
                                             note=f"{qid}={ans.value} (confidence {ans.confidence:.2f})"))
    if lexical.attributed_syndication:
        evidence.append(Evidence(signal="attributed_syndication", value=lexical.syndication_source or "wire",
                                 note="attributed wire copy; excluded from uniformity and diversity"))

    genre = semantic.answers["genre"].value if semantic and "genre" in semantic.answers else None
    if genre in ("opinion", "satire") and semantic.answers["genre"].gate != "reject":
        if ers > OPINION_CAP:
            ers = OPINION_CAP
            evidence.append(Evidence(signal="genre_cap", value=str(genre),
                                     note=f"{genre} is allowed to be one-sided; score capped at {OPINION_CAP:.0f}"))

    if not evidence:
        evidence.append(Evidence(signal="none", value=0.0, note="no signal reached the reporting threshold"))

    ers = max(0.0, min(100.0, round(ers, 1)))
    return RadarResult(
        item_id=item_id,
        narrative_id=narrative_id,
        title=title,
        ers=ers,
        band=band_for(ers),
        mode=mode,
        bank=bank,  # type: ignore[arg-type]
        evidence=evidence,
        falsifiers=_falsifiers(lexical, cluster, semantic),
        lexical=lexical,
        cluster=cluster,
        semantic=semantic,
        needs_review=bool(uncertain) or mode == "lexical-only",
        brief=brief,
    )
