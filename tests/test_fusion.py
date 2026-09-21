import pytest

from poradar.fusion import fuse
from poradar.models import (
    DISCLAIMER,
    ClusterSignals,
    LexicalSignals,
    RadarResult,
    SemanticAnswer,
    SemanticResult,
)


def lex(**kw):
    return LexicalSignals(**kw)


def sem(provider="jev:test", **answers):
    out = {}
    for qid, (typ, value, conf, gate) in answers.items():
        out[qid] = SemanticAnswer(qid=qid, type=typ, value=value, confidence=conf, gate=gate)
    return SemanticResult(provider=provider, answers=out)


def test_lexical_only_is_capped_at_watch_and_labeled():
    r = fuse(item_id="a", narrative_id="n", title="t",
             lexical=lex(emotional_load=1, absolutism=1, urgency=1, shout=1, attribution_absence=1, authority_words=1),
             cluster=ClusterSignals(uniformity=1.0, source_diversity=0.0, burst=1.0, item_count=9, unattributed_count=9),
             semantic=None)
    assert r.mode == "lexical-only"
    assert r.ers <= 49
    assert r.band == "watch"
    assert r.needs_review
    assert any(e.signal == "mode" for e in r.evidence)


def test_all_rejected_semantic_is_lexical_only():
    s = sem(engineered_likelihood=("score", 4.0, 0.1, "reject"), primary_source=("noul", 0.1, 0.1, "reject"))
    r = fuse(item_id="a", narrative_id="n", title="t", lexical=lex(), cluster=ClusterSignals(), semantic=s)
    assert r.mode == "lexical-only"
    assert r.band in ("quiet", "watch")


def test_rejected_weight_does_not_flow_to_lexical_terms():
    # Same lexical/cluster state; only difference: one semantic term rejected vs accepted-low.
    base = dict(item_id="a", narrative_id="n", title="t",
                lexical=lex(emotional_load=0.9, urgency=0.9, shout=0.9),
                cluster=ClusterSignals(uniformity=0.9, source_diversity=0.1, burst=0.9))
    accepted_low = sem(engineered_likelihood=("score", 0.0, 0.9, "accept"),
                       verifiability=("score", 4.0, 0.9, "accept"))
    one_rejected = sem(engineered_likelihood=("score", 0.0, 0.9, "accept"),
                       verifiability=("score", 0.0, 0.1, "reject"))
    r1 = fuse(semantic=accepted_low, **base)
    r2 = fuse(semantic=one_rejected, **base)
    # rejecting verifiability redistributes its weight to the accepted low engineered_likelihood,
    # so the semantic block stays low; the deterministic block is unchanged either way.
    assert r2.ers <= r1.ers + 0.1
    assert r2.mode == "semantic-partial"


def test_semantic_high_reaches_saturated():
    s = sem(engineered_likelihood=("score", 4.0, 0.9, "accept"), emotional_engineering=("score", 4.0, 0.9, "accept"),
            verifiability=("score", 0.0, 0.9, "accept"), manufactured_urgency=("noul", 0.95, 0.9, "accept"),
            one_sided=("noul", 0.9, 0.8, "accept"), tribal_signal=("noul", 0.9, 0.8, "accept"),
            primary_source=("noul", 0.05, 0.9, "accept"), genre=("choice", "social_post", 0.9, "accept"),
            technique=("choice", "appeal_to_fear", 0.8, "accept"))
    r = fuse(item_id="a", narrative_id="n", title="t",
             lexical=lex(emotional_load=0.9, absolutism=0.8, urgency=0.9, shout=0.7, attribution_absence=1, authority_words=0.8),
             cluster=ClusterSignals(uniformity=0.8, source_diversity=0.2, burst=1.0, item_count=6, unattributed_count=6),
             semantic=s)
    assert r.band == "saturated"
    assert r.mode == "semantic"
    assert any(e.signal == "technique" for e in r.evidence)


def test_wire_report_stays_quiet_with_semantic():
    s = sem(engineered_likelihood=("score", 0.2, 0.9, "accept"), emotional_engineering=("score", 1.0, 0.8, "accept"),
            verifiability=("score", 3.5, 0.9, "accept"), manufactured_urgency=("noul", 0.1, 0.8, "accept"),
            one_sided=("noul", 0.15, 0.7, "accept"), tribal_signal=("noul", 0.05, 0.9, "accept"),
            primary_source=("noul", 0.9, 0.8, "accept"), genre=("choice", "reporting", 0.9, "accept"))
    r = fuse(item_id="a", narrative_id="n", title="t",
             lexical=lex(emotional_load=0.7, attribution_absence=0.1, attributed_syndication=True, syndication_source="AP"),
             cluster=ClusterSignals(uniformity=0.0, source_diversity=1.0, burst=0.9, item_count=30, unattributed_count=0),
             semantic=s)
    assert r.band == "quiet"
    assert any(e.signal == "attributed_syndication" for e in r.evidence)


def test_opinion_cap():
    s = sem(engineered_likelihood=("score", 4.0, 0.9, "accept"), emotional_engineering=("score", 4.0, 0.9, "accept"),
            verifiability=("score", 0.0, 0.9, "accept"), genre=("choice", "opinion", 0.9, "accept"))
    r = fuse(item_id="a", narrative_id="n", title="t", lexical=lex(emotional_load=1, absolutism=1),
             cluster=ClusterSignals(uniformity=1.0, source_diversity=0.0, burst=1.0), semantic=s)
    assert r.ers <= 60
    assert any(e.signal == "genre_cap" for e in r.evidence)


def test_uncertain_marks_needs_review_and_half_weight():
    s_acc = sem(engineered_likelihood=("score", 4.0, 0.9, "accept"))
    s_unc = sem(engineered_likelihood=("score", 4.0, 0.5, "uncertain"))
    r_acc = fuse(item_id="a", narrative_id="n", title="t", lexical=lex(), cluster=ClusterSignals(), semantic=s_acc)
    # uncertain alone: no accepted term -> lexical-only
    r_unc = fuse(item_id="a", narrative_id="n", title="t", lexical=lex(), cluster=ClusterSignals(), semantic=s_unc)
    assert r_acc.mode == "semantic" and not r_acc.needs_review
    assert r_unc.mode == "lexical-only" and r_unc.needs_review


def test_result_fails_closed():
    with pytest.raises(ValueError):
        RadarResult(item_id="a", narrative_id="n", title="t", ers=1, band="quiet", mode="lexical-only",
                    evidence=[], falsifiers=["x"], lexical=lex(), cluster=ClusterSignals())
    with pytest.raises(ValueError):
        RadarResult(item_id="a", narrative_id="n", title="t", ers=1, band="quiet", mode="lexical-only",
                    evidence=[{"signal": "x", "value": 1, "note": "n"}], falsifiers=[], lexical=lex(),
                    cluster=ClusterSignals())
    with pytest.raises(ValueError):
        RadarResult(item_id="a", narrative_id="n", title="t", ers=1, band="quiet", mode="lexical-only",
                    evidence=[{"signal": "x", "value": 1, "note": "n"}], falsifiers=["f"], lexical=lex(),
                    cluster=ClusterSignals(), disclaimer="whatever")
    r = fuse(item_id="a", narrative_id="n", title="t", lexical=lex(), cluster=ClusterSignals(), semantic=None)
    assert r.to_json_dict()["disclaimer"] == DISCLAIMER
