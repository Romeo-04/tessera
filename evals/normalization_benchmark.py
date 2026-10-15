"""Synthetic drug-name benchmark: can the normaliser name what a label says?

    python -m evals.normalization_benchmark          # free; uses the public RxNorm API

This is NOT the hand-labelled gold set (data/gold/normalization.jsonl, which
needs real bottle photos), and it does not test the camera. It measures the
step after reading: given label-like text, does Tessera land on the right
ingredient, ask, or name the wrong drug? Inputs and answers both come from
RxNorm itself, never from a model:

- clean: a single-ingredient oral tablet or capsule, written as a label prints
  it ("ATORVASTATIN 20 MG TABLET"). These are RxNorm's own names fed back to
  RxNorm's matcher, so they are close to an upper bound, not a hard test.
- ocr:   the same text with two deterministic OCR-style misreadings inside the
  drug name (O/0, I/1, S/5, B/8, rn/m, a dropped letter).
- brand: the brand name and dose strength, from a single-ingredient branded
  product ("LIPITOR 20 MG").

Drugs with no single-ingredient oral tablet or capsule in RxNorm (injections,
inhalers, creams) are skipped, because they do not come in a pill bottle.

Outcomes:
- correct:      the right formulary ingredient
- asked:        no code; the app shows options or says it could not read it
- out of scope: no code, and the app says a drug outside its list - but names
                the right drug (e.g. RxNorm's "ursodeoxycholate" for ursodiol)
- wrong:        a different drug, either as a code or as the out-of-scope name
                the user would be shown. This is the number that matters.

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

_DROP = re.compile(r"\b(oral|delayed release oral)\b", re.IGNORECASE)
_PREFIX = re.compile(r"^\s*([\d.]+\s*(HR|ML|ACTUAT|MG)\s+)+", re.IGNORECASE)
_ORAL = re.compile(r"\bOral (Tablet|Capsule)\b", re.IGNORECASE)
# OCR confusions in the direction a camera actually gets them wrong.
_SWAPS = [("O", "0"), ("I", "1"), ("L", "1"), ("S", "5"), ("B", "8"), ("M", "RN"), ("E", "F")]


def label_text(product_name: str) -> str:
    """RxNorm's "atorvastatin 20 MG Oral Tablet" as a label prints it."""
    return " ".join(_DROP.sub("", _PREFIX.sub("", product_name)).split()).upper()


def pick_product(clinical_names: list[str]) -> str | None:
    """A single-ingredient oral tablet or capsule: immediate release first,
    then the lowest strength. None if the drug does not come as one."""
    oral = [n for n in clinical_names if _ORAL.search(n) and " / " not in n]
    if not oral:
        return None

    def strength(n: str) -> float:
        m = re.search(r"([\d.]+)\s*MG", n)
        return float(m.group(1)) if m else 0.0
    return sorted(oral, key=lambda n: ("Release" in n, strength(n), n))[0]


def ocr_noise(text: str, ingredient: str, seed: int, n: int = 2) -> str:
    """Two misreadings inside the drug's own name; everything else stays."""
    m = re.search(re.escape(ingredient), text, re.IGNORECASE)
    start, end = (m.start(), m.end()) if m else (0, len(text.split()[0]))
    name = text[start:end]
    rng = random.Random(seed)
    for _ in range(n):
        options = [(i, a, b) for a, b in _SWAPS for i in range(len(name)) if name.startswith(a, i)]
        if options and rng.random() < 0.8:
            i, a, b = rng.choice(options)
            name = name[:i] + b + name[i + len(a):]
        elif len(name) > 4:
            i = rng.randrange(1, len(name) - 1)
            name = name[:i] + name[i + 1:]
    return text[:start] + name + text[end:]


def brand_of(branded_names: list[str]) -> str | None:
    """The brand from a single-ingredient branded product name, if any."""
    for n in branded_names:
        m = re.search(r"\[([^\]]+)\]\s*$", n)
        if m and " / " not in n:
            return m.group(1)
    return None


def brand_case(brand: str, clean: str) -> str | None:
    """"LIPITOR 20 MG": the brand with the product's dose strength, never a volume."""
    m = re.search(r"\b\d[\d.]*\s*(MG|MCG|UNT)\b", clean)
    return f"{brand.upper()} {m.group(0)}" if m else None


def _same_drug(guess: str, truth: str) -> bool:
    """Is an out-of-scope name the true drug under another RxNorm name?
    A heuristic, stated as one: containment or a shared first four letters
    ("ursodeoxycholate" / "ursodiol")."""
    g, t = guess.lower(), truth.lower()
    return t in g or g in t or g[:4] == t[:4]


def outcome(predicted: str | None, truth: str, in_formulary: bool,
            best_guess: str | None, truth_name: str) -> str:
    if predicted is not None:
        return "correct" if predicted == truth else "wrong"
    if not in_formulary and best_guess:
        return "out of scope" if _same_drug(best_guess, truth_name) else "wrong"
    return "asked"


def summarize(outcomes: list[str]) -> dict:
    from evals.metrics import wilson_interval

    n = len(outcomes)
    counts = {k: outcomes.count(k) for k in ("correct", "asked", "out of scope", "wrong")}
    lo, hi = wilson_interval(counts["wrong"], n)
    answered = counts["correct"] + counts["wrong"]
    return {"n": n, **counts,
            "accuracy_when_answered": counts["correct"] / answered if answered else None,
            "wrong_rate": counts["wrong"] / n if n else None,
            "wrong_rate_lo": lo, "wrong_rate_hi": hi}


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
        product = pick_product(_related(r["rxcui"], "SCD"))
        if not product:
            continue
        clean = label_text(product)
        base = {"truth": r["rxcui"], "truth_name": r["ingredient"]}
        cases.append({**base, "kind": "clean", "text": clean})
        cases.append({**base, "kind": "ocr", "text": ocr_noise(clean, r["ingredient"], seed=SEED + i)})
        brand = brand_of(sorted(n for n in _related(r["rxcui"], "SBD") if _ORAL.search(n)))
        text = brand_case(brand, clean) if brand else None
        if text:
            cases.append({**base, "kind": "brand", "text": text})
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
        o = outcome(d.rxcui, c["truth"], d.in_formulary, d.display_name, c["truth_name"])
        results.append({**c, "predicted": d.rxcui, "in_formulary": d.in_formulary,
                        "best_guess": d.display_name, "outcome": o})
        if o != "correct":
            print(f"  {o:12} {c['kind']:5} {c['text']!r} -> {d.rxcui} ({d.display_name})", flush=True)

    report = {"drugs_sampled": N_DRUGS, "drugs_with_a_pill_product": len({c["truth"] for c in cases}),
              "all": summarize([r["outcome"] for r in results])}
    for kind in ("clean", "ocr", "brand"):
        report[kind] = summarize([r["outcome"] for r in results if r["kind"] == kind])
    report["cases"] = results
    RESULTS.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    for k in ("all", "clean", "ocr", "brand"):
        s = report[k]
        print(f"{k:6} n={s['n']:3}  correct {s['correct']:3}  asked {s['asked']:3}  "
              f"out of scope {s['out of scope']:2}  wrong {s['wrong']:2} "
              f"(95% CI up to {s['wrong_rate_hi'] or 0:.1%})")


if __name__ == "__main__":
    main()
