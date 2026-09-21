"""Dashboard surface tests: the JSON contract, and the promises the radar screen makes."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from poradar import server
from poradar.models import DISCLAIMER

ROOT = Path(__file__).resolve().parents[1]
RADAR_HTML = ROOT / "src" / "poradar" / "static" / "radar.html"
DEMO_HTML = ROOT / "docs" / "demo" / "index.html"
DEMO_JSON = ROOT / "docs" / "demo" / "sample_results.json"


def make_result(**over: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "item_id": "it-1",
        "narrative_id": "n-1",
        "title": "A test narrative about a harbor permit",
        "ers": 62.5,
        "band": "dense",
        "mode": "semantic",
        "bank": "provisional",
        "evidence": [{"signal": "uniformity", "value": 0.8, "note": "copied phrasing"}],
        "falsifiers": ["a named primary document"],
        "lexical": {"emotional_load": 0.3, "word_count": 400},
        "cluster": {"uniformity": 0.8, "source_diversity": 0.4, "burst": 0.6, "item_count": 4},
        "semantic": None,
        "needs_review": False,
        "brief": None,
        "disclaimer": DISCLAIMER,
        "generated": "2026-09-21T12:00:00+00:00",
    }
    base.update(over)
    return base


@pytest.fixture()
def results() -> list[dict[str, Any]]:
    return [
        make_result(),
        make_result(item_id="it-2", narrative_id="n-2", ers=18.0, band="quiet",
                    mode="lexical-only", semantic=None),
    ]


@pytest.fixture()
def client(results: list[dict[str, Any]]) -> TestClient:
    return TestClient(server.create_app(results_loader=lambda limit: results[:limit]))


def test_index_serves_the_radar_screen_with_the_disclaimer(client: TestClient) -> None:
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/html")
    assert DISCLAIMER in resp.text
    assert "Psyop Radar" in resp.text


def test_api_results_returns_injected_results_and_the_disclaimer(
    client: TestClient, results: list[dict[str, Any]]
) -> None:
    body = client.get("/api/results").json()
    assert body["results"] == results
    assert body["disclaimer"] == DISCLAIMER
    assert body["bank"] == "provisional"
    assert body["generated"]


def test_api_results_honors_limit(client: TestClient) -> None:
    body = client.get("/api/results", params={"limit": 1}).json()
    assert len(body["results"]) == 1


def test_bank_is_reconciled_only_when_every_result_says_so() -> None:
    reconciled = [make_result(bank="reconciled"), make_result(item_id="it-2", bank="reconciled")]
    app = server.create_app(results_loader=lambda limit: reconciled[:limit])
    assert TestClient(app).get("/api/results").json()["bank"] == "reconciled"
    mixed = [make_result(bank="reconciled"), make_result(item_id="it-2", bank="provisional")]
    app = server.create_app(results_loader=lambda limit: mixed[:limit])
    assert TestClient(app).get("/api/results").json()["bank"] == "provisional"


def test_api_single_result(client: TestClient) -> None:
    body = client.get("/api/results/it-2").json()
    assert body["result"]["narrative_id"] == "n-2"
    assert body["disclaimer"] == DISCLAIMER
    assert client.get("/api/results/nope").status_code == 404


def test_default_loader_is_resolved_at_request_time(
    monkeypatch: pytest.MonkeyPatch, results: list[dict[str, Any]]
) -> None:
    """The app is built before the store exists; tests patch the module function."""
    app = server.create_app()
    monkeypatch.setattr(server, "load_results", lambda limit: results[:limit])
    body = TestClient(app).get("/api/results").json()
    assert [r["item_id"] for r in body["results"]] == ["it-1", "it-2"]


def test_healthz(client: TestClient) -> None:
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_run_binds_localhost_by_default() -> None:
    import inspect

    sig = inspect.signature(server.run)
    assert sig.parameters["host"].default == "127.0.0.1"
    assert sig.parameters["port"].default == 8642


# --- the radar screen's own promises ------------------------------------------------

def blip_label_source() -> str:
    """The delimited blip-label section of radar.html."""
    html = RADAR_HTML.read_text(encoding="utf-8")
    match = re.search(
        r"/\* -+ BLIP LABEL.*?\*/(?P<body>.*?)/\* -+ END BLIP LABEL -+ \*/",
        html,
        re.DOTALL,
    )
    assert match, "radar.html must delimit its blip-label code path"
    return match.group("body")


def test_blip_label_function_exists() -> None:
    assert "function blipLabel(" in RADAR_HTML.read_text(encoding="utf-8")
    assert "function blipLabel(" in blip_label_source()


def test_blip_label_never_names_an_outlet() -> None:
    body = blip_label_source()
    assert "source_domain" not in body
    assert "sources" not in body
    assert ".title" in body and "falsifiers" in body


def test_blip_label_carries_title_and_top_falsifier() -> None:
    body = blip_label_source()
    assert "falsifiers[0]" in body
    assert "40" in body  # the title is truncated to 40 characters


def test_radar_html_is_self_contained_and_responsive() -> None:
    html = RADAR_HTML.read_text(encoding="utf-8")
    assert "http://" not in html.replace("http://www.w3.org/2000/svg", "")
    assert "https://" not in html
    assert "prefers-reduced-motion" in html
    assert "prefers-color-scheme: dark" in html
    assert ":root {" in html
    assert 'name="viewport"' in html
    assert "PORADAR_EMBEDDED" in html
    assert DISCLAIMER in html


def test_demo_page_embeds_the_sample_results() -> None:
    demo = DEMO_HTML.read_text(encoding="utf-8")
    assert "PORADAR_EMBEDDED" in demo
    assert "window.PORADAR_EMBEDDED = [" in demo
    assert DISCLAIMER in demo
    assert "n-grid-blackout" in demo


def test_demo_page_stays_in_sync_with_radar_html() -> None:
    def main_script(text: str) -> str:
        match = re.search(
            r'<script id="poradar-main">(?P<body>.*?)</script>', text, re.DOTALL
        )
        assert match, "the main script must be findable by id"
        return match.group("body")

    radar_main = main_script(RADAR_HTML.read_text(encoding="utf-8"))
    demo_main = main_script(DEMO_HTML.read_text(encoding="utf-8"))
    assert demo_main == radar_main


def test_sample_results_span_bands_narratives_and_modes() -> None:
    data = json.loads(DEMO_JSON.read_text(encoding="utf-8"))
    assert len(data) == 8
    assert {r["band"] for r in data} == {"quiet", "watch", "dense", "saturated"}
    assert len({r["narrative_id"] for r in data}) == 5
    modes = {r["mode"] for r in data}
    assert "lexical-only" in modes and "semantic" in modes
    for r in data:
        assert r["disclaimer"] == DISCLAIMER
        assert r["evidence"] and r["falsifiers"]
        for src in r.get("sources", []):
            assert src["domain"].endswith(".test")


def test_sample_results_validate_against_the_model() -> None:
    from poradar.models import RadarResult

    for raw in json.loads(DEMO_JSON.read_text(encoding="utf-8")):
        RadarResult.model_validate(raw)


def test_panel_renders_the_worksheet_the_reading_and_receipts() -> None:
    """The panel is the place where the whole result is shown, model fields included."""
    html = RADAR_HTML.read_text(encoding="utf-8")
    assert "function drawWorksheet(" in html
    for field in ("nci_reading", "worksheet", "lower_it", "receipt", "e.quote", "auto_rows"):
        assert field in html, field


def test_sample_results_carry_the_reading_and_one_full_worksheet() -> None:
    data = json.loads(DEMO_JSON.read_text(encoding="utf-8"))
    assert all(r["nci_reading"] for r in data)
    sheets = [r["worksheet"] for r in data if r.get("worksheet")]
    assert len(sheets) == 1
    sheet = sheets[0]
    assert len(sheet["rows"]) == 20
    assert 0 <= sheet["total"] <= 100
    assert sheet["auto_rows"] + sheet["human_rows"] == 20
