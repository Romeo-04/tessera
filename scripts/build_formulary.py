"""One-off: resolve the seed ingredient list to RXCUI codes.

Writes data/formulary.csv, which IS committed — the runtime scope must be
reproducible and reviewable from the repo, not re-derived from a live API on
every run.
"""
import csv
import sys
import time
from pathlib import Path

from tessera.sources.rxnorm import approximate_match

ROOT = Path(__file__).resolve().parents[1]
SEED = ROOT / "data" / "formulary_seed.csv"
OUT = ROOT / "data" / "formulary.csv"


def main() -> int:
    rows: list[dict] = []
    unresolved: list[str] = []
    seen_rxcui: dict[str, str] = {}

    seeds = list(csv.DictReader(SEED.open()))
    for i, row in enumerate(seeds, 1):
        name = row["ingredient"].strip()
        if not name:
            continue
        try:
            cands = approximate_match(name, max_entries=5)
        except Exception as exc:  # a public API; keep going on a blip
            print(f"[{i}/{len(seeds)}] {name}: ERROR {exc}")
            unresolved.append(name)
            continue

        if not cands:
            unresolved.append(name)
            print(f"[{i}/{len(seeds)}] {name}: NONE")
        else:
            best = cands[0]
            if best.rxcui in seen_rxcui:
                # Two seed names resolving to one concept is a seed-list
                # duplicate, not a data problem. Keep the first.
                print(f"[{i}/{len(seeds)}] {name}: dup of {seen_rxcui[best.rxcui]}")
            else:
                seen_rxcui[best.rxcui] = name
                rows.append({
                    "ingredient": name,
                    "rxcui": best.rxcui,
                    "display_name": best.display_name,
                })
                print(f"[{i}/{len(seeds)}] {name} -> {best.rxcui}")
        time.sleep(0.05)  # be polite to a free public API

    with OUT.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["ingredient", "rxcui", "display_name"])
        w.writeheader()
        w.writerows(rows)

    print(f"\nwrote {len(rows)} drugs to {OUT}")
    if unresolved:
        print(f"UNRESOLVED ({len(unresolved)}): {unresolved}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
