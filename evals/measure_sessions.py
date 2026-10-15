"""Live end-to-end sessions: what one assessment actually costs and how long it takes.

    python -m evals.measure_sessions        # needs NEBIUS_API_KEY and the built corpus

Runs the production `assess` - resolver, one Ultra adjudication call, the
verifier - on the seeded demo's medication list and on a fixed-seed sample of
medication lists that each have at least one documented interaction, so every
session exercises the models. Writes evals/sessions.jsonl, which
`python -m evals.run_all` summarises.

Codes only go in: this is the same gate the product enforces. Cost and latency
come from the router's own telemetry, not from estimates.
"""
from __future__ import annotations

import json
import random
import re
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "evals" / "sessions.jsonl"
DEMO = ["RXCUI:29046", "RXCUI:9997", "RXCUI:4603", "RXCUI:3407",
        "RXCUI:6809", "RXCUI:83367", "RXCUI:11289"]
SAMPLED = 12
SEED = 20261015


def code_sets(table, covered: set[str], n: int = SAMPLED, seed: int = SEED) -> list[list[str]]:
    """The demo list, then `n` lists of 3-6 covered drugs with >= 1 documented pair."""
    from tessera.schemas import CodeSet

    rng = random.Random(seed)
    pool = sorted(covered & table.known_subjects())
    out = [sorted(DEMO)]
    while len(out) < n + 1:
        codes = sorted(rng.sample(pool, rng.randint(3, 6)))
        if codes not in out and table.resolve(CodeSet(codes=codes)):
            out.append(codes)
    return out


def main() -> None:
    from tessera.cli import _load_corpus
    from tessera.config import get_settings
    from tessera.pipeline import assess
    from tessera.router import Router
    from tessera.schemas import CodeSet

    index, table, _, covered = _load_corpus(get_settings())
    router = Router()
    rows = []
    for codes in code_sets(table, covered):
        before = len(router.calls())
        started = time.perf_counter()
        result = assess(CodeSet(codes=codes), index, table, router, covered or None)
        latency = time.perf_counter() - started
        calls = router.calls()[before:]
        withheld = sum(int(m.group(1)) for n in result.notes
                       for m in [re.search(r"(\d+) statement\(s\) were withheld", n)] if m)
        rows.append({
            "codes": codes,
            "documented": len(table.resolve(CodeSet(codes=codes))),
            "shown": len(result.risks),
            "withheld": withheld,
            "status": result.status,
            "latency_s": round(latency, 2),
            "cost_usd": round(sum(c.cost_usd for c in calls), 6),
            "calls": [c.tier for c in calls],
        })
        r = rows[-1]
        print(f"{len(codes)} drugs, {r['documented']} documented -> {r['shown']} shown,"
              f" {r['withheld']} withheld, {r['status']}, {r['latency_s']} s, ${r['cost_usd']:.4f}",
              flush=True)
    OUT.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
