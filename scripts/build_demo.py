"""One-off: build the seeded demo scenario from the real label corpus.

Writes app/src/demo/scenario.json (committed). The app bundles it, so the
demo a judge sees needs no camera, no upload, no credentials and no API.

The pairs are not hand-picked: they are what data/interactions.csv documents
between the seven demo drugs, chosen and ranked by the production resolver, so
the demo shows exactly what the live product would. Only the plain-language
sentences are written by hand, each from its highlighted passage, and
tests/test_demo_scenario.py fails if a highlight is not in its span, an
action reads as dose advice, or a demo pair is missing from the table.

History: the first demo (2026-10-03) hand-picked six pairs, three of them
class-level ("ACE inhibitors", "antidiabetic medicines") that the extracted
table does not contain. Those were removed on 2026-10-04 so the demo never
shows what the live product cannot find.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

from tessera.adjudicate import MAX_RISKS, rank_assertions
from tessera.resolve import InteractionTable
from tessera.schemas import (
    CodeSet, InteractionAssertion, RankedRisk, SessionResult,
)

ROOT = Path(__file__).resolve().parents[1]
SECTIONS = ROOT / "data" / "spl" / "sections.jsonl"
TABLE = ROOT / "data" / "interactions.csv"
OUT = ROOT / "app" / "src" / "demo" / "scenario.json"

LISINOPRIL = "RXCUI:29046"
SPIRONOLACTONE = "RXCUI:9997"
FUROSEMIDE = "RXCUI:4603"
DIGOXIN = "RXCUI:3407"
METFORMIN = "RXCUI:6809"
ATORVASTATIN = "RXCUI:83367"
WARFARIN = "RXCUI:11289"

# What the vision model would read off seven bottles. Names here never leave the browser.
DRUGS = [
    {"raw_name": "LISINOPRIL 10MG TAB", "strength": "10 mg", "form": "tablet",
     "directions": "Take one tablet by mouth every morning",
     "rxcui": LISINOPRIL, "display_name": "Lisinopril"},
    {"raw_name": "SPIRONOLACTONE 25MG", "strength": "25 mg", "form": "tablet",
     "directions": "Take one tablet daily",
     "rxcui": SPIRONOLACTONE, "display_name": "Spironolactone"},
    {"raw_name": "FUROSEMIDE 40 MG", "strength": "40 mg", "form": "tablet",
     "directions": "Take one tablet every morning",
     "rxcui": FUROSEMIDE, "display_name": "Furosemide"},
    {"raw_name": "DIGOXIN 0.125MG", "strength": "0.125 mg", "form": "tablet",
     "directions": "Take one tablet daily",
     "rxcui": DIGOXIN, "display_name": "Digoxin"},
    {"raw_name": "METFORMIN ER 500MG", "strength": "500 mg", "form": "extended-release tablet",
     "directions": "Take one tablet with evening meal",
     "rxcui": METFORMIN, "display_name": "Metformin"},
    {"raw_name": "ATORVASTATIN 20MG", "strength": "20 mg", "form": "tablet",
     "directions": "Take one tablet at bedtime",
     "rxcui": ATORVASTATIN, "display_name": "Atorvastatin"},
    # The one the normaliser refuses to guess - a real abstention, not a staged
    # one. "WARF SOD" (a smudged label) was run through the live ingredient-level
    # matcher on 2026-10-03: warfarin 1.0, sulfacetamide 0.961, alendronate 0.938.
    # Warfarin is ahead by 0.039, inside the 0.05 margin, so it gets no code.
    # The demo precomputes only the warfarin answer; the other options are shown
    # as the real matcher returned them and are marked as not precomputed.
    {"raw_name": "WARF SOD", "strength": None, "form": "tablet",
     "directions": "Take as directed",
     "rxcui": None, "display_name": None,
     "margin": 0.039,
     "precomputed": [WARFARIN],
     "options": [
         {"rxcui": WARFARIN, "display_name": "warfarin", "score": 1.0},
         {"rxcui": "RXCUI:10169", "display_name": "sulfacetamide", "score": 0.961},
         {"rxcui": "RXCUI:46041", "display_name": "alendronate", "score": 0.938},
     ]},
]

# Plain-language explanations, keyed by the pair the REAL table resolves to.
# The pairs themselves are not chosen here: they are whatever
# data/interactions.csv documents between the seven demo drugs, picked by the
# production resolver. A demo pair the live table cannot produce would show
# judges something the product does not do, so the build fails if the table
# yields a pair with no explanation below, or a passage that lacks its
# highlight. Each sentence is written only from its highlighted passage.
# (subject, object) -> (highlight, mechanism, action)
EXPLAIN = {
    (LISINOPRIL, SPIRONOLACTONE): (
        "Potassium-sparing diuretics (spironolactone, amiloride, triamterene, and others) "
        "can increase the risk of hyperkalemia.",
        "Lisinopril's label says spironolactone can increase the risk of high blood "
        "potassium (hyperkalemia).",
        "Ask a pharmacist whether his potassium should be checked while he takes both."),
    (SPIRONOLACTONE, DIGOXIN): (
        "Digoxin: Spironolactone can interfere with radioimmunologic assays of digoxin exposure",
        "Spironolactone can interfere with the blood test used to measure digoxin.",
        "Tell whoever orders his digoxin blood test that he also takes spironolactone."),
    (DIGOXIN, ATORVASTATIN): (
        "Digoxin concentrations increased less than 50% Atorvastatin 22% 15%",
        "Digoxin's label lists atorvastatin among drugs that raise the level of digoxin "
        "in the blood, by less than half.",
        "Ask a pharmacist whether his digoxin levels need checking."),
    (DIGOXIN, METFORMIN): (
        "Digoxin concentrations increased, but magnitude is unclear Alprazolam, azithromycin, "
        "cyclosporine, diclofenac, diphenoxylate, epoprostenol, esomeprazole, ibuprofen, "
        "ketoconazole, lansoprazole, metformin",
        "Digoxin's label lists metformin among drugs that can raise the level of digoxin in "
        "the blood, by an amount it calls unclear.",
        "Ask a pharmacist whether his digoxin levels should be measured."),
    # Class warnings: the label names the class, and the demo drug is in it.
    (FUROSEMIDE, LISINOPRIL): (
        "Furosemide combined with angiotensin converting enzyme inhibitors or angiotensin II "
        "receptor blockers may lead to severe hypotension and deterioration in renal function, "
        "including renal failure.",
        "Furosemide's label warns that taking it with an ACE inhibitor such as lisinopril can "
        "cause severely low blood pressure and harm the kidneys.",
        "Ask his prescriber whether his blood pressure and kidney function should be checked "
        "while he takes both."),
    (LISINOPRIL, METFORMIN): (
        "Concomitant administration of lisinopril and antidiabetic medicines (insulins, oral "
        "hypoglycemic agents) may cause an increased blood-glucose-lowering effect with risk of "
        "hypoglycemia.",
        "Lisinopril's label warns that with diabetes medicines such as metformin it can lower "
        "blood sugar further, with a risk of hypoglycemia.",
        "Ask a pharmacist which signs of low blood sugar to watch for."),
}


def _result(codes: list[str], table, by_span, names, left_out: list[str]) -> SessionResult:
    found = table.resolve(CodeSet(codes=codes))
    top = rank_assertions(found, None)[:MAX_RISKS]
    notes: list[str] = []
    if left_out:
        notes.append(
            "You left these out rather than choose, so they were not checked: "
            + ", ".join(left_out) + "."
        )
    if len(found) > MAX_RISKS:
        notes.append(
            f"{len(found)} documented interactions were found in this demo's "
            f"curated set; showing the {MAX_RISKS} most severe."
        )
    risks = []
    for a in top:
        span, mechanism, action = by_span[a.span_id]
        risks.append(RankedRisk(
            subject=a.subject_rxcui, object=a.object_rxcui,
            subject_name=names[a.subject_rxcui], object_name=names[a.object_rxcui],
            severity=a.severity, mechanism=mechanism, span_id=a.span_id,
            source_url=span.source_url, action=action, quote=span.text,
            via_class=a.via_class,
        ))
    return SessionResult(
        risks=risks, excluded_drugs=left_out,
        status="partial" if left_out else "ok", notes=notes,
    )


def main() -> None:
    if not SECTIONS.exists():
        sys.exit("data/spl/sections.jsonl is missing - run scripts/fetch_spl.py first")
    if not TABLE.exists():
        sys.exit("data/interactions.csv is missing - run scripts/build_interactions.py first")

    from tessera.corpus.spans import SpanStore

    store = SpanStore.from_sections(SECTIONS)
    with TABLE.open(encoding="utf-8") as fh:
        table = InteractionTable([InteractionAssertion(**r) for r in csv.DictReader(fh)])

    names = {d["rxcui"]: d["display_name"] for d in DRUGS if d["rxcui"]}
    names[WARFARIN] = "Warfarin"
    confirmed = sorted(names)

    by_span, spans = {}, {}
    for a in table.resolve(CodeSet(codes=confirmed)):
        key = (a.subject_rxcui, a.object_rxcui)
        if key not in EXPLAIN:
            sys.exit(f"the live table documents {names[key[0]]} -> {names[key[1]]} "
                     f"(span {a.span_id}) but EXPLAIN has no sentence for it; write one "
                     "from that passage before rebuilding the demo")
        highlight, mechanism, action = EXPLAIN[key]
        span = store.by_id(a.span_id)
        if highlight not in span.text:
            sys.exit(f"span {a.span_id} does not contain its highlight: {highlight[:60]!r}")
        by_span[a.span_id] = (span, mechanism, action)
        spans[a.span_id] = {
            "text": span.text, "highlight": highlight, "setid": span.setid,
            "section": span.section, "label": names[key[0]].lower(),
            "source_url": span.source_url,
        }

    without = sorted(c for c in names if c != WARFARIN)
    variants = {
        ",".join(confirmed): _result(confirmed, table, by_span, names, []),
        ",".join(without): _result(without, table, by_span, names, ["WARF SOD"]),
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "about": "Seeded demo built by scripts/build_demo.py from data/interactions.csv "
                 "and the FDA label text it cites, through the production resolver. "
                 "Only the plain-language sentences are written by hand, each from "
                 "its quoted passage.",
        "drugs": DRUGS,
        "variants": {k: v.model_dump() for k, v in variants.items()},
        "spans": spans,
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}: {len(spans)} spans, "
          + ", ".join(f"{len(v.risks)} risks/{v.status}" for v in variants.values()))


if __name__ == "__main__":
    main()
