"""Canned provider for tests and `poradar dryrun --offline`. Never touches the network."""

from __future__ import annotations

from typing import Any

from .base import DecisionProvider, DecisionRequest, DecisionResponse


class StubProvider(DecisionProvider):
    name = "stub"

    def __init__(self, answers: dict[str, dict[str, Any]] | None = None) -> None:
        self._answers = answers
        self.requests: list[DecisionRequest] = []

    async def evaluate(self, request: DecisionRequest) -> DecisionResponse:
        self.requests.append(request)
        answers: dict[str, Any] = {}
        for qid, q in request.questions.items():
            if self._answers and qid in self._answers:
                answers[qid] = self._answers[qid]
                continue
            if q.type == "noul":
                answers[qid] = {"type": "noul", "noul": 0.5}
            elif q.type == "choice":
                first = next(iter(q.criteria))
                answers[qid] = {"type": "choice", "choice": first, "probabilities": {first: 1.0}, "confidence": 0.0}
            else:
                n = len(q.criteria)
                answers[qid] = {
                    "type": "score", "score": 0.0,
                    "legend": {str(i): lvl for i, lvl in enumerate(q.criteria)},
                    "probabilities": {str(i): (1.0 if i == 0 else 0.0) for i in range(n)},
                    "confidence": 0.0,
                }
        return DecisionResponse(model="stub", answers=answers, provider=self.name)
