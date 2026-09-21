"""Provider selection. Local by default; cloud only by explicit consent (premortem §13.2)."""

from __future__ import annotations

import os
from dataclasses import dataclass

from .base import DecisionProvider
from .jev import JevProvider, JevRoute
from .ollama import OllamaProvider, ollama_url, reachable
from .stub import StubProvider


@dataclass
class Route:
    provider: DecisionProvider | None
    egress: str  # "none" or a hostname
    reason: str


def cloud_allowed(cloud_flag: bool, env: dict[str, str] | None = None) -> bool:
    env = os.environ if env is None else env
    return bool(cloud_flag) or env.get("PORADAR_ALLOW_CLOUD") == "1"


def select(
    *,
    cloud: bool = False,
    origin: str = "file",
    allow_stdin_egress: bool = False,
    offline: bool = False,
    env: dict[str, str] | None = None,
    probe=reachable,
) -> Route:
    env = dict(os.environ) if env is None else env
    forced = env.get("PORADAR_PROVIDER")
    if forced == "none" or offline:
        return Route(None, "none", "offline: lexical-only mode")
    if forced == "stub":
        return Route(StubProvider(), "none", "stub provider (canned answers)")

    want_cloud = cloud_allowed(cloud, env) or forced == "jev"
    if want_cloud:
        if origin == "stdin" and not allow_stdin_egress:
            return _local(env, probe, prefix="stdin text stays on this machine (pass --allow-stdin-egress to override); ")
        try:
            route = JevRoute.from_env(env)
        except LookupError as e:
            if forced == "jev":
                raise
            return _local(env, probe, prefix=f"cloud allowed but {e}; ")
        host = route.url.split("/")[2]
        return Route(JevProvider(route=route), host, f"Jev via {host} (explicit cloud consent)")

    if forced == "ollama":
        return Route(OllamaProvider(), "none", f"Ollama at {ollama_url(env)} (forced)")
    return _local(env, probe, prefix="")


def _local(env: dict[str, str], probe, prefix: str) -> Route:
    url = ollama_url(env)
    if probe(url):
        return Route(OllamaProvider(url=url), "none", prefix + f"Ollama at {url} (local)")
    return Route(None, "none", prefix + "no local model reachable; lexical-only mode")
