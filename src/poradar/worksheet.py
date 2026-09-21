"""NCI-style worksheet: 20 categories, 1 to 5 each, receipts on every row.

Shape follows the transcript's description of the NCI PsyOps Identification Tool v8.3 (Chase Hughes):
observable, measurable elements in the delivery of the information; 1 = not present, 5 = overwhelming
and repeated; four interpretive bands. The transcript names only some categories (timing, historical
parallels, repetition/illusory truth, loss framing, identity/tribal, Cialdini levers, source
transparency); the rest of the 20 are composed from this app's signals. Rows the text alone cannot
score are labeled "human" and scored 1 with the question the human must answer.
"""

from __future__ import annotations

from datetime import datetime

from .models import ClusterSignals, Item, LexicalSignals, SemanticResult, Worksheet, WorksheetRow
from .receipts import loss_ratio, receipts_for, repetition, timing_dump


def _s(x: float) -> int:
    """0..1 → 1..5."""
    return max(1, min(5, 1 + round(x * 4)))


def _sem(sem: SemanticResult | None, qid: str):
    if sem and qid in sem.answers and sem.answers[qid].gate != "reject":
        return sem.answers[qid]
    return None


def build(item: Item, lex: LexicalSignals, clu: ClusterSignals, sem: SemanticResult | None,
          now: datetime | None = None) -> Worksheet:
    rc = receipts_for(item.text)
    rep, rep_phrase = repetition(item.text)
    tim, tim_note = timing_dump(item.published)
    rows: list[WorksheetRow] = []

    def add(cat: str, score: int, basis: str, receipt: str | None, lower: str) -> None:
        rows.append(WorksheetRow(n=len(rows) + 1, category=cat, score=score, basis=basis,  # type: ignore[arg-type]
                                 receipt=receipt or "no evidence found in the text", lower_it=lower))

    a = _sem(sem, "emotional_engineering")
    add("Emotional hijack (amygdala / System 1 targeting)",
        _s(float(a.value) / 4) if a else _s(lex.emotional_load), "semantic" if a else "deterministic",
        rc["emotional_load"], "neutral phrasing carrying the same facts")
    add("Manufactured urgency", _s(float(_sem(sem, "manufactured_urgency").value)) if _sem(sem, "manufactured_urgency") else _s(lex.urgency),
        "semantic" if _sem(sem, "manufactured_urgency") else "deterministic", rc["urgency"], "a stated reason the timing is critical")
    add("Absolutist certainty (thought-terminating)", _s(lex.absolutism), "deterministic", rc["absolutism"], "hedged claims with stated uncertainty")
    a = _sem(sem, "loss_framing")
    add("Loss framing (prospect theory)", _s(float(a.value)) if a else _s(loss_ratio(item.text)), "semantic" if a else "deterministic",
        rc["loss_framing"], "the same numbers stated as what was kept or gained")
    a = _sem(sem, "tribal_signal")
    add("Identity / tribal framing (social identity)", _s(float(a.value)) if a else (_s(0.6) if rc["tribal"] else 1),
        "semantic" if a else "deterministic", rc["tribal"], "arguing the idea on its merits rather than who believes it")
    a = _sem(sem, "cialdini_lever")
    add("Influence lever (Cialdini)", (4 if a.value != "none" else 1) if a else 1, "semantic" if a else "human",
        f"lever={a.value}" if a else "no decider answered; look for authority, social proof, scarcity, unity", "evidence offered instead of a lever")
    add("Within-text repetition (illusory truth)", _s(rep), "deterministic", rep_phrase, "the claim made once with support")
    add("Cross-outlet uniformity (talking points)", _s(clu.uniformity), "deterministic",
        f"uniformity {clu.uniformity:.2f} over {clu.unattributed_count} unattributed items" if clu.item_count > 1 else "single item; needs the narrative's other coverage",
        "independent outlets in their own words")
    add("Source homogeneity (narrative laundering)", _s(1 - clu.source_diversity), "deterministic",
        f"source diversity {clu.source_diversity:.2f}" if clu.item_count > 1 else "single item; compare with opposing and international coverage",
        "many independent, differently aligned sources")
    add("Burst / synchronized arrival", _s(clu.burst), "deterministic",
        f"burst {clu.burst:.2f}" if clu.item_count > 1 else "single item", "a spread over days")
    add("Timing (structurally advantageous drop)", _s(tim), "deterministic", tim_note, "a publication time organic to the event")
    add("Timing coincides with a competing event", 1, "human", "does the drop coincide with a vote, ruling, or announcement it could drown out?",
        "no competing event in the window")
    a = _sem(sem, "primary_source")
    add("Missing primary source", _s(1 - float(a.value)) if a else _s(lex.attribution_absence), "semantic" if a else "deterministic",
        rc["authority_words"] or ("named source present" if lex.attribution_absence < 0.4 else None), "a named document, record, or on-record witness")
    add("Anonymous authority (experts say, officials)", _s(lex.authority_words), "deterministic", rc["authority_words"], "named experts with checkable claims")
    a = _sem(sem, "source_transparency")
    add("Source transparency (white / gray / black)", ({"white": 1, "unclear": 2, "gray": 4, "black": 5}.get(str(a.value), 2)) if a else 1,
        "semantic" if a else "human", f"{a.value}" if a else "who is openly saying this, and does the text's own content fit that origin?",
        "an openly acknowledged origin")
    a = _sem(sem, "one_sided")
    add("One-sided framing", _s(float(a.value)) if a else 1, "semantic" if a else "human", "counter-explanations engaged?" if not a else f"p={float(a.value):.2f}",
        "the strongest counter-explanation engaged")
    a = _sem(sem, "technique")
    add("Persuasion technique (SemEval taxonomy)", (4 if a.value != "none" else 1) if a else 1, "semantic" if a else "human",
        f"technique={a.value}" if a else "loaded language, fear appeal, bandwagon, whataboutism?", "plain description")
    a = _sem(sem, "historical_parallel")
    add("Historical parallel (matches a documented template)", (4 if a.value != "none" else 1) if a else 1, "semantic" if a else "human",
        f"template={a.value}" if a else "does the structure and pacing match a documented campaign?", "no known template fits")
    add("Amplification by inauthentic accounts", 1, "human", "needs platform data: account age, posting synchrony, copypasta",
        "organic account behavior")
    a = _sem(sem, "organic_explanation_strength")
    add("Devil's advocate: organic explanation fails", _s(1 - float(a.value) / 4) if a else 1, "semantic" if a else "human",
        f"organic explanation strength={a.label}" if a else "state the strongest organic reading and try to make it fit",
        "a natural organic reading of the same text")

    raw = sum(r.score for r in rows)  # 20..100
    total = round((raw - 20) * 100 / 80)
    from .models import NCI_READINGS, band_for
    return Worksheet(rows=rows, total=total, reading=NCI_READINGS[band_for(total)],
                     auto_rows=sum(1 for r in rows if r.basis != "human"),
                     human_rows=sum(1 for r in rows if r.basis == "human"))
