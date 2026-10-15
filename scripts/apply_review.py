"""After a person fills in data/review/interactions-review.csv:

    python scripts/apply_review.py

1. Every "drop" and "regrade" verdict goes into data/interactions.rejected.csv
   (committed), so the next table build removes or regrades that claim and no
   rebuild can bring it back.
2. The verdicts on the random sample become the table's measured precision,
   written to evals/table_review.md: how often a claim's pair is right, and how
   often its pair *and* grade are right, each with a 95% Wilson interval.

Must-review claims are excluded from precision on purpose: they were chosen
because they are risky, so counting them would describe the riskiest claims,
not the table.

An unknown verdict, or a regrade without a valid grade, stops the script
rather than being guessed at.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHEET = ROOT / "data" / "review" / "interactions-review.csv"
REJECTED = ROOT / "data" / "interactions.rejected.csv"
RESULT = ROOT / "evals" / "table_review.md"
VERDICT = "verdict (keep / drop / regrade)"
GRADES = {"contraindicated", "warning", "monitor"}
FIELDS = ["span_id", "subject_rxcui", "claim", "reason", "corrected_severity"]


def _verdict(row: dict) -> str:
    v = (row.get(VERDICT) or "").strip().lower()
    if v not in {"", "keep", "drop", "regrade"}:
        raise ValueError(f"unknown verdict {v!r} for {row['subject_rxcui']} / {row['claim']}")
    if v == "regrade" and (row.get("corrected_severity") or "").strip().lower() not in GRADES:
        raise ValueError(f"regrade needs corrected_severity in {sorted(GRADES)}: "
                         f"{row['subject_rxcui']} / {row['claim']}")
    return v


def rejections_from(rows: list[dict]) -> list[dict]:
    out = []
    for r in rows:
        v = _verdict(r)
        if v in {"drop", "regrade"}:
            out.append({"span_id": r["span_id"], "subject_rxcui": r["subject_rxcui"],
                        "claim": r["claim"],
                        "reason": (r.get("note") or "").strip() or f"reviewer: {v}",
                        "corrected_severity": (r["corrected_severity"].strip().lower()
                                               if v == "regrade" else "")})
    return out


def review_precision(rows: list[dict]) -> dict:
    sample = [r for r in rows if r.get("section") == "sample"]
    done = [r for r in sample if _verdict(r)]
    return {
        "n": len(done),
        "unreviewed": len(sample) - len(done),
        "pair_correct": sum(_verdict(r) in {"keep", "regrade"} for r in done),
        "pair_and_grade_correct": sum(_verdict(r) == "keep" for r in done),
    }


def main() -> int:
    sys.path.insert(0, str(ROOT))  # run as `python scripts/apply_review.py`
    from evals.metrics import wilson_interval

    rows = list(csv.DictReader(SHEET.open(encoding="utf-8-sig")))
    try:
        new = rejections_from(rows)
        p = review_precision(rows)
    except ValueError as e:
        sys.exit(f"stopped: {e}")

    existing = list(csv.DictReader(REJECTED.open(encoding="utf-8"))) if REJECTED.exists() else []
    key = lambda r: (r["span_id"], r["subject_rxcui"], r["claim"].casefold())  # noqa: E731
    merged = {key(r): {f: r.get(f, "") for f in FIELDS} for r in existing}
    merged.update({key(r): r for r in new})
    with REJECTED.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(merged.values())

    def line(label: str, k: int) -> str:
        lo, hi = wilson_interval(k, p["n"])
        if lo is None:
            return f"- {label}: not measured (no sample claims reviewed)"
        return f"- {label}: **{k}/{p['n']} = {k / p['n']:.1%}** (95% CI {lo:.1%} to {hi:.1%})"

    RESULT.write_text("\n".join([
        "# Interaction table: reviewed precision",
        "",
        "Written by `python scripts/apply_review.py` from a person's verdicts on a reproducible",
        "random sample of claims (`scripts/review_sheet.py`, half named, half class).",
        "",
        line("Pair is documented by the cited passage", p["pair_correct"]),
        line("Pair and severity grade both right", p["pair_and_grade_correct"]),
        f"- Sample claims not yet reviewed: {p['unreviewed']}",
        "",
    ]), encoding="utf-8")
    print(f"{len(new)} verdicts -> {REJECTED.name} ({len(merged)} rejections/corrections in total)")
    print(RESULT.read_text(encoding="utf-8"))
    print("Rebuild with: python scripts/build_interactions.py  (no model calls; uses the stored reading)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
