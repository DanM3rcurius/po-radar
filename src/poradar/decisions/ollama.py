"""Local provider: emulate Choice/Score/Noul with one Ollama structured-output call.

All questions go in a single /api/chat request with one JSON schema (premortem §13.6).
Confidence is self-reported by the model, so it is capped at 0.8 and labeled as such.
"""

from __future__ import annotations

import json
import os
from typing import Any

import httpx

from .base import DecisionProvider, DecisionRequest, DecisionResponse

DEFAULT_URL = "http://localhost:11434"
DEFAULT_MODEL = "qwen3:8b"
SELF_REPORT_CAP = 0.8

SYSTEM = (
    "You are a strict classifier. You never write prose. Judge only from the evidence in STATE. "
    "For each question return the requested typed answer and a confidence in [0,1] that reflects how "
    "concentrated your belief is, not how strongly the text is worded. Do not assume the text is "
    "manipulative; organic reporting and honest argument are common."
)


def ollama_url(env: dict[str, str] | None = None) -> str:
    env = os.environ if env is None else env
    return env.get("OLLAMA_HOST", DEFAULT_URL).rstrip("/")


def reachable(url: str | None = None, timeout: float = 0.6) -> bool:
    try:
        r = httpx.get((url or ollama_url()) + "/api/tags", timeout=timeout)
        return r.status_code == 200
    except Exception:
        return False


def schema_for(request: DecisionRequest) -> dict[str, Any]:
    props: dict[str, Any] = {}
    for qid, q in request.questions.items():
        if q.type == "noul":
            props[qid] = {
                "type": "object",
                "properties": {"probability_true": {"type": "number", "minimum": 0, "maximum": 1}},
                "required": ["probability_true"],
            }
        elif q.type == "choice":
            props[qid] = {
                "type": "object",
                "properties": {
                    "choice": {"type": "string", "enum": list(q.criteria.keys())},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                },
                "required": ["choice", "confidence"],
            }
        else:
            props[qid] = {
                "type": "object",
                "properties": {
                    "level": {"type": "integer", "minimum": 0, "maximum": len(q.criteria) - 1},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                },
                "required": ["level", "confidence"],
            }
    return {"type": "object", "properties": props, "required": list(props)}


def prompt_for(request: DecisionRequest) -> str:
    lines = ["STATE (evidence to judge):", json.dumps(request.state, ensure_ascii=False), "", "QUESTIONS:"]
    for qid, q in request.questions.items():
        instr = q.instructions if isinstance(q.instructions, str) else json.dumps(q.instructions)
        if q.type == "noul":
            crit = ""
            if isinstance(q.criteria, dict):
                crit = f" true = {q.criteria.get('true')}; false = {q.criteria.get('false')}"
            lines.append(f"- {qid} (probability that the condition is true):{instr}{crit}")
        elif q.type == "choice":
            opts = "; ".join(f"{k}: {v}" for k, v in q.criteria.items())
            lines.append(f"- {qid} (choose exactly one): {instr} Options: {opts}")
        else:
            lv = "; ".join(f"{i} = {lvl}" for i, lvl in enumerate(q.criteria))
            lines.append(f"- {qid} (integer level): {instr} Levels: {lv}")
    lines.append("")
    # Ollama's docs recommend also passing the schema as text to ground the response.
    lines.append("Answer with JSON only, matching this schema exactly:")
    lines.append(json.dumps(schema_for(request)))
    return "\n".join(lines)


def parse_answers(request: DecisionRequest, raw: dict[str, Any]) -> dict[str, Any]:
    answers: dict[str, Any] = {}
    for qid, q in request.questions.items():
        a = raw.get(qid) or {}
        if q.type == "noul":
            p = float(a.get("probability_true", 0.5))
            p = min(1.0, max(0.0, p))
            # translate the cap into the noul scale: pull toward 0.5 so confidence <= cap
            p = 0.5 + (p - 0.5) * SELF_REPORT_CAP
            answers[qid] = {"type": "noul", "noul": p}
        elif q.type == "choice":
            ch = a.get("choice")
            if ch not in q.criteria:
                ch = "none" if "none" in q.criteria else next(iter(q.criteria))
            conf = min(SELF_REPORT_CAP, max(0.0, float(a.get("confidence", 0.0))))
            answers[qid] = {"type": "choice", "choice": ch, "probabilities": {ch: conf}, "confidence": conf}
        else:
            n = len(q.criteria)
            lvl = int(a.get("level", 0))
            lvl = min(n - 1, max(0, lvl))
            conf = min(SELF_REPORT_CAP, max(0.0, float(a.get("confidence", 0.0))))
            answers[qid] = {
                "type": "score",
                "score": float(lvl),
                "legend": {str(i): lv for i, lv in enumerate(q.criteria)},
                "probabilities": {str(lvl): conf},
                "confidence": conf,
            }
    return answers


class OllamaProvider(DecisionProvider):
    def __init__(self, url: str | None = None, model: str | None = None,
                 client: httpx.AsyncClient | None = None, timeout: float = 120.0) -> None:
        self.url = url or ollama_url()
        self.model = model or os.environ.get("PORADAR_OLLAMA_MODEL", DEFAULT_MODEL)
        self.name = f"ollama:{self.model}"
        self._client = client
        self._timeout = timeout

    async def evaluate(self, request: DecisionRequest) -> DecisionResponse:
        body = {
            "model": request.model or self.model,
            "stream": False,
            "format": schema_for(request),
            "options": {"temperature": 0},
            "messages": [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": prompt_for(request)},
            ],
        }
        client = self._client or httpx.AsyncClient(timeout=self._timeout)
        own = self._client is None
        try:
            resp = await client.post(self.url + "/api/chat", json=body)
            if not resp.is_success:
                raise RuntimeError(f"ollama: {resp.status_code}: {resp.text[:300]}")
            content = resp.json().get("message", {}).get("content", "{}")
            raw = json.loads(content)
        finally:
            if own:
                await client.aclose()
        return DecisionResponse(model=body["model"], answers=parse_answers(request, raw), provider=self.name)
