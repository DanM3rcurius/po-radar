"""RSS/Atom polling. Prefers feed-provided content over scraping (premortem §13.7)."""

from __future__ import annotations

import html
import re
from datetime import datetime, timezone
from time import mktime

import feedparser
import httpx

from ..models import Item
from .text import item_from_text
from .web import UA, extract, fetch_url

_TAG = re.compile(r"<[^>]+>")


def _published(entry) -> datetime | None:
    for key in ("published_parsed", "updated_parsed"):
        t = entry.get(key)
        if t:
            return datetime.fromtimestamp(mktime(t), tz=timezone.utc)
    return None


def _content(entry) -> str:
    if entry.get("content"):
        raw = entry["content"][0].get("value", "")
    else:
        raw = entry.get("summary", "") or entry.get("description", "")
    if "<" in raw:
        _, text = extract(raw)
        return text
    return html.unescape(raw)


def poll_feed(url: str, *, fetch_full: bool = True, min_words_for_feed_text: int = 80,
              timeout: float = 20.0) -> tuple[list[Item], str]:
    """Returns (items, status). status is 'ok' or an error string. Never raises for HTTP errors."""
    try:
        r = httpx.get(url, timeout=timeout, follow_redirects=True, headers={"User-Agent": UA})
    except Exception as e:  # network errors are health signals, not crashes
        return [], f"error: {type(e).__name__}"
    if r.status_code != 200:
        return [], f"http {r.status_code}"
    parsed = feedparser.parse(r.content)
    if parsed.bozo and not parsed.entries:
        return [], "unparseable feed"
    items: list[Item] = []
    for entry in parsed.entries[:50]:
        link = entry.get("link")
        title = html.unescape(_TAG.sub("", entry.get("title", ""))).strip()
        text = _content(entry)
        if fetch_full and link and len(text.split()) < min_words_for_feed_text:
            try:
                item = fetch_url(link)
                item.title = item.title or title
                item.origin = "feed"
                item.published = _published(entry)
                items.append(item)
                continue
            except Exception:
                pass  # fall back to whatever the feed gave us
        items.append(item_from_text(text, title=title, url=link, origin="feed", published=_published(entry)))
    return items, "ok"
