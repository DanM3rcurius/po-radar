import json

import httpx
import pytest
import respx

from poradar.decisions import DecisionRequest, choice, noul, score
from poradar.decisions.ollama import OllamaProvider, parse_answers, schema_for
from poradar.decisions.router import select
from poradar.decisions.stub import StubProvider
from poradar.models import Item
from poradar.semantic import evaluate_item
from poradar.store import Store


def test_default_is_local_even_with_key_present():
    r = select(env={"OPENROUTER_API_KEY": "k"}, probe=lambda url: False)
    assert r.provider is None and r.egress == "none"
    assert "lexical-only" in r.reason


def test_cloud_requires_consent_and_key():
    r = select(cloud=True, env={"OPENROUTER_API_KEY": "k"}, probe=lambda url: False)
    assert r.egress == "openrouter.ai" and r.provider is not None
    r2 = select(env={"OPENROUTER_API_KEY": "k", "PORADAR_ALLOW_CLOUD": "1"}, probe=lambda url: False)
    assert r2.egress == "openrouter.ai"
    r3 = select(cloud=True, env={}, probe=lambda url: False)
    assert r3.egress == "none"


def test_stdin_never_leaves_without_second_flag():
    r = select(cloud=True, origin="stdin", env={"OPENROUTER_API_KEY": "k"}, probe=lambda url: False)
    assert r.egress == "none" and "stdin" in r.reason
    r2 = select(cloud=True, origin="stdin", allow_stdin_egress=True, env={"OPENROUTER_API_KEY": "k"},
                probe=lambda url: False)
    assert r2.egress == "openrouter.ai"


def test_local_ollama_when_reachable():
    r = select(env={}, probe=lambda url: True)
    assert isinstance(r.provider, OllamaProvider) and r.egress == "none"


def test_offline_and_forced():
    assert select(offline=True, env={"OPENROUTER_API_KEY": "k", "PORADAR_ALLOW_CLOUD": "1"}).provider is None
    assert isinstance(select(env={"PORADAR_PROVIDER": "stub"}).provider, StubProvider)


def _req():
    return DecisionRequest(state={"title": "x", "excerpt": "y"}, questions={
        "u": noul("urgent?"),
        "g": choice("genre?", {"reporting": "r", "opinion": "o", "none": "n"}),
        "e": score("emotion?", ["calm", "warm", "hot"]),
    })


def test_ollama_schema_and_parse_cap():
    req = _req()
    s = schema_for(req)
    assert set(s["properties"]) == {"u", "g", "e"}
    assert s["properties"]["g"]["properties"]["choice"]["enum"] == ["reporting", "opinion", "none"]
    a = parse_answers(req, {"u": {"probability_true": 1.0}, "g": {"choice": "bogus", "confidence": 0.99},
                            "e": {"level": 7, "confidence": 0.95}})
    assert a["u"]["noul"] == pytest.approx(0.9)  # pulled toward 0.5 by the cap
    assert a["g"]["choice"] == "none" and a["g"]["confidence"] == 0.8
    assert a["e"]["score"] == 2.0 and a["e"]["confidence"] == 0.8


@respx.mock
async def test_ollama_single_batched_call():
    route = respx.post("http://localhost:11434/api/chat").mock(return_value=httpx.Response(200, json={
        "message": {"content": json.dumps({"u": {"probability_true": 0.2}, "g": {"choice": "opinion", "confidence": 0.7},
                                           "e": {"level": 1, "confidence": 0.6}})}}))
    p = OllamaProvider(url="http://localhost:11434", model="qwen3:8b")
    resp = await p.evaluate(_req())
    assert route.call_count == 1
    sent = json.loads(route.calls[0].request.content)
    assert sent["format"]["type"] == "object" and sent["stream"] is False
    assert sent["options"] == {"temperature": 0}
    assert '"enum"' in sent["messages"][1]["content"]  # schema also passed as text, per Ollama docs
    assert resp["g"].value == "opinion"


async def test_evaluate_item_sends_evidence_only_and_caches(tmp_path):
    stub = StubProvider()
    item = Item(id="i1", title="T", text="body " * 50, source_domain="example.test", origin="file")
    store = Store(tmp_path / "t.sqlite")
    r1 = await evaluate_item(item, stub, "none", store)
    r2 = await evaluate_item(item, stub, "none", store)
    assert len(stub.requests) == 1 and r2.cached and not r1.cached
    state = stub.requests[0].state
    assert set(state) == {"title", "source_domain", "published", "excerpt"}
    assert "signals" not in json.dumps(stub.requests[0].wire())
    assert len(r1.answers) == 16
    assert all(a.gate in ("accept", "uncertain", "reject") for a in r1.answers.values())
