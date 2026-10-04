from __future__ import annotations

import time
from enum import Enum
from pathlib import Path
from typing import Any

import openai

from tessera.config import get_settings
from tessera.errors import RateLimitedError, UpstreamError
from tessera.telemetry import CallRecord, Telemetry


class Tier(str, Enum):
    """What a call needs, not which model runs it."""

    CHEAP = "CHEAP"   # high-volume triage and shortlisting
    TOOL = "TOOL"     # function calling, entailment
    DEEP = "DEEP"     # adjudication — once per session, never in a loop
    VISION = "VISION"  # reads label photographs


MODEL_FOR_TIER: dict[Tier, str] = {
    Tier.CHEAP: "nvidia/Nemotron-3_5-Lightning",
    Tier.TOOL: "nvidia/nemotron-3-super-120b-a12b",
    Tier.DEEP: "nvidia/Nemotron-3-Ultra-550b-a55b",
    # Nemotron 3 Nano Omni was the plan; Token Factory does not serve it (404,
    # absent from the model catalog, 2026-10-04). MiniCPM-V is an open model
    # built for document reading; switching back is this one line.
    Tier.VISION: "openbmb/MiniCPM-V-4_5",
}

# USD per 1M tokens (input, output), from Nebius's model catalog
# (tokenfactory.nebius.com/model-catalog.md), checked 2026-10-04.
PRICE_PER_M: dict[Tier, tuple[float, float]] = {
    Tier.CHEAP: (0.06, 0.24),
    Tier.TOOL: (0.30, 0.90),
    Tier.DEEP: (1.00, 3.00),
    Tier.VISION: (0.658, 1.11),
}


class Router:
    """The single place a model ID appears. Swap tiers here, measure everywhere."""

    def __init__(self, client: Any | None = None, db_path: Path | None = None):
        if client is None:
            s = get_settings()
            client = openai.OpenAI(api_key=s.nebius_api_key, base_url=s.nebius_base_url)
            db_path = db_path or s.telemetry_db
        self._client = client
        self._telemetry = Telemetry(db_path or Path("./data/telemetry.sqlite"))

    def complete(self, tier: Tier, messages: list[dict], **kw: Any) -> str:
        model = MODEL_FOR_TIER[tier]
        started = time.perf_counter()
        try:
            resp = self._client.chat.completions.create(
                model=model, messages=messages, **kw
            )
        except openai.RateLimitError as exc:
            # Caught before APIError: RateLimitError is a subclass, and callers
            # need to tell "back off" apart from "upstream is broken".
            raise RateLimitedError(f"{model} rate limited") from exc
        except openai.APIError as exc:
            raise UpstreamError(f"{model} failed: {exc}") from exc

        latency_ms = (time.perf_counter() - started) * 1000
        pin, pout = PRICE_PER_M[tier]
        usage = resp.usage
        self._telemetry.record(
            CallRecord(
                tier=tier.value,
                model=model,
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                latency_ms=latency_ms,
                cost_usd=usage.prompt_tokens / 1e6 * pin
                + usage.completion_tokens / 1e6 * pout,
            )
        )
        return resp.choices[0].message.content

    def calls(self) -> list[CallRecord]:
        return self._telemetry.all()

    def spent_since(self, ts: float) -> float:
        return self._telemetry.spent_since(ts)
