"""The forensic brief: the writer role. A local generative model if present, else a template.

The brief never changes the score. It explains, steel-mans the organic reading, and says what to check.
"""

from __future__ import annotations

import os

import httpx

from .decisions.ollama import DEFAULT_MODEL, ollama_url, reachable
from .models import RadarResult

BRIEF_SYSTEM = (
    "You write short forensic reads of news items for a careful reader. Evidence and first principles over "
    "emotion or authority. Never name or guess who is behind a narrative. Structure: (1) what the text claims, "
    "(2) which signals fired and why they matter, (3) the strongest steel-man for the organic explanation, "
    "(4) what to check next. Plain prose, under 180 words, no headings."
)


def template_brief(r: RadarResult) -> str:
    fired = [e for e in r.evidence if e.signal not in ("mode", "none")]
    lines = [f"Read: {r.title or r.item_id}. Signal density {r.band} (ERS {r.ers:.0f}), mode {r.mode}."]
    if fired:
        lines.append("What fired: " + "; ".join(e.note for e in fired[:6]) + ".")
    else:
        lines.append("Nothing reached the reporting threshold.")
    if r.mode == "lexical-only":
        lines.append("Only surface signals were available; no semantic judgment was made, so treat this as a triage cue.")
    if r.define_first:
        lines.append("Define first (Deep Truth Mode): " + ", ".join(r.define_first) + "; until these terms are pinned down, the argument cannot be evaluated.")
    lines.append("Steel-man: serious organic news is often urgent, emotional, and widely syndicated; none of that alone is engineering.")
    lines.append("If this is later debunked, expect the continued influence effect: log the entry with today's date so the retraction is on record.")
    lines.append("Check next: " + "; ".join(r.falsifiers[:3]) + ".")
    lines.append(r.disclaimer)
    return " ".join(lines)


def ollama_brief(r: RadarResult, excerpt: str, model: str | None = None, timeout: float = 120.0) -> str | None:
    url = ollama_url()
    if not reachable(url):
        return None
    user = (
        f"TITLE: {r.title}\nEXCERPT: {excerpt[:1500]}\n\nSIGNALS: "
        + "; ".join(f"{e.signal}={e.value} ({e.note})" for e in r.evidence)
        + "\nFALSIFIERS: " + "; ".join(r.falsifiers)
        + f"\nBAND: {r.band} (ERS {r.ers:.0f}, mode {r.mode})"
    )
    body = {
        "model": model or os.environ.get("PORADAR_BRIEF_MODEL", os.environ.get("PORADAR_OLLAMA_MODEL", DEFAULT_MODEL)),
        "stream": False,
        "options": {"temperature": 0.3},
        "messages": [{"role": "system", "content": BRIEF_SYSTEM}, {"role": "user", "content": user}],
    }
    try:
        resp = httpx.post(url + "/api/chat", json=body, timeout=timeout)
        resp.raise_for_status()
        text = resp.json().get("message", {}).get("content", "").strip()
        return (text + "\n" + r.disclaimer) if text else None
    except Exception:
        return None


def write_brief(r: RadarResult, excerpt: str, *, use_local_model: bool = True) -> str:
    if use_local_model:
        out = ollama_brief(r, excerpt)
        if out:
            return out
    return template_brief(r)
