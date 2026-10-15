"""Synthetic drug-name benchmark: can the normaliser name what a label says?

    python -m evals.normalization_benchmark          # free; uses the public RxNorm API

This is NOT the hand-labelled gold set (data/gold/normalization.jsonl, which
needs real bottle photos). It measures the step after reading: given label-like
text, does Tessera land on the right ingredient code, abstain, or name the
wrong drug? Inputs and answers both come from RxNorm itself, never from a
model:

- clean: a single-ingredient product name as a label prints it
  ("ATORVASTATIN 20 MG TABLET"), from RxNorm's clinical drug names
- ocr:   the same text with two deterministic OCR-style misreadings
  (O/0, I/1, S/5, B/8, rn/m, a dropped letter)
- brand: the brand name and strength, where RxNorm has a single-ingredient
  branded product ("LIPITOR 20 MG")

The truth is the formulary ingredient the product is made of. "wrong" - naming
a different drug without asking - is the number that matters for safety;
"abstained" means the app would ask the user instead.

Cases are cached in evals/normalization_cases.jsonl so a rerun measures the
same inputs; results go to evals/normalization_results.json.
"""
from __future__ import annotations

import csv
import json
import random
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "evals" / "normalization_cases.jsonl"
RESULTS = ROOT / "evals" / "normalization_results.json"
FORMULARY = ROOT / "data" / "formulary.csv"
N_DRUGS = 100
SEED = 20261015
RXNAV = "https://rxnav.nlm.nih.gov/REST"

_DROP = re.compile(r"\b(oral|delayed release oral|for oral suspension)\b", re.IGNORECASE)
# OCR confusions in the direction a camera actually gets them wrong.
_SWAPS = [("O", "0"), ("I", "1"), ("L", "1"), ("S", "5"), ("B", "8"), ("M", "RN"), ("E", "F")]


def label_text(product_name: str) -> str:
    """RxNorm's "atorvastatin 20 MG Oral Tablet" as a label prints it."""
    return " ".join(_DROP.sub("", product_name).split()).upper()


def ocr_noise(text: str, seed: int, n: int = 2) -> str:
    """Two misreadings in the drug name only; the strength and form stay."""
    m = re.search(r"\s\d", text)
    name, rest = (text[:m.start()], text[m.start():]) if m else (text, "")
    rng = random.Random(seed)
    for _ in range(n):
        options = [(i, a, b) for a, b in _SWAPS for i in [k for k in range(len(name)) if name.startswith(a, k)]]
        if options and rng.random() < 0.8:
            i, a, b = rng.choice(options)
            name = name[:i] + b + name[i + len(a):]
        elif len(name) > 4:
            i = rng.randrange(1, len(name) - 1)
            name = name[:i] + name[i + 1:]
    return name + rest


def brand_of(branded_names: list[str]) -> str | None:
    """The brand from a single-ingredient branded product name, if any."""
    for n in branded_names:
        m = re.search(r"\[([^\]]+)\]\s*$", n)
        if m and " / " not in n:
            return m.group(1)
    return None


def outcome(predicted: str | None, truth: str) -> str:
    if predicted is None:
        return "abstained"
    return "correct" if predicted == truth else "wrong"


def summarize(outcomes: list[str]) -> dict:
    from evals.metrics import wilson_interval

    n = len(outcomes)
    c, a, w = (outcomes.count(k) for k in ("correct", "abstained", "wrong"))
    lo, hi = wilson_interval(w, n)
    return {"n": n, "correct": c, "abstained": a, "wrong": w,
            "accuracy_when_answered": c / (c + w) if c + w else None,
            "coverage": (c + w) / n if n else None,
            "wrong_rate": w / n if n else None, "wrong_rate_lo": lo, "wrong_rate_hi": hi}


def _related(rxcui: str, ttys: str) -> list[str]:
    import httpx
    r = httpx.get(f"{RXNAV}/rxcui/{rxcui.removeprefix('RXCUI:')}/related.json",
                  params={"tty": ttys}, timeout=30)
    r.raise_for_status()
    names = []
    for g in (r.json().get("relatedGroup") or {}).get("conceptGroup") or []:
        names += [p["name"] for p in g.get("conceptProperties") or []]
    return names


def build_cases() -> list[dict]:
    rows = list(csv.DictReader(FORMULARY.open(encoding="utf-8")))
    rng = random.Random(SEED)
    cases = []
    for i, r in enumerate(sorted(rng.sample(rows, N_DRUGS), key=lambda r: r["ingredient"])):
        clinical = sorted(n for n in _related(r["rxcui"], "SCD") if " / " not in n)
        if not clinical:
            continue
        clean = label_text(clinical[0])
        cases.append({"truth": r["rxcui"], "kind": "clean", "text": clean})
        cases.append({"truth": r["rxcui"], "kind": "ocr", "text": ocr_noise(clean, seed=SEED + i)})
        brand = brand_of(sorted(_related(r["rxcui"], "SBD")))
        strength = re.search(r"\d[\d.]*\s*(MG|MCG|ML|UNT|%)", clean)
        if brand and strength:
            cases.append({"truth": r["rxcui"], "kind": "brand",
                          "text": f"{brand.upper()} {strength.group(0)}"})
    return cases


def main() -> None:
    from tessera.normalize import normalize_drugs
    from tessera.schemas import DrugRecord

    if not CASES.exists():
        CASES.write_text("".join(json.dumps(c) + "\n" for c in build_cases()), encoding="utf-8")
    cases = [json.loads(x) for x in CASES.read_text(encoding="utf-8").splitlines() if x.strip()]
    formulary = {r["rxcui"] for r in csv.DictReader(FORMULARY.open(encoding="utf-8"))}

    results = []
    for c in cases:
        (d,) = normalize_drugs([DrugRecord(raw_name=c["text"])], formulary)
        results.append({**c, "predicted": d.rxcui, "outcome": outcome(d.rxcui, c["truth"]),
                        "best_guess": d.display_name})
        if results[-1]["outcome"] == "wrong":
            print(f"  WRONG {c['kind']:5} {c['text']!r} -> {d.rxcui} ({d.display_name})")

    report = {"all": summarize([r["outcome"] for r in results])}
    for kind in ("clean", "ocr", "brand"):
        report[kind] = summarize([r["outcome"] for r in results if r["kind"] == kind])
    report["wrong_cases"] = [r for r in results if r["outcome"] == "wrong"]
    RESULTS.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    for k in ("all", "clean", "ocr", "brand"):
        s = report[k]
        print(f"{k:6} n={s['n']:3}  correct {s['correct']:3}  abstained {s['abstained']:3}  "
              f"wrong {s['wrong']:2} (95% CI up to {s['wrong_rate_hi'] or 0:.1%})  "
              f"accuracy when answered {s['accuracy_when_answered'] or 0:.1%}")


if __name__ == "__main__":
    main()
