from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from poradar.models import Item, LexicalSignals
from poradar.signals import cluster_signals, lexical_signals, registrable_domain

FIXTURES = Path(__file__).parent / "fixtures"
NOW = datetime(2026, 9, 21, 12, 0, tzinfo=timezone.utc)

COPYPASTA = (
    "The levy was signed behind closed doors and the people who pay for it were never "
    "asked. Every household in the district will feel it within the month. The same "
    "thing is coming to your district next, and nobody in that building will warn you."
)
UNRELATED = (
    "Growers in the Tamarind Valley reported the smallest almond harvest in a decade "
    "after a dry spring, and the cooperative said it would reduce deliveries to bakeries."
)


def fixture(name: str) -> str:
    return (FIXTURES / f"{name}.txt").read_text(encoding="utf-8")


def ago(hours: float) -> datetime:
    return NOW - timedelta(hours=hours)


def item(ident: str, text: str, domain: str, hours: float = 1.0) -> Item:
    return Item(
        id=ident,
        text=text,
        source_domain=domain,
        url=f"https://{domain}/story/{ident}",
        published=ago(hours),
    )


def lex(items: list[Item]) -> dict[str, LexicalSignals]:
    return {it.id: lexical_signals(it) for it in items}


# --- registrable domain -----------------------------------------------------


@pytest.mark.parametrize(
    "host,expected",
    [
        ("example.test", "example.test"),
        ("www.example.test", "example.test"),
        ("news.example.test", "example.test"),
        ("EXAMPLE.TEST", "example.test"),
        ("news.bbc.co.uk", "bbc.co.uk"),
        ("www.theguardian.co.uk", "theguardian.co.uk"),
        ("a.b.c.example.com.au", "example.com.au"),
        ("https://www.example.test/story/1", "example.test"),
        ("example.test:8443", "example.test"),
        ("", ""),
    ],
)
def test_registrable_domain(host, expected):
    assert registrable_domain(host) == expected


# --- the syndication carve-out ----------------------------------------------


def test_wire_copies_are_excluded_from_uniformity_and_diversity():
    """Three verbatim AP copies on three domains plus one unrelated original."""
    wire = fixture("wire_report")
    items = [
        item("ap1", wire, "alpha.test"),
        item("ap2", wire, "beta.test"),
        item("ap3", wire, "gamma.test"),
        item("own", UNRELATED, "delta.test"),
    ]
    signals = lex(items)
    assert [signals[i].attributed_syndication for i in ("ap1", "ap2", "ap3")] == [True] * 3
    assert signals["own"].attributed_syndication is False

    cluster = cluster_signals(items, signals, NOW)
    assert cluster.item_count == 4
    assert cluster.unattributed_count == 1
    # Only one unattributed voice remains: nothing to be uniform with.
    assert cluster.uniformity == 0.0
    assert cluster.source_diversity == 1.0


def test_all_wire_cluster_reports_no_uniformity():
    wire = fixture("wire_report")
    items = [item(f"w{i}", wire, f"outlet{i}.test") for i in range(3)]
    cluster = cluster_signals(items, lex(items), NOW)
    assert cluster.unattributed_count == 0
    assert cluster.uniformity == 0.0
    assert cluster.source_diversity == 1.0
    assert cluster.item_count == 3


def test_unattributed_copypasta_is_uniform():
    items = [item(f"c{i}", COPYPASTA, f"outlet{i}.test") for i in range(3)]
    cluster = cluster_signals(items, lex(items), NOW)
    assert cluster.unattributed_count == 3
    assert cluster.uniformity == pytest.approx(1.0)
    assert cluster.source_diversity == pytest.approx(1.0)


def test_same_registrable_domain_collapses_diversity():
    items = [
        item("c0", COPYPASTA, "www.outlet.test"),
        item("c1", COPYPASTA, "news.outlet.test"),
        item("c2", COPYPASTA, "other.test"),
    ]
    cluster = cluster_signals(items, lex(items), NOW)
    assert cluster.source_diversity == pytest.approx(2 / 3)


def test_wire_copies_do_not_drag_diversity_down():
    wire = fixture("wire_report")
    originals = [item("o1", COPYPASTA, "one.test"), item("o2", COPYPASTA, "two.test")]
    copies = [item(f"w{i}", wire, "one.test") for i in range(4)]
    items = originals + copies
    cluster = cluster_signals(items, lex(items), NOW)
    assert cluster.unattributed_count == 2
    assert cluster.source_diversity == pytest.approx(1.0)
    assert cluster.uniformity == pytest.approx(1.0)
    assert cluster.item_count == 6


# --- burst and edges --------------------------------------------------------


def test_burst_uses_every_item_including_wire_copies():
    wire = fixture("wire_report")
    items = [item(f"w{i}", wire, f"o{i}.test", hours=i * 0.5) for i in range(6)]
    items.append(item("own", UNRELATED, "own.test", hours=2))
    cluster = cluster_signals(items, lex(items), NOW)
    assert cluster.burst == pytest.approx(1.0)

    spread = [item(f"s{i}", UNRELATED, f"o{i}.test", hours=8 + 6 * i) for i in range(10)]
    quiet = cluster_signals(spread, lex(spread), NOW)
    assert quiet.burst == 0.0


def test_items_without_a_published_time_are_skipped_for_burst():
    items = [item("a", COPYPASTA, "one.test"), item("b", COPYPASTA, "two.test")]
    items.append(Item(id="c", text=COPYPASTA, source_domain="three.test"))
    cluster = cluster_signals(items, lex(items), NOW)
    assert cluster.burst == 0.0  # only two dated items
    assert cluster.unattributed_count == 3


def test_single_item_cluster():
    items = [item("solo", COPYPASTA, "one.test")]
    cluster = cluster_signals(items, lex(items), NOW)
    assert cluster.item_count == 1
    assert cluster.unattributed_count == 1
    assert cluster.uniformity == 0.0
    assert cluster.source_diversity == 1.0
    assert cluster.burst == 0.0


def test_empty_cluster():
    cluster = cluster_signals([], {}, NOW)
    assert cluster.item_count == 0
    assert cluster.unattributed_count == 0
    assert cluster.uniformity == 0.0
    assert cluster.source_diversity == 1.0


def test_missing_lexical_entry_is_treated_as_unattributed():
    items = [item("a", COPYPASTA, "one.test"), item("b", COPYPASTA, "two.test")]
    cluster = cluster_signals(items, {}, NOW)
    assert cluster.unattributed_count == 2
    assert cluster.uniformity == pytest.approx(1.0)


def test_domain_falls_back_to_the_url():
    items = [
        Item(id="a", text=COPYPASTA, url="https://www.one.test/a", published=ago(1)),
        Item(id="b", text=COPYPASTA, url="https://news.two.test/b", published=ago(2)),
    ]
    cluster = cluster_signals(items, lex(items), NOW)
    assert cluster.source_diversity == pytest.approx(1.0)


def test_values_stay_within_the_contract():
    items = [item(f"c{i}", COPYPASTA, "one.test", hours=i) for i in range(5)]
    cluster = cluster_signals(items, lex(items), NOW)
    for field in ("uniformity", "source_diversity", "burst"):
        assert 0.0 <= getattr(cluster, field) <= 1.0
