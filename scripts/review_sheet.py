"""One-off: turn data/interactions.csv into a spreadsheet a person can review.

Writes data/review/interactions-review.csv (gitignored scratch). Each row
shows the pair, the grade, and the exact label passage it cites, with blank
verdict/note columns to fill in. Rows that need a human first are flagged
and sorted to the top:

- the cited passage never names the other drug (the builder's likeliest
  error: a drug inferred from a class the label mentions, e.g. "diuretics")
- the grade is "contraindicated" (the strongest claim the product makes)
- either drug is in the seeded demo (what judges will see)

Needs no key and no outside data.
"""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TABLE = ROOT / "data" / "interactions.csv"
FORMULARY = ROOT / "data" / "formulary.csv"
SECTIONS = ROOT / "data" / "spl" / "sections.jsonl"
OUT = ROOT / "data" / "review" / "interactions-review.csv"

# The seven medications in the seeded demo (app/src/demo/scenario.json).
DEMO = {"RXCUI:29046", "RXCUI:9997", "RXCUI:4603", "RXCUI:3407",
        "RXCUI:6809", "RXCUI:83367", "RXCUI:11289"}


def _named(name: str, text: str) -> bool:
    return bool(name) and re.search(rf"\b{re.escape(name)}\b", text, re.IGNORECASE) is not None


def review_flags(row: dict, passage: str, names: dict[str, str], demo: set[str]) -> list[str]:
    """Why a person should look at this row first; empty when nothing stands out."""
    flags = []
    if not _named(names.get(row["object_rxcui"], ""), passage):
        flags.append("object not named in passage")
    if row["severity"] == "contraindicated":
        flags.append("contraindicated: always reviewed")
    if row["subject_rxcui"] in demo or row["object_rxcui"] in demo:
        flags.append("demo drug")
    return flags


def _excerpt(passage: str, name: str, width: int = 400) -> str:
    m = re.search(rf"\b{re.escape(name)}\b", passage, re.IGNORECASE) if name else None
    if not m:
        return passage[:width] + ("…" if len(passage) > width else "")
    start = max(0, m.start() - width // 2)
    return ("…" if start else "") + passage[start:start + width] + ("…" if start + width < len(passage) else "")


def main() -> int:
    from tessera.corpus.spans import SpanStore

    names = {r["rxcui"]: r["ingredient"] for r in csv.DictReader(FORMULARY.open(encoding="utf-8"))}
    spans = SpanStore.from_sections(SECTIONS)
    rows = list(csv.DictReader(TABLE.open(encoding="utf-8")))

    out = []
    for r in rows:
        span = spans.by_id(r["span_id"])
        flags = review_flags(r, span.text, names, DEMO)
        out.append({
            "flags": "; ".join(flags),
            "subject": names.get(r["subject_rxcui"], r["subject_rxcui"]),
            "object": names.get(r["object_rxcui"], r["object_rxcui"]),
            "severity": r["severity"],
            "passage": _excerpt(span.text, names.get(r["object_rxcui"], "")),
            "source_url": span.source_url,
            "verdict (keep / fix / drop)": "",
            "note": "",
            "span_id": r["span_id"],
        })
    out.sort(key=lambda x: (-len(x["flags"].split("; ")) if x["flags"] else 0, x["subject"], x["object"]))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)

    flagged = sum(1 for x in out if x["flags"])
    unnamed = sum(1 for x in out if "object not named" in x["flags"])
    print(f"{len(out)} rows -> {OUT}")
    print(f"{flagged} flagged for review first ({unnamed} where the passage never names the other drug)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
