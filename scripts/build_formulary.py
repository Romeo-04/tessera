"""One-off: resolve the seed ingredient list to RXCUI codes.

Writes data/formulary.csv, which IS committed — the runtime scope must be
reproducible and reviewable from the repo, not re-derived from a live API on
every run.
"""
import csv
import sys
import time
from pathlib import Path

from tessera.sources.rxnorm import approximate_match, ingredients_of

ROOT = Path(__file__).resolve().parents[1]
SEED = ROOT / "data" / "formulary_seed.csv"
OUT = ROOT / "data" / "formulary.csv"


def resolve(name: str, match_fn=approximate_match, ingredient_fn=ingredients_of):
    """A seed name -> its single RxNorm ingredient, or None.

    The formulary is keyed by ingredient. Taking approximateTerm's top match
    as-is once stored a product ("ursodiol 300 MG Oral Capsule") for ursodiol.
    The ingredient is confirmed directly: match_ingredients would keep the
    product's own code on a lookup failure or a combination, so here a lookup
    failure raises (and main() lists the name as unresolved) and anything that
    is not exactly one ingredient is None.
    """
    cands = match_fn(name, max_entries=5)
    if not cands:
        return None
    ings = ingredient_fn(cands[0].rxcui)
    if len(ings) != 1:
        return None
    code, ing_name = ings[0]
    return cands[0].model_copy(update={"rxcui": code, "display_name": ing_name or cands[0].display_name})


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
            best = resolve(name)
        except Exception as exc:  # a public API; keep going on a blip
            print(f"[{i}/{len(seeds)}] {name}: ERROR {exc}")
            unresolved.append(name)
            continue

        if best is None:
            unresolved.append(name)
            print(f"[{i}/{len(seeds)}] {name}: NONE")
        else:
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
