"""Confidence gate. Code owns the thresholds; providers only report."""

from __future__ import annotations

import os
from dataclasses import dataclass

from ..models import SemanticAnswer
from .base import Answer, ChoiceAnswer, NoulAnswer, ScoreAnswer


@dataclass(frozen=True)
class Thresholds:
    accept: float
    uncertain: float


def thresholds_for(provider: str) -> Thresholds:
    acc = os.environ.get("PORADAR_ACCEPT")
    unc = os.environ.get("PORADAR_UNCERTAIN")
    if acc and unc:
        return Thresholds(float(acc), float(unc))
    if provider.startswith("jev"):
        return Thresholds(0.6, 0.3)
    if provider.startswith("ollama"):
        return Thresholds(0.7, 0.45)
    return Thresholds(0.6, 0.35)


def confidence_of(answer: Answer) -> float:
    if isinstance(answer, NoulAnswer):
        return answer.confidence
    return answer.confidence


def gate_answer(qid: str, answer: Answer, provider: str) -> SemanticAnswer:
    t = thresholds_for(provider)
    conf = confidence_of(answer)
    if isinstance(answer, NoulAnswer):
        uncertain_floor = 0.3 if provider.startswith("jev") else t.uncertain
        accept_floor = 0.6 if provider.startswith("jev") else t.accept
    else:
        uncertain_floor, accept_floor = t.uncertain, t.accept
    if conf >= accept_floor:
        g = "accept"
    elif conf >= uncertain_floor:
        g = "uncertain"
    else:
        g = "reject"
    if isinstance(answer, NoulAnswer):
        return SemanticAnswer(qid=qid, type="noul", value=answer.noul, confidence=conf, gate=g)
    if isinstance(answer, ChoiceAnswer):
        return SemanticAnswer(
            qid=qid, type="choice", value=answer.choice, confidence=conf, gate=g,
            probabilities=answer.probabilities, label=answer.choice,
        )
    assert isinstance(answer, ScoreAnswer)
    return SemanticAnswer(
        qid=qid, type="score", value=answer.score, confidence=conf, gate=g,
        probabilities=answer.probabilities, label=answer.label,
    )
