"""Golden pairs that pin the MinHash/LSH threshold."""

from pathlib import Path

import pytest

from poradar.models import Item
from poradar.signals import cluster_items, jaccard, shingles, uniformity
from poradar.signals.dedup import DEFAULT_THRESHOLD

FIXTURES = Path(__file__).parent / "fixtures"

# Same story, rewritten: roughly half of A's 3-grams survive into B.
STORY_A = (
    "The Meridian Maritime Authority said the ferry lost power at 6:12 a.m. on Tuesday "
    "and drifted into the breakwater at the mouth of the Calder Strait. Four passengers "
    "died and thirty-one were injured, the authority said. The operator suspended the "
    "route and said it would cooperate with investigators reviewing the maintenance record."
)
STORY_A_REWRITE = (
    "The Meridian Maritime Authority said the ferry lost power on Tuesday morning and "
    "drifted into the breakwater near the Calder Strait. Four passengers died and "
    "thirty-one were hurt in the collision. Calder Line Ferries suspended the route and "
    "said it would cooperate with investigators who are reviewing the maintenance record."
)
UNRELATED = (
    "Growers in the Tamarind Valley reported the smallest almond harvest in a decade "
    "after a dry spring, and the cooperative said it would reduce deliveries to bakeries "
    "in the capital. Prices at the weekend market rose for the fourth straight week."
)


def item(ident: str, text: str, domain: str = "example.test") -> Item:
    return Item(id=ident, text=text, source_domain=domain)


# --- shingles ---------------------------------------------------------------


def test_shingles_are_lowercased_word_trigrams():
    grams = shingles("The Ferry lost power.")
    assert grams == {"the ferry lost", "ferry lost power"}


def test_shingles_ignore_punctuation_and_boilerplate():
    with_junk = "Subscribe to our newsletter\nThe ferry, lost power!\nAll rights reserved."
    assert shingles(with_junk) == shingles("The ferry lost power")


def test_shingles_of_short_and_empty_text():
    assert shingles("") == set()
    assert shingles("   \n ") == set()
    assert shingles("two words") == {"two words"}


def test_shingle_size_is_configurable():
    assert shingles("a b c d", n=2) == {"a b", "b c", "c d"}
    with pytest.raises(ValueError):
        shingles("a b c", n=0)


# --- jaccard ----------------------------------------------------------------


def test_jaccard_bounds():
    assert jaccard(set(), set()) == 0.0
    assert jaccard({"a"}, set()) == 0.0
    assert jaccard({"a", "b"}, {"a", "b"}) == 1.0
    assert jaccard({"a", "b"}, {"b", "c"}) == pytest.approx(1 / 3)


# --- the pinned threshold ---------------------------------------------------


def test_rewrite_pair_sits_above_the_threshold():
    """Documents the pin: ~54% of A's trigrams survive, Jaccard 0.38 > 0.35."""
    a, b = shingles(STORY_A), shingles(STORY_A_REWRITE)
    overlap = len(a & b) / len(a)
    assert 0.45 < overlap < 0.65
    assert jaccard(a, b) == pytest.approx(0.384, abs=0.02)
    assert jaccard(a, b) > DEFAULT_THRESHOLD


def test_unrelated_pair_sits_far_below_the_threshold():
    assert jaccard(shingles(STORY_A), shingles(UNRELATED)) < 0.05


def test_rewrites_cluster_and_the_unrelated_story_does_not():
    clusters = cluster_items(
        [item("a", STORY_A), item("b", STORY_A_REWRITE), item("c", UNRELATED)]
    )
    assert [[i.id for i in c] for c in clusters] == [["a", "b"], ["c"]]


def test_verbatim_copies_cluster():
    clusters = cluster_items([item(str(i), STORY_A) for i in range(3)])
    assert [[i.id for i in c] for c in clusters] == [["0", "1", "2"]]


def test_a_higher_threshold_splits_the_rewrite_pair():
    clusters = cluster_items(
        [item("a", STORY_A), item("b", STORY_A_REWRITE)], threshold=0.6
    )
    assert [[i.id for i in c] for c in clusters] == [["a"], ["b"]]


def test_clustering_is_transitive_through_union_find():
    bridge = (
        "The Meridian Maritime Authority said the ferry lost power at 6:12 a.m. on Tuesday "
        "and drifted into the breakwater at the mouth of the Calder Strait. Four passengers "
        "died and thirty-one were hurt in the collision. Calder Line Ferries suspended the "
        "route and said it would cooperate with investigators reviewing the maintenance record."
    )
    clusters = cluster_items(
        [item("a", STORY_A), item("c", UNRELATED), item("b", STORY_A_REWRITE), item("m", bridge)]
    )
    assert [[i.id for i in c] for c in clusters] == [["a", "b", "m"], ["c"]]


def test_cluster_ordering_is_deterministic():
    items = [item("a", STORY_A), item("c", UNRELATED), item("b", STORY_A_REWRITE)]
    first = [[i.id for i in c] for c in cluster_items(items)]
    for _ in range(3):
        assert [[i.id for i in c] for c in cluster_items(items)] == first
    # Clusters come back ordered by the position of their first member.
    assert first == [["a", "b"], ["c"]]


def test_cluster_edge_cases():
    assert cluster_items([]) == []
    one = item("solo", STORY_A)
    assert cluster_items([one]) == [[one]]
    with pytest.raises(ValueError):
        cluster_items([item("a", STORY_A), item("b", STORY_A)], threshold=0.0)


def test_empty_texts_do_not_cluster_together():
    clusters = cluster_items([item("a", ""), item("b", ""), item("c", STORY_A)])
    assert [[i.id for i in c] for c in clusters] == [["a"], ["b"], ["c"]]


# --- uniformity -------------------------------------------------------------


def test_uniformity_of_verbatim_copies_is_one():
    assert uniformity([STORY_A, STORY_A]) == pytest.approx(1.0)
    assert uniformity([STORY_A, STORY_A, STORY_A]) == pytest.approx(1.0)


def test_uniformity_ignores_differing_boilerplate():
    a = "Accept all cookies\n" + STORY_A
    b = STORY_A + "\nSubscribe to our newsletter\nAll rights reserved."
    assert uniformity([a, b]) == pytest.approx(1.0)


def test_uniformity_of_fewer_than_two_texts_is_zero():
    assert uniformity([]) == 0.0
    assert uniformity([STORY_A]) == 0.0


def test_uniformity_orders_rewrites_above_unrelated_texts():
    rewrites = uniformity([STORY_A, STORY_A_REWRITE])
    mixed = uniformity([STORY_A, STORY_A_REWRITE, UNRELATED])
    assert rewrites == pytest.approx(0.384, abs=0.02)
    assert mixed < rewrites
    assert uniformity([STORY_A, UNRELATED]) < 0.05


def test_uniformity_of_distinct_real_fixtures_is_low():
    texts = [
        (FIXTURES / f"{n}.txt").read_text(encoding="utf-8")
        for n in ("wire_report", "opinion_column", "outrage_bait", "satire")
    ]
    assert uniformity(texts) < 0.05
