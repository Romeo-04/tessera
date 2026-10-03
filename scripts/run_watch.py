"""Scheduled: re-check every covered drug for new FDA safety communications.

Writes data/watch/alerts.json (gitignored), which GET /api/alerts serves whole.
Needs NEBIUS_API_KEY and TAVILY_API_KEY.

One pass is one Tavily search per drug with label evidence (~285). Tavily's
free tier is 1,000 searches a month, so run this weekly, not daily:
    0 6 * * 1  python scripts/run_watch.py
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

from tessera.config import get_settings
from tessera.router import Router
from tessera.watch import run_watch

ROOT = Path(__file__).resolve().parents[1]


def covered_formulary(data_dir: Path) -> list[tuple[str, str]]:
    seen: dict[str, str] = {}
    for line in (data_dir / "spl" / "sections.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            d = json.loads(line)
            seen.setdefault(d["rxcui"], d["ingredient"])
    return sorted((ing, rxcui) for rxcui, ing in seen.items())


def main() -> None:
    settings = get_settings()
    key = settings.tavily_api_key or os.environ.get("TAVILY_API_KEY")
    if not key:
        sys.exit("TAVILY_API_KEY is not set")
    drugs = covered_formulary(settings.data_dir)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with httpx.Client() as client:
        out = run_watch(drugs, client, Router(), api_key=key, now=now)
    dest = settings.data_dir / "watch" / "alerts.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(f"{len(out['alerts'])} alerts over {len(drugs)} drugs -> {dest}")


if __name__ == "__main__":
    main()
