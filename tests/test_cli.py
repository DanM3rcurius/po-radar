import json
import os
from pathlib import Path

from typer.testing import CliRunner

from poradar.cli import app

FIX = Path(__file__).parent / "fixtures"
runner = CliRunner()


def _env(tmp_path):
    return {"PORADAR_HOME": str(tmp_path), "PORADAR_PROVIDER": "none", "OLLAMA_HOST": "http://127.0.0.1:1"}


def test_scan_file_lexical_only(tmp_path):
    r = runner.invoke(app, ["scan", str(FIX / "outrage_bait.txt"), "--offline"], env=_env(tmp_path))
    assert r.exit_code == 0, r.output
    assert "lexical-only" in r.output
    assert "Signals to investigate" in r.output


def test_scan_json_has_evidence_and_disclaimer(tmp_path):
    r = runner.invoke(app, ["scan", str(FIX / "wire_report.txt"), "--offline", "--json", "--no-brief"], env=_env(tmp_path))
    assert r.exit_code == 0, r.output
    data = json.loads(r.output[r.output.index("{"):])
    assert data["evidence"] and data["falsifiers"]
    assert data["disclaimer"].startswith("Signals to investigate")
    assert data["band"] in ("quiet", "watch")


def test_scan_stdin_offline(tmp_path):
    text = (FIX / "opinion_column.txt").read_text()
    r = runner.invoke(app, ["scan", "-", "--offline"], input=text, env=_env(tmp_path))
    assert r.exit_code == 0, r.output


def test_scan_rejects_boilerplate(tmp_path):
    r = runner.invoke(app, ["scan", str(FIX / "boilerplate_page.txt"), "--offline"], env=_env(tmp_path))
    assert r.exit_code == 2
    assert "ingest rejected" in r.output


def test_dryrun_stub_and_questions_show(tmp_path):
    r = runner.invoke(app, ["dryrun"], env=_env(tmp_path))
    assert r.exit_code == 0, r.output
    assert "stub" in r.output
    r2 = runner.invoke(app, ["questions", "show"], env=_env(tmp_path))
    assert r2.exit_code == 0 and "engineered_likelihood" in r2.output


def test_doctor_never_prints_secret(tmp_path):
    env = _env(tmp_path) | {"OPENROUTER_API_KEY": "sk-SECRET-VALUE"}
    r = runner.invoke(app, ["doctor"], env=env)
    assert r.exit_code == 0, r.output
    assert "SECRET" not in r.output and "set" in r.output


def test_scan_save_then_report(tmp_path):
    env = _env(tmp_path)
    r = runner.invoke(app, ["scan", str(FIX / "outrage_bait.txt"), "--offline", "--save", "--no-brief"], env=env)
    assert r.exit_code == 0, r.output
    assert os.path.exists(tmp_path / "radar.sqlite")
    r2 = runner.invoke(app, ["report", "--json"], env=env)
    assert r2.exit_code == 0
    data = json.loads(r2.output[r2.output.index("{"):])
    assert len(data["results"]) == 1
