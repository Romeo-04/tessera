"""Watch the whole formulary for new FDA safety communications.

The label corpus is a snapshot; safety communications are continuous. This
job runs on a schedule over every drug Tessera covers - never over a user's
list - and writes one file the API serves whole. The browser keeps only the
alerts for its own codes, so no request ever pairs a person with what they
take.

Three filters, cheapest first:
  1. Tavily search restricted to fda.gov.
  2. Deterministic prefilter: the host really is fda.gov, and the text names
     the ingredient as a whole word.
  3. Nemotron Lightning judges materiality - and only that. It returns
     indices, not prose, so nothing it writes reaches a user. The summary
     shown is the source's own text.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from urllib.parse import urlparse

from tessera.router import Tier

TAVILY_URL = "https://api.tavily.com/search"
SUMMARY_CHARS = 280

PROMPT = """You are triaging search results for a medication safety watcher.

Ingredient: {ingredient}

Mark a result MATERIAL only if it is an FDA safety communication, boxed
warning change, recall, or label safety update that concerns this ingredient
directly. Approvals, marketing news, and general articles are not material.

Return strict JSON only: {{"material": [<indices of material results>]}}

RESULTS:
{block}
"""


@dataclass(frozen=True)
class Hit:
    title: str
    url: str
    content: str
    published: str | None

    @classmethod
    def from_tavily(cls, r: dict) -> "Hit":
        return cls(
            title=str(r.get("title") or ""), url=str(r.get("url") or ""),
            content=str(r.get("content") or ""), published=r.get("published_date"),
        )


@dataclass(frozen=True)
class Alert:
    rxcui: str
    title: str
    url: str
    published: str | None
    summary: str


def search_safety(ingredient: str, client, api_key: str, max_results: int = 5) -> list[Hit]:
    resp = client.post(
        TAVILY_URL,
        json={
            "query": f"FDA drug safety communication {ingredient}",
            "include_domains": ["fda.gov"],
            "max_results": max_results,
            "search_depth": "basic",
        },
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=30,
    )
    resp.raise_for_status()
    return [Hit.from_tavily(r) for r in resp.json().get("results", [])]


def _is_fda(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return host == "fda.gov" or host.endswith(".fda.gov")


def prefilter(hits: list[Hit], ingredient: str) -> list[Hit]:
    """Deterministic, before any model sees anything."""
    named = re.compile(rf"\b{re.escape(ingredient)}\b", re.IGNORECASE)
    return [h for h in hits if _is_fda(h.url) and named.search(f"{h.title} {h.content}")]


def triage(hits: list[Hit], ingredient: str, rxcui: str, router) -> list[Alert]:
    """Keep the hits the cheap tier marks material. Fails closed."""
    if not hits:
        return []
    block = "\n".join(f"[{i}] {h.title} - {h.content[:400]}" for i, h in enumerate(hits))
    raw = router.complete(
        Tier.CHEAP,
        [{"role": "user", "content": PROMPT.format(ingredient=ingredient, block=block)}],
        response_format={"type": "json_object"},
    )
    try:
        picked = json.loads(raw).get("material", [])
    except (json.JSONDecodeError, AttributeError, TypeError):
        return []
    if not isinstance(picked, list):
        return []

    out: list[Alert] = []
    for i in picked:
        if not isinstance(i, int) or not 0 <= i < len(hits):
            continue
        h = hits[i]
        summary = h.content[:SUMMARY_CHARS].rstrip()
        if len(h.content) > SUMMARY_CHARS:
            summary += "…"
        out.append(Alert(rxcui=rxcui, title=h.title, url=h.url,
                         published=h.published, summary=summary))
    return out


def run_watch(formulary: list[tuple[str, str]], client, router, api_key: str,
              now: str) -> dict:
    """One pass over (ingredient, rxcui) pairs. Returns the file the API serves."""
    alerts: list[Alert] = []
    for ingredient, rxcui in formulary:
        hits = prefilter(search_safety(ingredient, client, api_key), ingredient)
        alerts.extend(triage(hits, ingredient, rxcui, router))
    return {"generated_at": now, "alerts": [asdict(a) for a in alerts]}
