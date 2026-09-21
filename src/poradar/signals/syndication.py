"""Wire-service attribution detection.

Syndication is not copypasta. Twenty outlets running the same AP story are a
distribution fact, not a coordination signal, so attributed items are excluded
from ``uniformity`` and ``source_diversity`` upstream.
"""

from __future__ import annotations

import re

__all__ = ["detect_syndication", "WIRE_SOURCES"]

# Canonical name -> alternative spellings. Abbreviations are matched
# case-sensitively (so "pa" in prose is not a wire), full names case-insensitively.
WIRE_SOURCES: dict[str, tuple[str, ...]] = {
    "AP": ("AP", "Associated Press", "The Associated Press"),
    "Reuters": ("Reuters", "Thomson Reuters"),
    "AFP": ("AFP", "Agence France-Presse", "Agence France Presse"),
    "Bloomberg": ("Bloomberg", "Bloomberg News"),
    "PA": ("PA", "PA Media", "Press Association"),
    "dpa": ("dpa", "DPA", "Deutsche Presse-Agentur"),
    "UPI": ("UPI", "United Press International"),
    "ANSA": ("ANSA",),
    "EFE": ("EFE", "Agencia EFE"),
    "Kyodo": ("Kyodo", "Kyodo News"),
    "Xinhua": ("Xinhua",),
    "Yonhap": ("Yonhap",),
    "IANS": ("IANS",),
    "PTI": ("PTI", "Press Trust of India"),
    "ANI": ("ANI",),
    "TASS": ("TASS",),
    "Interfax": ("Interfax",),
    "Anadolu": ("Anadolu", "Anadolu Agency"),
    "CNN Wire": ("CNN Wire",),
}

_ABBREVIATIONS = {
    alias: canonical
    for canonical, aliases in WIRE_SOURCES.items()
    for alias in aliases
    if alias.isupper() or alias in {"dpa"}
}
_FULL_NAMES = {
    alias.lower(): canonical
    for canonical, aliases in WIRE_SOURCES.items()
    for alias in aliases
    if alias not in _ABBREVIATIONS
}

_ALL_ALIASES = sorted(
    {a for aliases in WIRE_SOURCES.values() for a in aliases}, key=len, reverse=True
)
_ALIAS_ALT = "|".join(re.escape(a) for a in _ALL_ALIASES)

_DASH = r"[—–‒-]"
_HEAD_CHARS = 400

# CITY (AP) — / CITY, Country (Reuters) - / PARIS (AFP)
_DATELINE = re.compile(
    r"^[\s\"'“]*"
    r"(?P<city>[A-Z][A-Za-z.À-ſ'’-]*(?:[ ,][A-Z][A-Za-z.À-ſ'’-]*){0,4})"
    r"\s*\(\s*(?P<wire>" + _ALIAS_ALT + r")\s*\)",
    re.MULTILINE,
)
# "(Reuters) -" anywhere in the body.
_PAREN_DASH = re.compile(r"\(\s*(?P<wire>" + _ALIAS_ALT + r")\s*\)\s*" + _DASH)
# By Jane Doe | Associated Press   /   By Jane Doe, Reuters
_BYLINE = re.compile(
    r"^\s*By\s+[^\n|,]{2,60}(?:\s*[|,—-]\s*)(?P<wire>" + _ALIAS_ALT + r")\b",
    re.IGNORECASE | re.MULTILINE,
)
# Reporting by / additional reporting for a wire.
_REPORTING = re.compile(
    r"\((?:Additional\s+)?[Rr]eporting by[^)]{0,120}\)\s*(?:[-—–]\s*)?(?P<wire>"
    + _ALIAS_ALT
    + r")?"
)
# (c) 2026 The Associated Press / Copyright Reuters / (AP) footer
_COPYRIGHT = re.compile(
    r"(?:©|\(c\)|\bCopyright\b)\s*(?:\d{4}\s*)?(?:The\s+)?(?P<wire>" + _ALIAS_ALT + r")\b",
    re.IGNORECASE,
)
# "— Reuters" / "-- AP" trailing credit on its own line.
_TRAILING_CREDIT = re.compile(
    r"^\s*(?:" + _DASH + r"|--)\s*(?:The\s+)?(?P<wire>" + _ALIAS_ALT + r")\s*\.?\s*$",
    re.MULTILINE,
)
# "Source: Reuters" / "Credit: AFP"
_SOURCE_LINE = re.compile(
    r"^\s*(?:source|credit|via|wire)\s*:\s*(?:The\s+)?(?P<wire>" + _ALIAS_ALT + r")\b",
    re.IGNORECASE | re.MULTILINE,
)


def _canonical(alias: str | None) -> str | None:
    """Map a matched alias to its canonical wire name, honouring case rules."""
    if not alias:
        return None
    alias = alias.strip()
    if alias in _ABBREVIATIONS:
        return _ABBREVIATIONS[alias]
    lowered = alias.lower()
    if lowered in _FULL_NAMES:
        return _FULL_NAMES[lowered]
    # A lowercase/oddly-cased abbreviation ("(ap)") is prose, not a wire credit.
    return None


def detect_syndication(text: str) -> tuple[bool, str | None]:
    """Detect attributed wire copy.

    Returns ``(True, canonical_source)`` when the text carries a wire dateline,
    a wire byline, a wire credit line or a wire copyright footer, else
    ``(False, None)``.
    """
    if not text or not text.strip():
        return (False, None)

    head = text[:_HEAD_CHARS]
    for pattern, scope in (
        (_DATELINE, head),
        (_BYLINE, head),
        (_PAREN_DASH, text),
        (_SOURCE_LINE, text),
        (_TRAILING_CREDIT, text),
        (_COPYRIGHT, text),
        (_REPORTING, text),
    ):
        for match in pattern.finditer(scope):
            canonical = _canonical(match.groupdict().get("wire"))
            if canonical:
                return (True, canonical)
    return (False, None)
