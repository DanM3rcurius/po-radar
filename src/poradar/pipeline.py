"""Orchestration: items → signals → (semantic) → fusion → brief. Pure functions plus one async entry."""

from __future__ import annotations

import asyncio
import hashlib
from datetime import datetime, timezone

from .brief import write_brief
from .decisions.router import Route, select
from .fusion import fuse
from .models import ClusterSignals, Item, LexicalSignals, RadarResult, SemanticResult
from .questions import bank_status
from .receipts import loaded_abstractions
from .signals import cluster_items, cluster_signals, lexical_signals
from .store import Store
from .worksheet import build as build_worksheet


def narrative_id_for(cluster: list[Item]) -> str:
    ids = sorted(i.id for i in cluster)
    return "n-" + hashlib.sha256("|".join(ids).encode()).hexdigest()[:12]


async def run(
    items: list[Item],
    *,
    route: Route | None = None,
    store: Store | None = None,
    now: datetime | None = None,
    brief: bool = True,
    use_local_model_for_brief: bool = True,
    cloud: bool = False,
    offline: bool = False,
    allow_stdin_egress: bool = False,
) -> list[RadarResult]:
    now = now or datetime.now(timezone.utc)
    live = [i for i in items if not i.ingest_rejected]
    if not live:
        return []
    origin = "stdin" if any(i.origin == "stdin" for i in live) else live[0].origin
    route = route or select(cloud=cloud, origin=origin, allow_stdin_egress=allow_stdin_egress, offline=offline)

    lex: dict[str, LexicalSignals] = {i.id: lexical_signals(i) for i in live}
    clusters = cluster_items(live)
    bank = bank_status()

    semantic: dict[str, SemanticResult] = {}
    if route.provider is not None:
        from .semantic import evaluate_item

        async def one(i: Item) -> None:
            try:
                semantic[i.id] = await evaluate_item(i, route.provider, route.egress, store)
            except Exception as e:  # a failed provider must never block the deterministic path
                semantic[i.id] = SemanticResult(provider=route.provider.name + " (error: " + type(e).__name__ + ")",
                                                answers={}, egress=route.egress)

        await asyncio.gather(*(one(i) for i in live))

    results: list[RadarResult] = []
    for cl in clusters:
        nid = narrative_id_for(cl)
        cs: ClusterSignals = cluster_signals(cl, lex, now) if len(cl) > 1 else ClusterSignals()
        for i in cl:
            r = fuse(item_id=i.id, narrative_id=nid, title=i.title, lexical=lex[i.id], cluster=cs,
                     semantic=semantic.get(i.id), bank=bank)
            r.worksheet = build_worksheet(i, lex[i.id], cs, semantic.get(i.id), now)
            r.define_first = loaded_abstractions(i.text)
            if cs.item_count <= 1:
                r.falsifiers.append("NCI rule: read opposing and international coverage of the same event before trusting this score")
            if brief:
                r.brief = write_brief(r, i.excerpt, use_local_model=use_local_model_for_brief)
            results.append(r)
            if store is not None:
                store.put_item(i.model_dump(mode="json"))
                store.put_result(r.model_dump(mode="json"))
    results.sort(key=lambda r: r.ers, reverse=True)
    return results
