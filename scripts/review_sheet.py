"""One-off: turn data/interactions.csv into a review sheet a person can finish.

Writes data/review/interactions-review.csv (gitignored scratch). One line per
*claim*, not per row: a label sentence about "NSAIDs" that reached eight drugs
is one verdict, because it is one reading of one sentence. Two sections:

- must review: every "contraindicated" claim (the strongest thing the product
  says), every claim between two drugs in the seeded demo (what judges see),
  and every claim where the model gave one drug two grades in one passage.
- sample: a reproducible random sample of the remaining claims, half named and
  half class. scripts/apply_review.py turns the verdicts on these into the
  table's measured precision, with a confidence interval. Without a random
  sample, a review can only say "we fixed what we looked at".

Verdicts: keep, drop (the passage does not say this), or regrade with a
corrected_severity (contraindicated / warning / monitor).

Needs no key and no outside data.
"""
from __future__ import annotations

import csv
import random
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TABLE = ROOT / "data" / "interactions.csv"
FORMULARY = ROOT / "data" / "formulary.csv"
SECTIONS = ROOT / "data" / "spl" / "sections.jsonl"
OUT = ROOT / "data" / "review" / "interactions-review.csv"
CONFLICTS = ROOT / "data" / "review" / "grade-conflicts.csv"
SAMPLE = 100
SEED = 20261015

# The seven medications in the seeded demo (app/src/demo/scenario.json).
DEMO = {"RXCUI:29046", "RXCUI:9997", "RXCUI:4603", "RXCUI:3407",
        "RXCUI:6809", "RXCUI:83367", "RXCUI:11289"}
VERDICT = "verdict (keep / drop / regrade)"


def _named(name: str, text: str) -> bool:
    return bool(name) and re.search(rf"\b{re.escape(name)}\b", text, re.IGNORECASE) is not None


def review_flags(row: dict, passage: str, names: dict[str, str], demo: set[str],
                 conflicts: set[tuple[str, str, str]] = frozenset()) -> list[str]:
    """Why a person should look at this row first; empty when nothing stands out."""
    flags = []
    phrase = row.get("via_class") or ""
    if phrase:
        # The label warned about a class; the member drug is our expansion.
        flags.append("via class")
        if phrase.lower() not in passage.lower():
            flags.append("class phrase not in passage")
    elif not _named(names.get(row["object_rxcui"], ""), passage):
        flags.append("object not named in passage")
    if (row["subject_rxcui"], row["object_rxcui"], row["span_id"]) in conflicts:
        # The model gave this drug two grades in one passage; the most severe
        # was kept, and only a person reading the passage can say which is right.
        flags.append("grades disagree")
    if row["severity"] == "contraindicated":
        flags.append("contraindicated: always reviewed")
    if row["subject_rxcui"] in demo or row["object_rxcui"] in demo:
        flags.append("demo drug")
    return flags


def group_claims(rows: list[dict]) -> list[dict]:
    """Table rows -> claims. A class claim is (passage, subject, phrase) and
    covers every drug the phrase reached; a named claim is one row. `claim` is
    what data/interactions.rejected.csv keys a verdict by."""
    claims: dict[tuple[str, str, str], dict] = {}
    for r in rows:
        via = r.get("via_class") or ""
        key = (r["span_id"], r["subject_rxcui"], via or r["object_rxcui"])
        c = claims.setdefault(key, {"span_id": r["span_id"], "subject_rxcui": r["subject_rxcui"],
                                    "claim": key[2], "via_class": via, "severity": r["severity"],
                                    "objects": [], "rows": []})
        c["objects"].append(r["object_rxcui"])
        c["rows"].append(r)
    return list(claims.values())


def _must_review(c: dict, demo: set[str], conflicts: set[tuple[str, str, str]]) -> list[str]:
    why = []
    if c["severity"] == "contraindicated":
        why.append("contraindicated")
    if c["subject_rxcui"] in demo and any(o in demo for o in c["objects"]):
        why.append("demo pair")
    if any((c["subject_rxcui"], o, c["span_id"]) in conflicts for o in c["objects"]):
        why.append("grades disagree")
    return why


def select_for_review(claims: list[dict], demo: set[str], conflicts: set[tuple[str, str, str]],
                      n_sample: int = SAMPLE, seed: int = SEED) -> tuple[list[dict], list[dict]]:
    """(must review, random sample). The sample excludes must-review claims and
    is split evenly between named and class claims, topping up from the other
    kind when one runs short."""
    must = [dict(c, why=_must_review(c, demo, conflicts)) for c in claims]
    must = [c for c in must if c["why"]]
    taken = {(c["span_id"], c["subject_rxcui"], c["claim"]) for c in must}
    rest = [c for c in claims if (c["span_id"], c["subject_rxcui"], c["claim"]) not in taken]
    rng = random.Random(seed)
    named = [c for c in rest if not c["via_class"]]
    by_class = [c for c in rest if c["via_class"]]
    rng.shuffle(named)
    rng.shuffle(by_class)
    half = n_sample // 2
    k_class = min(len(by_class), max(half, n_sample - len(named)))
    k_named = min(len(named), n_sample - k_class)
    return must, named[:k_named] + by_class[:k_class]


def _excerpt(passage: str, term: str, width: int = 500) -> str:
    m = re.search(re.escape(term), passage, re.IGNORECASE) if term else None
    if not m:
        return passage[:width] + ("…" if len(passage) > width else "")
    start = max(0, m.start() - width // 2)
    return ("…" if start else "") + passage[start:start + width] + ("…" if start + width < len(passage) else "")


def main() -> int:
    from tessera.corpus.spans import SpanStore

    names = {r["rxcui"]: r["ingredient"] for r in csv.DictReader(FORMULARY.open(encoding="utf-8"))}
    spans = SpanStore.from_sections(SECTIONS)
    rows = list(csv.DictReader(TABLE.open(encoding="utf-8")))
    conflicts = ({(r["subject_rxcui"], r["object_rxcui"], r["span_id"])
                  for r in csv.DictReader(CONFLICTS.open(encoding="utf-8"))}
                 if CONFLICTS.exists() else set())

    must, sample = select_for_review(group_claims(rows), DEMO, conflicts)
    out = []
    for section, claims in (("must review", must), ("sample", sample)):
        for c in sorted(claims, key=lambda c: names.get(c["subject_rxcui"], "")):
            span = spans.by_id(c["span_id"])
            shown = c["via_class"] or names.get(c["claim"], c["claim"])
            out.append({
                "section": section,
                "why": ", ".join(c.get("why", [])),
                "subject (whose label)": names.get(c["subject_rxcui"], c["subject_rxcui"]),
                "interacts with (as the label says it)": shown,
                "drugs this covers": ", ".join(sorted(names.get(o, o) for o in c["objects"])),
                "severity": c["severity"],
                "passage": _excerpt(span.text, c["via_class"] or names.get(c["claim"], "")),
                "source_url": span.source_url,
                VERDICT: "",
                "corrected_severity": "",
                "note": "",
                "span_id": c["span_id"],
                "subject_rxcui": c["subject_rxcui"],
                "claim": c["claim"],
            })

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)
    print(f"{len(must)} claims must be reviewed, {len(sample)} sampled -> {OUT}")
    print(f"(the table has {len(rows)} rows in {len(group_claims(rows))} claims)")
    print("Then: python scripts/apply_review.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
