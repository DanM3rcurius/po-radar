"""URL → Item. A readability-lite extractor: no JS, no cookies, one GET."""

from __future__ import annotations

import html
import re

import httpx

from ..models import Item
from .text import item_from_text

UA = "poradar/0.1 (+local-first influence-operation radar; no tracking)"
_BLOCK = re.compile(r"<(script|style|nav|header|footer|aside|form|noscript)[^>]*>.*?</\1>", re.S | re.I)
_TAG = re.compile(r"<[^>]+>")
_TITLE = re.compile(r"<title[^>]*>(.*?)</title>", re.S | re.I)
_P = re.compile(r"<(p|h1|h2|h3|li|blockquote)[^>]*>(.*?)</\1>", re.S | re.I)


def extract(html_text: str) -> tuple[str, str]:
    title = ""
    m = _TITLE.search(html_text)
    if m:
        title = html.unescape(_TAG.sub("", m.group(1))).strip()
    body = _BLOCK.sub(" ", html_text)
    paras = [html.unescape(_TAG.sub("", p[1])).strip() for p in _P.findall(body)]
    paras = [p for p in paras if len(p.split()) >= 4]
    if not paras:
        text = html.unescape(_TAG.sub(" ", body))
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n\s*\n+", "\n", text)
        return title, text.strip()
    return title, "\n".join(paras)


def fetch_url(url: str, timeout: float = 15.0) -> Item:
    r = httpx.get(url, timeout=timeout, follow_redirects=True, headers={"User-Agent": UA})
    r.raise_for_status()
    title, text = extract(r.text)
    return item_from_text(text, title=title, url=str(r.url), origin="url")
