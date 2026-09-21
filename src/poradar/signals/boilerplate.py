"""Boilerplate stripping: cookie banners, nav menus, subscribe furniture.

Pure functions, no state. Everything upstream of shingling and lexical scoring
runs the text through :func:`strip_boilerplate` first, so that a cookie wall
never counts as a talking point and a nav menu never counts as copypasta.
"""

from __future__ import annotations

import re

__all__ = ["strip_boilerplate", "boilerplate_density", "is_boilerplate_line"]

# Phrases that mark a line (or a sentence inside a line) as page furniture.
# Kept deliberately narrow: they must not swallow article prose that happens to
# contain a word like "subscribe" or "share".
_DENYLIST = [
    # cookie / consent
    r"\bwe use cookies\b",
    r"\bthis (site|website) uses cookies\b",
    r"\bcookie (policy|settings|preferences|notice|banner|consent)\b",
    r"\b(accept|reject|allow|manage)\s+(all\s+)?cookies\b",
    r"\bmanage (your )?(consent|privacy) (preferences|settings|choices)\b",
    r"\bconsent (preferences|manager|settings)\b",
    r"\byour privacy (choices|rights|settings)\b",
    r"^\s*(accept all|reject all|allow all|got it, thanks)\b",
    r"^\s*privacy policy\b",
    r"^\s*terms (of|and) (service|use|conditions)\b",
    # subscribe / newsletter
    r"\bsubscribe (to|for|now|today)\b",
    r"\bsign up for (our|the|a)\b",
    r"\b(newsletter|briefing) sign[- ]?up\b",
    r"\bget (our|the) (free )?(newsletter|daily briefing)\b",
    r"\bcreate (a free )?account to (keep )?read\b",
    r"\balready a (subscriber|member)\b",
    # social / share furniture
    r"\bshare (this|it)\b\s*(article|story|post|page|with|on|:)?\s*$",
    r"\bshare (this|it) (article|story|post|page|video|photo)\b",
    r"\bshare on (facebook|twitter|x|whatsapp|linkedin|reddit|telegram)\b",
    r"\bfollow us on\b",
    r"\b(click|tap) here to\b",
    # more-of-this furniture
    r"^\s*read more\b",
    r"\bread more (from|about|on|here|:)\b",
    r"^\s*(related|more) (articles|stories|coverage|reading|from|on)\b",
    r"^\s*most (popular|read|viewed|shared)\b",
    r"^\s*(trending|recommended|you may also like|editor'?s picks?)\b",
    # legal / chrome
    r"\ball rights reserved\b",
    r"^\s*(©|\(c\))\s*\d{4}",
    r"^\s*copyright\s+(©\s*)?\d{4}",
    r"^\s*advertisement\b",
    r"^\s*(sponsored|promoted) (content|by|links?|story)\b",
    r"^\s*(skip to (main )?content|back to top|jump to content)\b",
    r"^\s*(sign in|sign up|log in|log out|register|subscribe|menu|search|home|"
    r"newsletter|advertisement|contact us|about us|site ?map)\s*[:|>-]?\s*$",
]

_DENY_RE = [re.compile(p, re.IGNORECASE) for p in _DENYLIST]

# A nav strip: a short line of shouted words with no sentence punctuation,
# e.g. "HOME NEWS SPORT BUSINESS" or "SECTIONS | MENU | SEARCH".
_NAV_SEPARATORS = re.compile(r"[|•·>/›»]+")
_WORD_RE = re.compile(r"[^\W\d_]+", re.UNICODE)
_TOKEN_RE = re.compile(r"[\w'\u2019-]+", re.UNICODE)
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def _is_nav_caps(line: str) -> bool:
    """True for short, punctuation-free, all-uppercase menu strips."""
    cleaned = _NAV_SEPARATORS.sub(" ", line).strip()
    if not cleaned or any(ch in cleaned for ch in ".!?"):
        return False
    words = _WORD_RE.findall(cleaned)
    if len(words) < 2 or len(words) > 8:
        return False
    return all(w.isupper() for w in words)


def is_boilerplate_line(line: str) -> bool:
    """True when a whole line is page furniture rather than article text."""
    stripped = line.strip()
    if not stripped:
        return False
    if _is_nav_caps(stripped):
        return True
    return any(rx.search(stripped) for rx in _DENY_RE)


def _is_boilerplate_sentence(sentence: str) -> bool:
    stripped = sentence.strip()
    if not stripped:
        return False
    return any(rx.search(stripped) for rx in _DENY_RE)


def strip_boilerplate(text: str) -> str:
    """Drop boilerplate lines, and boilerplate sentences inside surviving lines."""
    if not text:
        return ""
    kept: list[str] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        if _is_nav_caps(line.strip()):
            continue
        # Filter sentence by sentence so one subscribe prompt does not take the
        # paragraph it was injected into with it.
        sentences = [s for s in _SENTENCE_SPLIT.split(line.strip()) if s.strip()]
        survivors = [s for s in sentences if not _is_boilerplate_sentence(s)]
        if survivors:
            kept.append(" ".join(s.strip() for s in survivors))
    return "\n".join(kept)


def boilerplate_density(text: str) -> float:
    """Share of non-empty lines that are furniture or too short to be prose."""
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        return 0.0
    junk = 0
    for line in lines:
        if is_boilerplate_line(line) or len(_TOKEN_RE.findall(line)) < 4:
            junk += 1
    return junk / len(lines)
