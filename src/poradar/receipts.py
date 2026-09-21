"""Receipts: the sentence or datum each signal rests on (the NCI rule: point to the specific sentence)."""

from __future__ import annotations

import re
from datetime import datetime, timezone

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

_SENT = re.compile(r"(?<=[.!?])\s+|\n+")
_vader = SentimentIntensityAnalyzer()

ABSOLUTIST = re.compile(r"\b(always|never|everyone knows|undeniabl\w*|no doubt|proven|clearly|obviously|every single|nobody|total(?:ly)?|complete(?:ly)?|absolute(?:ly)?)\b", re.I)
URGENCY = re.compile(r"\b(breaking|urgent(?:ly)?|act now|immediately|before it'?s too late|right now|wake up|last chance|emergency|warning)\b", re.I)
AUTHORITY = re.compile(r"\b(experts? (?:say|warn|agree)|officials|sources familiar|studies show|people (?:say|are saying)|many believe|critics say|insiders)\b", re.I)
LOSS = re.compile(r"\b(destroy\w*|devastat\w*|lose|lost|loss(?:es)?|wipe\w* out|kill\w*|ruin\w*|catastroph\w*|collapse|crisis|threat\w*|danger\w*|die|dead|victims?)\b", re.I)
GAIN = re.compile(r"\b(save[ds]?|saving|gain\w*|improv\w*|protect\w*|secure[ds]?|benefit\w*|keep|kept|grow\w*|win\w*|recover\w*)\b", re.I)
TRIBAL = re.compile(r"\b(they|them|these people|the elites?|globalists?|patriots?|traitors?|real (?:americans|people)|the enemy|our side|their side|us vs\.? them|sheep|shills?)\b", re.I)


ABSTRACTIONS = re.compile(r"\b(the elites?|globalists?|the establishment|the system|the regime|deep state|real (?:people|americans|citizens)|patriots?|extremists?|radicals?|woke|the media|big (?:pharma|tech)|freedom|liberty|the people|our (?:way of life|values)|the agenda|they want)\b", re.I)


def loaded_abstractions(text: str, limit: int = 6) -> list[str]:
    """Deep Truth Mode: terms the text leans on without defining. Returns distinct lowercased hits."""
    seen: list[str] = []
    for m in ABSTRACTIONS.finditer(text):
        t = m.group(0).lower()
        if t not in seen:
            seen.append(t)
        if len(seen) >= limit:
            break
    return seen


def sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENT.split(text) if len(s.split()) >= 4]


def _first_match(text: str, rx: re.Pattern) -> str | None:
    for s in sentences(text):
        if rx.search(s):
            return s[:240]
    return None


def receipts_for(text: str) -> dict[str, str | None]:
    sents = sentences(text)
    hottest = max(sents, key=lambda s: abs(_vader.polarity_scores(s)["compound"]), default=None)
    caps = next((s for s in sents if sum(1 for w in s.split() if len(w) >= 4 and w.isupper()) >= 2 or "!!" in s), None)
    return {
        "emotional_load": (hottest[:240] if hottest else None),
        "absolutism": _first_match(text, ABSOLUTIST),
        "urgency": _first_match(text, URGENCY),
        "shout": (caps[:240] if caps else None),
        "authority_words": _first_match(text, AUTHORITY),
        "loss_framing": _first_match(text, LOSS),
        "tribal": _first_match(text, TRIBAL),
    }


def repetition(text: str, n: int = 4) -> tuple[float, str | None]:
    """Within-text repetition of n-grams (illusory-truth lever). Returns (0..1, the repeated phrase)."""
    words = re.findall(r"[a-z']+", text.lower())
    if len(words) < 60:
        return 0.0, None
    grams: dict[str, int] = {}
    for i in range(len(words) - n + 1):
        g = " ".join(words[i:i + n])
        grams[g] = grams.get(g, 0) + 1
    repeated = {g: c for g, c in grams.items() if c >= 3}
    if not repeated:
        return 0.0, None
    top = max(repeated, key=repeated.get)
    share = sum(repeated.values()) / max(1, len(words) / n)
    return min(1.0, share * 3), f'"{top}" x{repeated[top]}'


def loss_ratio(text: str) -> float:
    loss, gain = len(LOSS.findall(text)), len(GAIN.findall(text))
    if loss + gain < 3:
        return 0.0
    return loss / (loss + gain)


def timing_dump(published: datetime | None) -> tuple[float, str]:
    """News-dump windows: Friday after 17:00, weekends, 22:00-05:00 (UTC unless tz-aware)."""
    if published is None:
        return 0.0, "no publication time available"
    t = published if published.tzinfo else published.replace(tzinfo=timezone.utc)
    dow, hour = t.weekday(), t.hour
    if dow == 4 and hour >= 17:
        return 0.8, f"published {t:%a %H:%M} (Friday-evening window)"
    if dow >= 5:
        return 0.6, f"published {t:%a %H:%M} (weekend)"
    if hour >= 22 or hour < 5:
        return 0.5, f"published {t:%a %H:%M} (overnight)"
    return 0.0, f"published {t:%a %H:%M} (business hours)"
