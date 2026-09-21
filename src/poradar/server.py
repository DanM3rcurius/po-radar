"""FastAPI dashboard surface: the radar screen and the JSON it eats.

The server is a thin read-only window onto ``store.py``. It never scores anything;
it hands ``RadarResult`` dicts to a single-file HTML page and burns the disclaimer
into every payload.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse

from .models import DISCLAIMER

STATIC_DIR = Path(__file__).resolve().parent / "static"
RADAR_HTML = STATIC_DIR / "radar.html"

DEFAULT_LIMIT = 200
MAX_LIMIT = 2000

ResultsLoader = Callable[[int], Sequence[dict[str, Any]]]


def load_results(limit: int = DEFAULT_LIMIT) -> list[dict[str, Any]]:
    """Read the newest results out of the local SQLite store.

    Imported lazily so the dashboard module stays importable (and testable) in
    environments where the store has not been built yet.
    """
    from .store import Store, default_db_path

    return list(Store(default_db_path()).recent(limit=limit))


def load_result(item_id: str) -> dict[str, Any] | None:
    """Read one result by item id, or ``None``."""
    from .store import Store, default_db_path

    return Store(default_db_path()).get(item_id)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def bank_of(results: Sequence[dict[str, Any]]) -> str:
    """Report ``reconciled`` only when every result says so; otherwise provisional."""
    banks = {str(r.get("bank") or "provisional") for r in results}
    if banks == {"reconciled"}:
        return "reconciled"
    return "provisional"


def read_radar_html() -> str:
    """The single-file radar screen, straight off disk (no template engine)."""
    return RADAR_HTML.read_text(encoding="utf-8")


def create_app(results_loader: ResultsLoader | None = None) -> FastAPI:
    """Build the dashboard app.

    ``results_loader`` is a ``(limit) -> list[dict]`` callable; when omitted the
    module-level :func:`load_results` is resolved at request time, so tests can
    monkeypatch ``poradar.server.load_results`` after the app is built.
    """

    def _load(limit: int) -> list[dict[str, Any]]:
        loader = results_loader if results_loader is not None else load_results
        return list(loader(limit))

    app = FastAPI(
        title="Psyop Radar",
        description=DISCLAIMER,
        version="0.1.0",
        docs_url=None,
        redoc_url=None,
    )

    @app.get("/", response_class=HTMLResponse)
    def radar_screen() -> HTMLResponse:
        if not RADAR_HTML.exists():
            raise HTTPException(status_code=500, detail="radar.html is missing from the package")
        return HTMLResponse(content=read_radar_html(), media_type="text/html")

    @app.get("/api/results")
    def api_results(
        limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    ) -> dict[str, Any]:
        results = _load(limit)
        return {
            "results": results,
            "disclaimer": DISCLAIMER,
            "bank": bank_of(results),
            "generated": _now_iso(),
        }

    @app.get("/api/results/{item_id}")
    def api_result(item_id: str) -> dict[str, Any]:
        for result in _load(MAX_LIMIT):
            if str(result.get("item_id")) == item_id:
                return {
                    "result": result,
                    "disclaimer": DISCLAIMER,
                    "bank": bank_of([result]),
                    "generated": _now_iso(),
                }
        if results_loader is None:
            try:
                found = load_result(item_id)
            except Exception:  # pragma: no cover - store absent or unreadable
                found = None
            if found is not None:
                return {
                    "result": found,
                    "disclaimer": DISCLAIMER,
                    "bank": bank_of([found]),
                    "generated": _now_iso(),
                }
        raise HTTPException(status_code=404, detail="no result with that item id")

    @app.get("/healthz")
    def healthz() -> dict[str, Any]:
        return {"status": "ok", "disclaimer": DISCLAIMER, "generated": _now_iso()}

    return app


def run(host: str = "127.0.0.1", port: int = 8642) -> None:
    """Serve the dashboard on localhost. Binding elsewhere is an explicit choice."""
    import uvicorn

    uvicorn.run(create_app(), host=host, port=port, log_level="info")
