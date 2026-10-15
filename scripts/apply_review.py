"""After a person fills in data/review/interactions-review.csv:

    python scripts/apply_review.py

1. Every "drop" and "regrade" verdict goes into data/interactions.rejected.csv
   (committed), so the next table build removes or regrades that claim and no
   rebuild can bring it back.
2. The verdicts become the table's measured precision, in
   evals/table_review.md: how often a claim's pair is right, and how often its
   pair *and* grade are right.

The review has three groups, and precision is reported per group because they
are not alike: must-review claims (all checked, so known exactly), and the
rest split into named and class claims, each sampled at random. The sample is
50/50 but the table is not (about 71/29), so a pooled sample figure would
describe neither. The table-wide estimate weights each group by how many
claims it stands for (data/review/review-manifest.json). It counts claims,
not rows: a class claim covers several rows and is one verdict.

An unknown verdict, a regrade without a valid grade, a sheet that is not
UTF-8, or a verdict that matches no claim in the table stops the script
rather than being guessed at.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHEET = ROOT / "data" / "review" / "interactions-review.csv"
REJECTED = ROOT / "data" / "interactions.rejected.csv"
RESULT = ROOT / "evals" / "table_review.md"
MANIFEST = ROOT / "data" / "review" / "review-manifest.json"
TABLE = ROOT / "data" / "interactions.csv"
VERDICT = "verdict (keep / drop / regrade)"
GRADES = {"contraindicated", "warning", "monitor"}
FIELDS = ["span_id", "subject_rxcui", "claim", "reason", "corrected_severity"]
GROUPS = ("must review", "named", "class")


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
    """The random sample alone, pooled. Kept for the unreviewed count; the
    published figure is table_precision, which does not pool."""
    sample = [r for r in rows if r.get("section") == "sample"]
    done = [r for r in sample if _verdict(r)]
    return {
        "n": len(done),
        "unreviewed": len(sample) - len(done),
        "pair_correct": sum(_verdict(r) in {"keep", "regrade"} for r in done),
        "pair_and_grade_correct": sum(_verdict(r) == "keep" for r in done),
    }


def _group(row: dict) -> str:
    if row.get("section") != "sample":
        return "must review"
    return "named" if row["claim"].startswith("RXCUI:") else "class"


def group_counts(rows: list[dict], grade_too: bool) -> dict[str, tuple[int, int]]:
    """{group: (correct, reviewed)}. A regrade has the right pair, wrong grade."""
    ok = {"keep"} if grade_too else {"keep", "regrade"}
    out: dict[str, list[int]] = {}
    for r in rows:
        v = _verdict(r)
        if v:
            c = out.setdefault(_group(r), [0, 0])
            c[0] += v in ok
            c[1] += 1
    return {g: (k, n) for g, (k, n) in out.items()}


def table_precision(groups: dict[str, tuple[int, int]], sizes: dict[str, int],
                    expected: dict[str, int] | None = None) -> dict:
    """Per-group precision with 95% Wilson intervals, and the table-wide
    estimate weighted by each group's share of the table's claims.

    With `expected` (how many claims each group has on the sheet), the
    table-wide estimate is withheld until every group is reviewed in full: a
    half-done must-review group is neither complete nor random (the sheet is
    sorted), and a missing group would quietly reweight the rest. Its interval
    is the stratified normal approximation, with the finite-population
    correction, so a group reviewed in full adds no uncertainty.
    """
    from evals.metrics import wilson_interval

    per = {}
    for g, (k, n) in groups.items():
        lo, hi = wilson_interval(k, n)
        per[g] = {"k": k, "n": n, "p": k / n if n else None, "lo": lo, "hi": hi}
    measured = {g: v for g, v in per.items() if v["p"] is not None and sizes.get(g)}
    total = sum(sizes[g] for g in measured)
    complete = expected is None or all(groups.get(g, (0, 0))[1] >= n for g, n in expected.items())
    estimate = lo = hi = None
    if total and complete:
        estimate = sum(sizes[g] * v["p"] for g, v in measured.items()) / total
        var = sum((sizes[g] / total) ** 2 * v["p"] * (1 - v["p"]) / v["n"]
                  * max(0.0, 1 - v["n"] / sizes[g]) for g, v in measured.items())
        lo, hi = max(0.0, estimate - 1.96 * var ** 0.5), min(1.0, estimate + 1.96 * var ** 0.5)
    return {"groups": per, "estimate": estimate, "lo": lo, "hi": hi, "complete": complete,
            "covers": total, "of": sum(sizes.values())}


def unmatched(rejections: list[dict], claim_keys: set, already: set = frozenset()) -> list[dict]:
    """Verdicts that would match nothing on rebuild - e.g. a phrase a
    spreadsheet re-encoded. These stop the run; a warning would be missed.
    A verdict already in the rejection file is fine: after a rebuild its claim
    is gone from the table because it was applied."""
    from scripts.build_interactions import claim_key
    return [r for r in rejections
            if (k := claim_key(r["span_id"], r["subject_rxcui"], r["claim"])) not in claim_keys
            and k not in already]


def _block(title: str, rows: list[dict], sizes: dict[str, int], grade_too: bool) -> list[str]:
    expected: dict[str, int] = {}
    for r in rows:
        expected[_group(r)] = expected.get(_group(r), 0) + 1
    t = table_precision(group_counts(rows, grade_too), sizes, expected)
    out = [f"## {title}", ""]
    for g in GROUPS:
        v = t["groups"].get(g)
        if not v or v["p"] is None:
            out.append(f"- {g}: not reviewed")
            continue
        out.append(f"- {g} ({sizes.get(g, '?')} claims in the table): **{v['k']}/{v['n']} ="
                   f" {v['p']:.1%}** (95% CI {v['lo']:.1%} to {v['hi']:.1%})")
    if t["estimate"] is not None:
        out.append(f"- **Table-wide estimate: {t['estimate']:.1%}** (95% CI {t['lo']:.1%} to"
                   f" {t['hi']:.1%}), each group weighted by its share of the table's claims")
    else:
        out.append("- Table-wide estimate: withheld until every group on the sheet is reviewed")
    return out + [""]


def main() -> int:
    sys.path.insert(0, str(ROOT))  # run as `python scripts/apply_review.py`
    from scripts.build_interactions import claim_key

    try:
        rows = list(csv.DictReader(SHEET.open(encoding="utf-8-sig")))
    except UnicodeDecodeError:
        sys.exit(f"{SHEET.name} is not UTF-8. In Excel use Save As -> 'CSV UTF-8 (Comma"
                 " delimited)', not plain 'CSV', which loses characters in the passages.")
    try:
        new = rejections_from(rows)
    except ValueError as e:
        sys.exit(f"stopped: {e}")

    table = list(csv.DictReader(TABLE.open(encoding="utf-8")))
    keys = {claim_key(r["span_id"], r["subject_rxcui"], r["via_class"] or r["object_rxcui"])
            for r in table}
    existing = list(csv.DictReader(REJECTED.open(encoding="utf-8"))) if REJECTED.exists() else []
    already = {claim_key(r["span_id"], r["subject_rxcui"], r["claim"]) for r in existing}
    bad = unmatched(new, keys, already)
    if bad:
        for r in bad:
            print(f"  no such claim in the table: {r['subject_rxcui']} / {r['claim']!r} in {r['span_id']}")
        sys.exit(f"stopped: {len(bad)} verdict(s) match no claim, so they would silently do nothing."
                 " Was the sheet edited outside the verdict columns, or the table rebuilt?")

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8")) if MANIFEST.exists() else {}
    sizes = manifest.get("sizes", {})
    drawn = {tuple(x) for x in manifest.get("sample", [])}
    on_sheet = {(r["span_id"], r["subject_rxcui"], r["claim"]) for r in rows if r["section"] == "sample"}
    if drawn != on_sheet:
        sys.exit(f"stopped: the sheet's sample does not match {MANIFEST.name}, so the precision"
                 " weights would be wrong. Regenerate both with scripts/review_sheet.py.")

    # Nothing is written until every check above has passed.
    merged = {claim_key(r["span_id"], r["subject_rxcui"], r["claim"]): {f: r.get(f, "") for f in FIELDS}
              for r in existing}
    merged.update({claim_key(r["span_id"], r["subject_rxcui"], r["claim"]): r for r in new})
    with REJECTED.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(merged.values())

    RESULT.write_text("\n".join([
        "# Interaction table: reviewed precision",
        "",
        "Written by `python scripts/apply_review.py` from a person's verdicts. Must-review claims",
        "(contraindicated, demo pairs, conflicting or mixed grades) are reviewed in full; named and",
        "class claims are each a random sample (`scripts/review_sheet.py`). Counts are claims,",
        "not rows.",
        "",
        *_block("Pair is documented by the cited passage", rows, sizes, grade_too=False),
        *_block("Pair and severity grade both right", rows, sizes, grade_too=True),
        f"Sample claims not yet reviewed: {review_precision(rows)['unreviewed']}",
        "",
    ]), encoding="utf-8")
    print(f"{len(new)} verdicts -> {REJECTED.name} ({len(merged)} rejections/corrections in total)")
    print(RESULT.read_text(encoding="utf-8"))
    print("Rebuild with: python scripts/build_interactions.py  (no model calls; uses the stored reading)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
