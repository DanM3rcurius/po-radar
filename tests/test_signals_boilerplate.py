from pathlib import Path

import pytest

from poradar.signals import boilerplate_density, is_boilerplate_line, strip_boilerplate

FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name: str) -> str:
    return (FIXTURES / f"{name}.txt").read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "line",
    [
        "We use cookies and similar technologies to personalise content and ads.",
        "Accept all cookies",
        "Manage consent preferences",
        "Subscribe to our newsletter for the stories that matter.",
        "Sign up for our newsletter",
        "Share this article",
        "Share on Facebook",
        "Follow us on social media",
        "Read more: the five things to watch this week",
        "All rights reserved.",
        "© 2026 Harborton Daily",
        "Advertisement",
        "Sponsored content",
        "HOME NEWS SPORT BUSINESS CULTURE TRAVEL",
        "SECTIONS MENU SEARCH",
        "MOST POPULAR",
        "Sign in",
        "Register",
    ],
)
def test_denylist_lines_are_boilerplate(line):
    assert is_boilerplate_line(line) is True


@pytest.mark.parametrize(
    "line",
    [
        "The Harborton ferry terminal reopened on Thursday morning after a closure.",
        "Urgent: share this before it is too late, because the window closes soon.",
        "Investigators said they would read more of the maintenance file this week.",
        "The company said subscribers would be refunded within thirty days.",
        "WAKE UP! They are counting on you to scroll past this one.",
    ],
)
def test_article_prose_survives(line):
    assert is_boilerplate_line(line) is False
    assert line.strip() in strip_boilerplate(line)


def test_strip_boilerplate_keeps_only_the_article_sentences():
    stripped = strip_boilerplate(fixture("boilerplate_page"))
    assert stripped.count("\n") == 0
    assert "The Harborton ferry terminal reopened on Thursday morning" in stripped
    assert "passenger sailings would resume on a reduced timetable from Monday" in stripped
    for junk in ("cookie", "Subscribe", "Advertisement", "rights reserved", "MOST POPULAR"):
        assert junk not in stripped


def test_boilerplate_density_high_on_a_furniture_page():
    assert boilerplate_density(fixture("boilerplate_page")) > 0.5


@pytest.mark.parametrize("name", ["wire_report", "opinion_column", "outrage_bait", "satire"])
def test_boilerplate_density_low_on_real_prose(name):
    assert boilerplate_density(fixture(name)) < 0.3


def test_strip_removes_a_boilerplate_sentence_inside_a_prose_line():
    text = "The port reopened on Thursday. Sign up for our newsletter. Sailings resume Monday."
    stripped = strip_boilerplate(text)
    assert "The port reopened on Thursday." in stripped
    assert "Sailings resume Monday." in stripped
    assert "newsletter" not in stripped


def test_empty_text_is_safe():
    assert strip_boilerplate("") == ""
    assert boilerplate_density("") == 0.0
    assert boilerplate_density("\n\n  \n") == 0.0
