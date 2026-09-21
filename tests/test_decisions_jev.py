import httpx
import pytest
import respx

from poradar.decisions import DecisionRequest, choice, noul, score
from poradar.decisions.jev import OPENROUTER_DECISIONS_URL, JevProvider, JevRoute


def test_route_prefers_typesafe_over_openrouter():
    r = JevRoute.from_env({"TYPESAFE_API_KEY": "t", "OPENROUTER_API_KEY": "o"})
    assert r.url == "https://api.typesafe.ai/v1/systemone"
    assert r.model == "jev-latest"
    assert r.name == "jev:typesafe"


def test_route_openrouter():
    r = JevRoute.from_env({"OPENROUTER_API_KEY": "o"})
    assert r.url == OPENROUTER_DECISIONS_URL
    assert r.model == "~typesafe/jev-latest"


def test_route_custom_base_url_and_rejects_relative():
    r = JevRoute.from_env({"TYPESAFE_API_KEY": "t", "TYPESAFE_BASE_URL": "https://jev.internal/"})
    assert r.url == "https://jev.internal/v1/systemone"
    with pytest.raises(ValueError):
        JevRoute.from_env({"TYPESAFE_API_KEY": "t", "TYPESAFE_BASE_URL": "jev.internal"})


def test_route_missing_keys():
    with pytest.raises(LookupError):
        JevRoute.from_env({})


def test_question_validation():
    with pytest.raises(ValueError):
        choice("pick", {})
    with pytest.raises(ValueError):
        score("rate", [])
    with pytest.raises(ValueError):
        DecisionRequest(state=3, questions={"q": noul("x")})
    with pytest.raises(ValueError):
        DecisionRequest(state="s", questions={})


def test_wire_format_matches_adapter():
    req = DecisionRequest(
        state={"headline": "Help! My payouts have been failing for 3 days."},
        questions={
            "is_urgent": noul("Does this convey urgency?"),
            "department": choice("Which team?", {"billing": "Payments", "technical": "Bugs"}),
            "anger": score("How angry?", ["Calm", "Frustrated", "Very angry"]),
        },
    )
    body = req.wire()
    assert body["questions"]["is_urgent"] == {"type": "noul", "instructions": "Does this convey urgency?"}
    assert body["questions"]["department"]["criteria"] == {"billing": "Payments", "technical": "Bugs"}
    assert body["questions"]["anger"]["criteria"] == ["Calm", "Frustrated", "Very angry"]
    assert "model" not in body


FAKE = {
    "model": "jev-1.13.0",
    "answers": {
        "is_urgent": {"type": "noul", "noul": 0.9},
        "department": {
            "type": "choice",
            "choice": "billing",
            "probabilities": {"billing": 0.88, "technical": 0.12},
            "confidence": 0.81,
        },
        "anger": {
            "type": "score",
            "score": 1.05,
            "legend": {"0": "Calm", "1": "Frustrated", "2": "Very angry"},
            "probabilities": {"0": 0.0, "1": 0.95, "2": 0.05},
            "confidence": 0.92,
        },
    },
    "usage": {"input_tokens": 40},
}


@respx.mock
async def test_evaluate_parses_all_three_types_and_sends_bearer():
    route = respx.post(OPENROUTER_DECISIONS_URL).mock(return_value=httpx.Response(200, json=FAKE))
    p = JevProvider(route=JevRoute.from_env({"OPENROUTER_API_KEY": "sk-test"}))
    req = DecisionRequest(
        state="Help!",
        questions={
            "is_urgent": noul("urgent?"),
            "department": choice("team?", {"billing": None, "technical": None}),
            "anger": score("anger?", ["Calm", "Frustrated", "Very angry"]),
        },
    )
    resp = await p.evaluate(req)
    sent = route.calls[0].request
    assert sent.headers["authorization"] == "Bearer sk-test"
    import json

    assert json.loads(sent.content)["model"] == "~typesafe/jev-latest"
    assert resp.provider == "jev:openrouter"
    assert resp["is_urgent"].value == 0.9
    assert resp["is_urgent"].confidence == pytest.approx(0.8)
    assert resp["department"].value == "billing"
    assert resp["department"].confidence == 0.81
    assert resp["anger"].level == 1
    assert resp["anger"].label == "Frustrated"


@respx.mock
async def test_evaluate_retries_429_then_succeeds():
    route = respx.post(OPENROUTER_DECISIONS_URL).mock(
        side_effect=[httpx.Response(429, text="slow down"), httpx.Response(200, json=FAKE)]
    )
    p = JevProvider(route=JevRoute.from_env({"OPENROUTER_API_KEY": "k"}), backoff=0.001)
    resp = await p.evaluate(DecisionRequest(state="s", questions={"is_urgent": noul("u?")}))
    assert route.call_count == 2
    assert resp["is_urgent"].value == 0.9


@respx.mock
async def test_evaluate_non_retryable_error_raises_without_retry():
    route = respx.post(OPENROUTER_DECISIONS_URL).mock(return_value=httpx.Response(400, text="bad criteria"))
    p = JevProvider(route=JevRoute.from_env({"OPENROUTER_API_KEY": "k"}), backoff=0.001)
    with pytest.raises(RuntimeError, match="400"):
        await p.evaluate(DecisionRequest(state="s", questions={"q": noul("u?")}))
    assert route.call_count == 1
