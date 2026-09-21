"""Per-item deterministic lexical signals, each normalized to [0, 1].

These are crude proxies by design: they are cheap, explainable, always on, and
sufficient for a degraded-mode score when no semantic provider is reachable.
"""

from __future__ import annotations

import re
from functools import lru_cache

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from ..models import Item, LexicalSignals
from .boilerplate import strip_boilerplate
from .syndication import detect_syndication

__all__ = ["lexical_signals", "split_sentences", "word_count"]

# --- tokenisation -----------------------------------------------------------

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?…])[\"'”’)]*\s+|\n+")
_WORD_RE = re.compile(r"[\w'’-]+", re.UNICODE)
_ALPHA_WORD_RE = re.compile(r"[^\W\d_]+", re.UNICODE)

# Acronyms that are legitimately upper case and must not count as shouting.
_ACRONYMS = frozenset(
    """AP UPI PA DPA AFP US USA UK EU UN NATO FBI CIA NSA GDP CEO CFO CTO COVID
    WHO IMF OPEC NASA FDA EPA IRS DOJ DHS ICE GOP NHS BBC CNN NPR PBS AFL CIO
    SEC FTC FCC NATO ASEAN BRICS OECD IPCC UNICEF UNESCO NGO PDF URL HTTP AI
    GPS DNA HIV AIDS PTSD ICU ER TV RADAR SONAR LASER MP MPS TD TDS""".split()
)

# --- term lexicons ----------------------------------------------------------

ABSOLUTIST_TERMS = (
    "always",
    "never",
    "everyone knows",
    "undeniable",
    "undeniably",
    "no doubt",
    "proven",
    "clearly",
    "obviously",
    "every single",
    "nobody",
    "no one",
    "total",
    "totally",
    "complete",
    "completely",
    "absolute",
    "absolutely",
    "without question",
    "irrefutable",
)

URGENCY_TERMS = (
    "breaking",
    "urgent",
    "urgently",
    "act now",
    "immediately",
    "before it's too late",
    "before it is too late",
    "right now",
    "wake up",
    "last chance",
    "emergency",
    "must",
    "warning",
    "don't wait",
    "do not wait",
    "running out of time",
)

AUTHORITY_PHRASES = (
    r"experts?\s+(?:say|said|warn|warned|agree|believe|note|caution)",
    r"(?:top|senior|government|state|local)?\s*officials?\s+"
    r"(?:say|said|told|warn|warned|confirm|confirmed|believe|deny|denied|will|are|have)",
    r"sources?\s+(?:familiar|close to|say|said|tell|told|confirm|confirmed)",
    r"studies\s+(?:show|showed|suggest|suggested|find|found|prove)",
    r"research\s+(?:shows|suggests|proves)",
    r"(?:some\s+|many\s+)?people\s+(?:say|are saying|believe|think|know)",
    r"many\s+(?:believe|say|think|worry|fear)",
    r"critics?\s+(?:say|said|argue|argued|warn|warned|call|called)",
    r"insiders?\s+(?:say|said|tell|told|report|reported|confirm|confirmed)",
    r"analysts?\s+(?:say|said|warn|warned|believe)",
    r"observers?\s+(?:say|said|note|noted|believe)",
    r"it is (?:widely )?(?:believed|understood|reported|said)",
    r"word (?:is|on the street)",
)

# Generic collective nouns that are NOT a named entity for attribution purposes.
_GENERIC_SUBJECTS = frozenset(
    """experts expert officials official sources source critics critic insiders
    insider studies study people analysts analyst observers observer many some
    others they we you it he she reports report rumors rumours everyone anyone
    nobody someone authorities pundits commentators""".split()
)

_ATTRIBUTION_VERBS = (
    r"said|says|told|tells|reported|reports|announced|announces|confirmed|confirms|"
    r"testified|wrote|writes|stated|states|acknowledged|declared|explained|added|"
    r"disclosed|published|released|ruled|found"
)

# "Ilse Vantorren said" / "Ilse Vantorren, the safety director, said"
_ENTITY_VERB = re.compile(
    r"\b(?P<entity>(?:[A-Z][\w.'’-]+)(?:\s+(?:of|for|the|de|van|von|al)\s+)?"
    r"(?:\s*[A-Z][\w.'’-]+){0,4})"
    r"(?:,[^,.;:!?]{2,70},)?\s+(?:" + _ATTRIBUTION_VERBS + r")\b"
)
# "said Ilse Vantorren" / "according to the Meridian Maritime Authority"
_VERB_ENTITY = re.compile(
    r"\b(?:said|told|according to|reported by|per)\s+(?:the\s+)?"
    r"(?P<entity>[A-Z][\w.'’-]+(?:\s+[A-Z][\w.'’-]+){0,4})"
)
_IN_A_STATEMENT = re.compile(r"\bin (?:a|an|its|their|his|her) (?:written )?statement\b", re.I)

_QUOTE_RE = re.compile(r"[\"“]([^\"“”]{10,600})[\"”]")
_DOC_WORDS = (
    r"report|reports|document|documents|record|records|filing|filings|affidavit|"
    r"indictment|transcript|dataset|data|study|studies|memo|memos|audit|survey|"
    r"court|ruling|testimony|invoice|contract|plan|summary|minutes|inspection"
)
_DOC_REF = re.compile(
    r"\b(?:" + _DOC_WORDS + r")\b[^.;:!?\n]{0,60}?"
    r"(?:\b[A-Z][\w.'’-]{2,}\b|\b\d{2,}\b|\b[A-Z]{2,}[-\d][\w-]*\b)"
    r"|(?:\b[A-Z][\w.'’-]{2,}\b|\b\d{4}\b)[^.;:!?\n]{0,40}?\b(?:" + _DOC_WORDS + r")\b"
)
_LINK_RE = re.compile(r"https?://\S+")
_SENT_END = re.compile(r"[.!?…\n]")
_CAP_TOKEN = re.compile(r"^[A-Z][\w'’-]{2,}$")

# Capitalised words that carry no naming force (sentence openers, pronouns).
_WEAK_CAPS = frozenset(
    """The They This That These Those There Their It Its We You Our But And For Nor
    Yet So If When While After Before Because Although However Meanwhile Still
    Now Today Yesterday Tomorrow Every Each Many Some Most All None Not One Two
    Three Four Five Six Seven Eight Nine Ten Also Even Only Just Here What Who
    Why How Where Which Whether Officials Experts Sources Critics Insiders People
    Studies Analysts Observers Authorities Nobody Everyone Someone Anyone""".split()
)


@lru_cache(maxsize=1)
def _analyzer() -> SentimentIntensityAnalyzer:
    """VADER is the only model we load, once, lazily."""
    return SentimentIntensityAnalyzer()


def split_sentences(text: str) -> list[str]:
    """Cheap sentence splitter; good enough for rates and means."""
    return [s.strip() for s in _SENTENCE_SPLIT.split(text or "") if s and s.strip()]


def word_count(text: str) -> int:
    return len(_WORD_RE.findall(text or ""))


def _term_pattern(terms: tuple[str, ...]) -> re.Pattern[str]:
    alts = []
    for term in sorted(terms, key=len, reverse=True):
        escaped = re.escape(term).replace(r"\'", r"['’]")
        escaped = escaped.replace(r"\ ", r"\s+")
        alts.append(escaped)
    return re.compile(r"\b(?:" + "|".join(alts) + r")\b", re.IGNORECASE)


_ABSOLUTIST_RE = _term_pattern(ABSOLUTIST_TERMS)
_URGENCY_RE = _term_pattern(URGENCY_TERMS)
_AUTHORITY_RE = re.compile(r"\b(?:" + "|".join(AUTHORITY_PHRASES) + r")", re.IGNORECASE)


def _clamp(value: float) -> float:
    return 0.0 if value < 0.0 else (1.0 if value > 1.0 else value)


def _rate_per_100(count: int, words: int) -> float:
    return 100.0 * count / words if words else 0.0


def emotional_load(text: str) -> float:
    """Mean |VADER compound| over sentences, blended with the hot-sentence share."""
    sentences = split_sentences(text)
    if not sentences:
        return 0.0
    analyzer = _analyzer()
    scores = [abs(analyzer.polarity_scores(s)["compound"]) for s in sentences]
    mean_abs = sum(scores) / len(scores)
    hot_share = sum(1 for s in scores if s > 0.5) / len(scores)
    return _clamp(0.6 * mean_abs + 0.4 * hot_share)


def absolutism(text: str, words: int) -> float:
    """Absolutist terms per 100 words; 3 per 100 saturates."""
    return _clamp(_rate_per_100(len(_ABSOLUTIST_RE.findall(text)), words) / 3.0)


def urgency(text: str, words: int) -> float:
    """Urgency terms per 100 words; 3 per 100 saturates."""
    return _clamp(_rate_per_100(len(_URGENCY_RE.findall(text)), words) / 3.0)


def shout(text: str, words: int) -> float:
    """Half caps-word ratio (x10, capped), half exclamations per sentence (capped)."""
    if not words:
        return 0.0
    caps = 0
    for token in _WORD_RE.findall(text):
        letters = _ALPHA_WORD_RE.findall(token)
        word = "".join(letters)
        if len(word) >= 4 and word.isupper() and word not in _ACRONYMS:
            caps += 1
    caps_part = _clamp((caps / words) * 10.0)
    sentences = split_sentences(text)
    bangs = text.count("!")
    bang_part = _clamp(bangs / len(sentences)) if sentences else 0.0
    return _clamp(0.5 * caps_part + 0.5 * bang_part)


def _named_attributions(text: str) -> int:
    """Count entity+attribution-verb patterns with a genuinely named subject."""
    found = 0
    seen: set[int] = set()
    for rx in (_ENTITY_VERB, _VERB_ENTITY):
        for match in rx.finditer(text):
            entity = match.group("entity").strip()
            head = entity.split()[0] if entity.split() else ""
            if head.lower() in _GENERIC_SUBJECTS:
                continue
            if len(entity.split()) == 1 and head in _WEAK_CAPS:
                continue
            if match.start() in seen:
                continue
            seen.add(match.start())
            found += 1
    found += len(_IN_A_STATEMENT.findall(text))
    return found


def _long_quotes(text: str) -> int:
    return sum(1 for q in _QUOTE_RE.findall(text) if len(_WORD_RE.findall(q)) >= 6)


def attribution_score(text: str) -> float:
    """Credit for verifiability: named attribution, quotes, documents, links."""
    named = min(0.40, 0.12 * _named_attributions(text))
    quotes = min(0.30, 0.15 * _long_quotes(text))
    documents = min(0.20, 0.10 * len(_DOC_REF.findall(text)))
    links = min(0.15, 0.15 * len(_LINK_RE.findall(text)))
    return _clamp(named + quotes + documents + links)


def attribution_absence(text: str) -> float:
    return _clamp(1.0 - attribution_score(text))


def _has_named_entity_ahead(text: str, start: int, window: int = 8) -> bool:
    """True if a proper noun appears within `window` words after `start`, same sentence."""
    tail = text[start : start + 400]
    end = _SENT_END.search(tail)
    if end:
        tail = tail[: end.start()]
    for token in _WORD_RE.findall(tail)[:window]:
        if token in _ACRONYMS and len(token) >= 2:
            return True
        if _CAP_TOKEN.match(token) and token not in _WEAK_CAPS and not token.isupper():
            return True
    return False


def authority_words(text: str, words: int) -> float:
    """Anonymous-authority phrases with no named entity nearby; 2 per 100 saturates."""
    count = 0
    for match in _AUTHORITY_RE.finditer(text):
        if not _has_named_entity_ahead(text, match.end()):
            count += 1
    return _clamp(_rate_per_100(count, words) / 2.0)


def lexical_signals(item: Item) -> LexicalSignals:
    """Compute every per-item lexical signal for one Item."""
    raw = item.text or ""
    attributed, source = detect_syndication(raw)
    text = strip_boilerplate(raw)
    words = word_count(text)
    if not words:
        # No prose survived: report no evidence rather than maximal absence.
        return LexicalSignals(
            attributed_syndication=attributed, syndication_source=source, word_count=0
        )
    return LexicalSignals(
        emotional_load=emotional_load(text),
        absolutism=absolutism(text, words),
        urgency=urgency(text, words),
        shout=shout(text, words),
        attribution_absence=attribution_absence(text),
        authority_words=authority_words(text, words),
        attributed_syndication=attributed,
        syndication_source=source,
        word_count=words,
    )
