"""Local SQLite persistence. Nothing leaves the machine from here."""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
  id TEXT PRIMARY KEY, title TEXT, text TEXT, source_domain TEXT, url TEXT,
  published TEXT, fetched TEXT, origin TEXT, ingest_rejected INTEGER, ingest_reason TEXT
);
CREATE TABLE IF NOT EXISTS results (
  item_id TEXT PRIMARY KEY, narrative_id TEXT, ers REAL, band TEXT, mode TEXT,
  generated TEXT, payload TEXT
);
CREATE TABLE IF NOT EXISTS feeds (
  url TEXT PRIMARY KEY, last_success TEXT, last_status TEXT, consecutive_failures INTEGER DEFAULT 0,
  items_total INTEGER DEFAULT 0, dead INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, payload TEXT, created TEXT);
"""


def home_dir() -> Path:
    p = Path(os.environ.get("PORADAR_HOME", Path.home() / ".poradar"))
    p.mkdir(parents=True, exist_ok=True)
    return p


def default_db_path() -> Path:
    return home_dir() / "radar.sqlite"


class Store:
    def __init__(self, path: Path | str | None = None) -> None:
        self.path = Path(path) if path else default_db_path()
        self.conn = sqlite3.connect(str(self.path))
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)

    # items
    def put_item(self, item: dict[str, Any]) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO items VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                item["id"], item.get("title", ""), item["text"], item.get("source_domain", ""),
                item.get("url"), item.get("published"), item.get("fetched"), item.get("origin", "file"),
                int(bool(item.get("ingest_rejected"))), item.get("ingest_reason"),
            ),
        )
        self.conn.commit()

    def has_item(self, item_id: str) -> bool:
        return self.conn.execute("SELECT 1 FROM items WHERE id=?", (item_id,)).fetchone() is not None

    def items(self, limit: int = 500, include_rejected: bool = False) -> list[dict[str, Any]]:
        q = "SELECT * FROM items" + ("" if include_rejected else " WHERE ingest_rejected=0")
        q += " ORDER BY COALESCE(published, fetched) DESC LIMIT ?"
        return [dict(r) for r in self.conn.execute(q, (limit,))]

    # results
    def put_result(self, result: dict[str, Any]) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO results VALUES (?,?,?,?,?,?,?)",
            (
                result["item_id"], result["narrative_id"], result["ers"], result["band"], result["mode"],
                result.get("generated") or datetime.now(timezone.utc).isoformat(), json.dumps(result),
            ),
        )
        self.conn.commit()

    def recent(self, limit: int = 200) -> list[dict[str, Any]]:
        rows = self.conn.execute("SELECT payload FROM results ORDER BY generated DESC LIMIT ?", (limit,))
        return [json.loads(r["payload"]) for r in rows]

    def get(self, item_id: str) -> dict[str, Any] | None:
        r = self.conn.execute("SELECT payload FROM results WHERE item_id=?", (item_id,)).fetchone()
        return json.loads(r["payload"]) if r else None

    # feeds
    def feed_ok(self, url: str, new_items: int) -> None:
        self.conn.execute(
            "INSERT INTO feeds(url,last_success,last_status,consecutive_failures,items_total,dead) "
            "VALUES(?,?,?,0,?,0) ON CONFLICT(url) DO UPDATE SET last_success=excluded.last_success, "
            "last_status='ok', consecutive_failures=0, items_total=items_total+excluded.items_total, dead=0",
            (url, datetime.now(timezone.utc).isoformat(), new_items),
        )
        self.conn.commit()

    def feed_fail(self, url: str, status: str, dead_after: int = 5) -> None:
        self.conn.execute(
            "INSERT INTO feeds(url,last_status,consecutive_failures) VALUES(?,?,1) "
            "ON CONFLICT(url) DO UPDATE SET last_status=excluded.last_status, "
            "consecutive_failures=consecutive_failures+1",
            (url, status),
        )
        self.conn.execute("UPDATE feeds SET dead=1 WHERE url=? AND consecutive_failures>=?", (url, dead_after))
        self.conn.commit()

    def feeds(self) -> list[dict[str, Any]]:
        return [dict(r) for r in self.conn.execute("SELECT * FROM feeds ORDER BY url")]

    # cache
    def cache_get(self, key: str) -> dict[str, Any] | None:
        r = self.conn.execute("SELECT payload FROM cache WHERE key=?", (key,)).fetchone()
        return json.loads(r["payload"]) if r else None

    def cache_put(self, key: str, payload: dict[str, Any]) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO cache VALUES (?,?,?)",
            (key, json.dumps(payload), datetime.now(timezone.utc).isoformat()),
        )
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()
