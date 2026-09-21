from pathlib import Path

import pytest

from poradar.signals import detect_syndication

FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name: str) -> str:
    return (FIXTURES / f"{name}.txt").read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "text,expected",
    [
        ("WASHINGTON (AP) — The measure passed on Tuesday.", "AP"),
        ("LONDON (Reuters) - Shares closed lower.", "Reuters"),
        ("PARIS (AFP)\n\nThe ministers met for six hours.", "AFP"),
        ("NEW YORK (Bloomberg) — The index slipped.", "Bloomberg"),
        ("BERLIN (dpa) — The coalition agreed a budget.", "dpa"),
        ("LONDON (PA Media) — The inquiry opened.", "PA"),
        ("SAO PAULO, Brazil (Reuters) — The harvest shrank.", "Reuters"),
        ("By Jane Okoro | Associated Press\nThe vote came after midnight.", "AP"),
        ("By Jane Okoro, Reuters\nThe vote came after midnight.", "Reuters"),
        ("The court ruled on Friday. (Reuters) - Additional detail followed.", "Reuters"),
        ("Story text here.\n\n© 2026 The Associated Press. All rights reserved.", "AP"),
        ("Story text here.\n\nCopyright Reuters 2026.", "Reuters"),
        ("Story text here.\n\nSource: AFP", "AFP"),
        ("Story text here.\n\n— Reuters", "Reuters"),
    ],
)
def test_detects_wire_attribution(text, expected):
    attributed, source = detect_syndication(text)
    assert attributed is True
    assert source == expected


@pytest.mark.parametrize(
    "text",
    [
        "",
        "   \n  ",
        "The company said it would appeal the ruling on Monday.",
        "The pa system failed during the announcement and nobody could hear.",
        "He put the paper (a draft) on the desk and walked out.",
        "Reuters-watching analysts is not a dateline, and neither is this sentence.",
    ],
)
def test_no_false_positive_on_prose(text):
    assert detect_syndication(text) == (False, None)


def test_lowercase_abbreviation_is_not_a_wire_credit():
    assert detect_syndication("the pa (ap) note was informal") == (False, None)


def test_fixture_wire_report_is_attributed():
    attributed, source = detect_syndication(fixture("wire_report"))
    assert attributed is True
    assert source == "AP"


@pytest.mark.parametrize(
    "name", ["outrage_bait", "opinion_column", "press_release", "satire", "boilerplate_page"]
)
def test_non_wire_fixtures_are_not_attributed(name):
    assert detect_syndication(fixture(name)) == (False, None)
