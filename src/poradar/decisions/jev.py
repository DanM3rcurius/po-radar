"""Jev (TypeSafe System One) provider.

Two routes, same body, same response:
  * TypeSafe direct:  POST {TYPESAFE_BASE_URL}/v1/systemone   (TYPESAFE_API_KEY)
  * OpenRouter:       POST https://openrouter.ai/api/alpha/decisions (OPENROUTER_API_KEY)

TYPESAFE_API_KEY wins if both are set (matches the community `evaluate` adapter,
so a stray OpenRouter key cannot re-bill an existing setup). Keys are read from the
environment only and are never logged or echoed.
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass

import httpx

from .base import DecisionProvider, DecisionRequest, DecisionResponse

TYPESAFE_DEFAULT_BASE = "https://api.typesafe.ai"
OPENROUTER_DECISIONS_URL = "https://openrouter.ai/api/alpha/decisions"
MAX_BODY = 16 << 20


@dataclass(frozen=True)
class JevRoute:
    url: str
    api_key: str
    model: str
    name: str

    @staticmethod
    def from_env(env: dict[str, str] | None = None) -> "JevRoute":
        env = os.environ if env is None else env
        if env.get("TYPESAFE_API_KEY"):
            base = env.get("TYPESAFE_BASE_URL", TYPESAFE_DEFAULT_BASE).rstrip("/")
            if not base.startswith(("http://", "https://")):
                raise ValueError("TYPESAFE_BASE_URL must be an absolute http(s) URL")
            return JevRoute(f"{base}/v1/systemone", env["TYPESAFE_API_KEY"], "jev-latest", "jev:typesafe")
        if env.get("OPENROUTER_API_KEY"):
            return JevRoute(
                OPENROUTER_DECISIONS_URL, env["OPENROUTER_API_KEY"], "~typesafe/jev-latest", "jev:openrouter"
            )
        raise LookupError(
            "set TYPESAFE_API_KEY (https://console.typesafe.ai/) or OPENROUTER_API_KEY "
            "(https://openrouter.ai/keys) in your shell; never paste keys into chat"
        )


class JevProvider(DecisionProvider):
    def __init__(
        self,
        route: JevRoute | None = None,
        client: httpx.AsyncClient | None = None,
        timeout: float = 60.0,
        backoff: float = 0.5,
        max_retries: int = 3,
    ) -> None:
        self.route = route or JevRoute.from_env()
        self.name = self.route.name
        self._client = client
        self._timeout = timeout
        self._backoff = backoff
        self._max_retries = max_retries

    async def evaluate(self, request: DecisionRequest) -> DecisionResponse:
        body = request.wire()
        body.setdefault("model", self.route.model)
        headers = {"Authorization": f"Bearer {self.route.api_key}", "Content-Type": "application/json"}
        client = self._client or httpx.AsyncClient(timeout=self._timeout)
        own = self._client is None
        delay = self._backoff
        try:
            for attempt in range(self._max_retries + 1):
                resp = await client.post(self.route.url, json=body, headers=headers)
                if len(resp.content) > MAX_BODY:
                    raise RuntimeError(f"jev: response exceeds {MAX_BODY} bytes")
                if resp.is_success:
                    data = resp.json()
                    return DecisionResponse(
                        model=data.get("model"),
                        answers=data["answers"],
                        usage=data.get("usage"),
                        provider=self.name,
                    )
                retryable = resp.status_code in (429, 529)
                if not retryable or attempt == self._max_retries:
                    raise RuntimeError(f"jev: {resp.status_code}: {resp.text[:500]}")
                await asyncio.sleep(delay)
                delay *= 2
        finally:
            if own:
                await client.aclose()
        raise RuntimeError("jev: unreachable")
