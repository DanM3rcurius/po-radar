"""Typed decision primitives: Choice, Score, Noul.

This mirrors the TypeSafe Jev System One contract exactly so that any provider
(Jev via TypeSafe or OpenRouter, a local Ollama model, or the deterministic
heuristic fallback) returns the same shapes and the rest of the app never
cares which one answered.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Literal, Union

from pydantic import BaseModel, Field, model_validator

QuestionType = Literal["noul", "choice", "score"]


class Question(BaseModel):
    """One bounded judgment. Ids are not sent to the model: instructions carry the meaning."""

    type: QuestionType
    instructions: Any
    criteria: Any = None

    @model_validator(mode="after")
    def _check_criteria(self) -> "Question":
        if self.type == "choice":
            if not isinstance(self.criteria, dict) or not self.criteria:
                raise ValueError("choice criteria must be a non-empty map of option -> description")
            if len(self.criteria) > 255:
                raise ValueError("choice supports at most 255 options")
        elif self.type == "score":
            if not isinstance(self.criteria, list) or len(self.criteria) < 1:
                raise ValueError("score criteria must be an ordered list of level descriptions")
        elif self.type == "noul":
            if self.criteria is not None and not isinstance(self.criteria, dict):
                raise ValueError('noul criteria must be {"true": ..., "false": ...} or omitted')
        return self


def noul(instructions: Any, criteria: dict[str, str] | None = None) -> Question:
    return Question(type="noul", instructions=instructions, criteria=criteria)


def choice(instructions: Any, options: dict[str, str | None]) -> Question:
    return Question(type="choice", instructions=instructions, criteria=options)


def score(instructions: Any, levels: list[str]) -> Question:
    return Question(type="score", instructions=instructions, criteria=levels)


class DecisionRequest(BaseModel):
    state: Any
    questions: dict[str, Question]
    model: str | None = None

    @model_validator(mode="after")
    def _check(self) -> "DecisionRequest":
        if self.state is None:
            raise ValueError("state is required")
        if isinstance(self.state, (int, float, bool)):
            raise ValueError("state must be a string, object, array (not a bare number/bool)")
        if not self.questions:
            raise ValueError("questions must not be empty")
        return self

    def wire(self) -> dict[str, Any]:
        body: dict[str, Any] = {
            "state": self.state,
            "questions": {
                qid: {k: v for k, v in q.model_dump().items() if v is not None}
                for qid, q in self.questions.items()
            },
        }
        if self.model:
            body["model"] = self.model
        return body


class NoulAnswer(BaseModel):
    type: Literal["noul"] = "noul"
    noul: float = Field(ge=0.0, le=1.0)

    @property
    def confidence(self) -> float:
        """Distance from the coin flip, on [0, 1]. A noul near 0.5 means uncertain."""
        return abs(self.noul - 0.5) * 2

    @property
    def value(self) -> float:
        return self.noul


class ChoiceAnswer(BaseModel):
    type: Literal["choice"] = "choice"
    choice: str
    probabilities: dict[str, float] = Field(default_factory=dict)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)

    @property
    def value(self) -> str:
        return self.choice


class ScoreAnswer(BaseModel):
    type: Literal["score"] = "score"
    score: float
    legend: dict[str, Any] = Field(default_factory=dict)  # values are strings or {"what": ..., "examples": [...]}
    probabilities: dict[str, float] = Field(default_factory=dict)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)

    @property
    def value(self) -> float:
        return self.score

    @property
    def level(self) -> int:
        """Nearest 0-indexed level."""
        return int(round(self.score))

    @property
    def label(self) -> str:
        lv = self.legend.get(str(self.level), str(self.level))
        if isinstance(lv, dict):
            return str(lv.get("what") or lv.get("description") or lv)
        return str(lv)


Answer = Union[NoulAnswer, ChoiceAnswer, ScoreAnswer]


class DecisionResponse(BaseModel):
    model: str | None = None
    answers: dict[str, Answer]
    usage: dict[str, Any] | None = None
    provider: str | None = None

    def __getitem__(self, qid: str) -> Answer:
        return self.answers[qid]


class DecisionProvider(ABC):
    """Anything that can answer typed questions about a state."""

    name: str = "abstract"

    @abstractmethod
    async def evaluate(self, request: DecisionRequest) -> DecisionResponse: ...
