"""Ask the decider the bank's questions about one item, gate the answers, cache by content."""

from __future__ import annotations

import hashlib
import json
import time

from .decisions import DecisionProvider, DecisionRequest
from .decisions.gate import gate_answer
from .models import Item, SemanticResult
from .questions import jev_state, questions
from .store import Store


def cache_key(provider_name: str, state: dict, qs: dict) -> str:
    h = hashlib.sha256()
    h.update(provider_name.encode())
    h.update(json.dumps(state, sort_keys=True, ensure_ascii=False).encode())
    h.update(json.dumps({k: v.model_dump() for k, v in qs.items()}, sort_keys=True).encode())
    return h.hexdigest()


async def evaluate_item(
    item: Item, provider: DecisionProvider, egress: str, store: Store | None = None
) -> SemanticResult:
    qs = questions()
    state = jev_state(item.title, item.source_domain,
                      item.published.isoformat() if item.published else None, item.excerpt)
    key = cache_key(provider.name, state, qs)
    if store is not None:
        hit = store.cache_get(key)
        if hit:
            res = SemanticResult.model_validate(hit)
            res.cached = True
            return res
    t0 = time.perf_counter()
    resp = await provider.evaluate(DecisionRequest(state=state, questions=qs))
    ms = int((time.perf_counter() - t0) * 1000)
    gated = {qid: gate_answer(qid, ans, provider.name) for qid, ans in resp.answers.items()}
    res = SemanticResult(provider=provider.name, answers=gated, egress=egress, latency_ms=ms)
    if store is not None:
        store.cache_put(key, res.model_dump(mode="json"))
    return res
