from pathlib import Path

import pytest

from poradar.models import Item, LexicalSignals
from poradar.signals import lexical_signals
from poradar.signals.lexical import (
    absolutism,
    attribution_absence,
    authority_words,
    emotional_load,
    shout,
    split_sentences,
    urgency,
    word_count,
)

FIXTURES = Path(__file__).parent / "fixtures"
NAMES = [
    "wire_report",
    "outrage_bait",
    "opinion_column",
    "press_release",
    "satire",
    "boilerplate_page",
]


def fixture(name: str) -> str:
    return (FIXTURES / f"{name}.txt").read_text(encoding="utf-8")


def signals(name: str) -> LexicalSignals:
    return lexical_signals(Item(id=name, text=fixture(name), source_domain=f"{name}.test"))


@pytest.fixture(scope="module")
def all_signals() -> dict[str, LexicalSignals]:
    return {name: signals(name) for name in NAMES}


# --- contract ---------------------------------------------------------------


@pytest.mark.parametrize("name", NAMES)
def test_every_field_is_normalised(name, all_signals):
    s = all_signals[name]
    for field in (
        "emotional_load",
        "absolutism",
        "urgency",
        "shout",
        "attribution_absence",
        "authority_words",
    ):
        value = getattr(s, field)
        assert 0.0 <= value <= 1.0, f"{name}.{field} = {value}"
    assert s.word_count > 0
    assert 0.0 <= s.composite <= 1.0


def test_empty_item_is_safe():
    s = lexical_signals(Item(id="empty", text=""))
    assert s == LexicalSignals()


# --- the golden contrast ----------------------------------------------------


def test_wire_report_is_attributed_and_well_sourced(all_signals):
    s = all_signals["wire_report"]
    assert s.attributed_syndication is True
    assert s.syndication_source == "AP"
    assert s.attribution_absence < 0.35
    assert s.shout < 0.1
    assert s.absolutism < 0.2


def test_outrage_bait_fires_the_manipulation_signals(all_signals):
    s = all_signals["outrage_bait"]
    assert s.attributed_syndication is False
    assert s.attribution_absence > 0.7
    assert s.urgency > 0.5
    assert s.shout > 0.3
    assert s.authority_words > 0.3
    assert s.absolutism > 0.5


def test_opinion_column_sits_between(all_signals):
    wire = all_signals["wire_report"]
    opinion = all_signals["opinion_column"]
    bait = all_signals["outrage_bait"]
    assert wire.attribution_absence < opinion.attribution_absence < bait.attribution_absence
    assert wire.composite < opinion.composite < bait.composite
    # An argued essay is not a shouted one.
    assert opinion.shout < 0.2
    assert opinion.authority_words < 0.3
    assert opinion.attributed_syndication is False


def test_press_release_is_sourced_but_unattributed_to_a_wire(all_signals):
    s = all_signals["press_release"]
    assert s.attributed_syndication is False
    assert s.attribution_absence < 0.35
    assert s.authority_words < 0.3


def test_satire_is_not_mistaken_for_a_wire(all_signals):
    s = all_signals["satire"]
    assert s.attributed_syndication is False
    assert s.shout < 0.2


# --- boilerplate is stripped before anything is counted ---------------------


def test_boilerplate_is_stripped_before_counting(all_signals):
    s = all_signals["boilerplate_page"]
    # Only the two article sentences are counted, not the 25 lines of furniture.
    assert s.word_count < 40
    assert s.word_count == word_count(
        "The Harborton ferry terminal reopened on Thursday morning after a four-day "
        "closure. The Meridian Maritime Authority said passenger sailings would resume "
        "on a reduced timetable from Monday."
    )


def test_appended_furniture_does_not_change_the_signals():
    prose = fixture("opinion_column")
    junk = "\nSubscribe to our newsletter\nAdvertisement\nShare on Facebook\nAll rights reserved.\n"
    clean = lexical_signals(Item(id="a", text=prose))
    dirty = lexical_signals(Item(id="b", text=prose + junk))
    assert clean.model_dump() == dirty.model_dump()


# --- individual signals -----------------------------------------------------


def test_split_sentences():
    assert split_sentences("One. Two! Three?") == ["One.", "Two!", "Three?"]
    assert split_sentences("") == []


def test_emotional_load_orders_neutral_below_charged():
    calm = "The committee met on Tuesday. The report was filed. The route reopened."
    hot = "This is a disgusting betrayal! It is a horrifying, evil disaster! I hate it!"
    assert emotional_load(calm) < 0.2
    assert emotional_load(hot) > 0.6
    assert emotional_load("") == 0.0


def test_absolutism_scaling_saturates_at_three_per_hundred_words():
    filler = ["alpha"] * 97
    text = " ".join(filler + ["always"] * 3)
    assert word_count(text) == 100
    assert absolutism(text, 100) == pytest.approx(1.0)
    one = " ".join(["alpha"] * 99 + ["always"])
    assert absolutism(one, 100) == pytest.approx(1 / 3)
    assert absolutism("alpha beta gamma", 3) == 0.0


def test_urgency_scaling_and_phrases():
    text = " ".join(["alpha"] * 94 + ["act", "now", "before", "it", "is", "too", "late"])
    assert urgency(text, 100) == pytest.approx(2 / 3)
    assert urgency(" ".join(["alpha"] * 100), 100) == 0.0


def test_shout_combines_caps_and_exclamations():
    assert shout("", 0) == 0.0
    quiet = " ".join(["alpha"] * 100) + "."
    assert shout(quiet, 100) == 0.0
    caps = " ".join(["SCANDAL"] * 10 + ["alpha"] * 90) + "."
    assert shout(caps, 100) == pytest.approx(0.5)
    bangs = "Wow! Amazing! Terrible!"
    assert shout(bangs, 3) == pytest.approx(0.5)


def test_shout_ignores_known_acronyms():
    text = " ".join(["NATO", "GDP", "FBI", "AP"] * 5 + ["alpha"] * 80)
    assert shout(text, 100) == 0.0


def test_attribution_credits_names_quotes_documents_and_links():
    bare = "The levy will rise. It is going to hurt. Nothing else was explained."
    assert attribution_absence(bare) > 0.9
    named = (
        "Ilse Vantorren, the authority's safety director, said the generator failed. "
        '"The crew followed the procedure as written and it did not save the ship," '
        "she told reporters. Petar Rask confirmed that divers recovered the recorder. "
        '"We handed it to the technical team on Wednesday afternoon," Rask said. '
        "According to the Meridian Maritime Authority, Report MM-2026-114 sets out "
        "the maintenance record. The full text is at https://example.test/report."
    )
    assert attribution_absence(named) < 0.2


def test_anonymous_authority_counts_only_without_a_nearby_name():
    anonymous = " ".join(["alpha"] * 96) + " Experts say the levy will rise."
    named = " ".join(["alpha"] * 92) + " Experts at the Northmark Institute say the levy rises."
    assert authority_words(anonymous, 100) > 0.0
    assert authority_words(named, 100) == 0.0
