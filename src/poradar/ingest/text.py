"""Text and file ingestion plus the ingestion-health gate (premortem §13.7)."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime
from urllib.parse import urlparse

from ..models import Item, Origin

MIN_WORDS = 40
MAX_BOILERPLATE_DENSITY = 0.6


def item_id_for(text: str, url: str | None = None) -> str:
    h = hashlib.sha256()
    h.update((url or "").encode())
    h.update(re.sub(r"\s+", " ", text.strip().lower()).encode())
    return h.hexdigest()[:16]


def domain_of(url: str | None) -> str:
    if not url:
        return ""
    host = urlparse(url).netloc.lower()
    return host[4:] if host.startswith("www.") else host


def item_from_text(
    text: str,
    *,
    title: str = "",
    url: str | None = None,
    origin: Origin = "file",
    published: datetime | None = None,
) -> Item:
    from ..signals.boilerplate import boilerplate_density, strip_boilerplate

    clean = strip_boilerplate(text)
    words = len(clean.split())
    rejected, reason = False, None
    if words < MIN_WORDS:
        rejected, reason = True, f"too short after boilerplate removal ({words} words < {MIN_WORDS})"
    else:
        dens = boilerplate_density(text)
        if dens > MAX_BOILERPLATE_DENSITY:
            rejected, reason = True, f"boilerplate density {dens:.2f} > {MAX_BOILERPLATE_DENSITY}"
    if not title:
        first = clean.strip().split("\n", 1)[0]
        title = first[:120]
    return Item(
        id=item_id_for(clean, url),
        title=title,
        text=clean,
        source_domain=domain_of(url),
        url=url,
        published=published,
        origin=origin,
        ingest_rejected=rejected,
        ingest_reason=reason,
    )
