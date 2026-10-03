"""One-off: build the seeded demo scenario from the real label corpus.

Writes web/src/demo/scenario.json (committed). The web app bundles it, so the
demo a judge sees needs no camera, no upload, no credentials and no API.

Nothing here is invented except the plain-language sentences, and those are
held to the product's own rules: each one is written only from the quoted
label text beneath it, and tests/test_demo_scenario.py fails if a quote is not
in its span or an action reads as dose advice. Ranking, de-duplication and the
five-risk cap come from the real resolver and adjudicator code, not from a
hand-ordered list.

Every pair below was checked verbatim against data/spl/sections.jsonl on
2026-10-03. Two pairs in the original clickable prototype ("lisinopril +
spironolactone: contraindicated" and "warfarin + spironolactone") are NOT
supported by the label text and are deliberately absent.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from tessera.adjudicate import MAX_RISKS, rank_assertions
from tessera.corpus.chunks import chunk_section
from tessera.resolve import InteractionTable
from tessera.schemas import (
    CodeSet, InteractionAssertion, RankedRisk, SessionResult,
)
from tessera.sources.dailymed import RawSection

ROOT = Path(__file__).resolve().parents[1]
SECTIONS = ROOT / "data" / "spl" / "sections.jsonl"
OUT = ROOT / "web" / "src" / "demo" / "scenario.json"

LISINOPRIL = "RXCUI:29046"
SPIRONOLACTONE = "RXCUI:9997"
FUROSEMIDE = "RXCUI:4603"
DIGOXIN = "RXCUI:3407"
METFORMIN = "RXCUI:6809"
ATORVASTATIN = "RXCUI:83367"
WARFARIN = "RXCUI:11289"

# What Omni would read off seven bottles. Names here never leave the browser.
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
    # The one the normaliser refuses to guess. Both strengths are the same
    # ingredient, and interactions are documented per ingredient, so either
    # answer is checked as warfarin - but the system still asks rather than
    # silently picking, because the next ambiguity might not be this benign.
    {"raw_name": "WARFARIN SOD", "strength": None, "form": "tablet",
     "directions": "Take as directed",
     "rxcui": None, "display_name": "Warfarin",
     "ingredient_rxcui": WARFARIN,
     "margin": 0.037,
     "options": [
         {"rxcui": "RXCUI:855331", "display_name": "Warfarin sodium 5 mg oral tablet",
          "score": 1.0},
         {"rxcui": "RXCUI:855318", "display_name": "Warfarin sodium 2 mg oral tablet",
          "score": 0.963},
     ]},
]

# (subject, object, severity, label ingredient, highlight, mechanism, action)
PAIRS = [
    (LISINOPRIL, SPIRONOLACTONE, "warning", "lisinopril",
     "Potassium-sparing diuretics (spironolactone, amiloride, triamterene, and others) "
     "can increase the risk of hyperkalemia.",
     "Lisinopril's label says spironolactone can increase the risk of high blood "
     "potassium (hyperkalemia).",
     "Ask a pharmacist whether his potassium should be checked while he takes both."),
    (FUROSEMIDE, LISINOPRIL, "warning", "furosemide",
     "Furosemide combined with angiotensin converting enzyme inhibitors or angiotensin "
     "II receptor blockers may lead to severe hypotension and deterioration in renal "
     "function, including renal failure.",
     "Furosemide's label warns that combining it with ACE inhibitors, the group "
     "lisinopril belongs to, may cause severe low blood pressure and worsening kidney "
     "function.",
     "Bring this combination up with his pharmacist or prescriber."),
    (LISINOPRIL, METFORMIN, "warning", "lisinopril",
     "Concomitant administration of lisinopril and antidiabetic medicines (insulins, "
     "oral hypoglycemic agents) may cause an increased blood-glucose-lowering effect "
     "with risk of hypoglycemia.",
     "Lisinopril's label says that with diabetes medicines it may lower blood sugar "
     "further, with a risk of hypoglycemia.",
     "Ask a pharmacist which signs of low blood sugar to watch for."),
    (SPIRONOLACTONE, DIGOXIN, "monitor", "spironolactone",
     "Spironolactone and its metabolites interfere with radioimmunoassays for digoxin "
     "and increase the apparent exposure to digoxin.",
     "Spironolactone can make some blood tests show more digoxin than is really there.",
     "Tell whoever orders his digoxin blood test that he also takes spironolactone."),
    (ATORVASTATIN, DIGOXIN, "monitor", "atorvastatin",
     "Digoxin: May increase digoxin plasma levels;",
     "Atorvastatin's label says it may increase the level of digoxin in the blood.",
     "Ask a pharmacist whether his digoxin levels need watching."),
    # Narrower than it could be, on purpose. The label's sentence saying CYP3A4
    # inhibitors "increase the effect (increase INR) of warfarin" sits in a
    # different span from the table that names atorvastatin, and a risk cites
    # exactly one span. So the claim says only what the table span shows.
    (WARFARIN, ATORVASTATIN, "monitor", "warfarin",
     "CYP3A4 alprazolam, amiodarone, amlodipine, amprenavir, aprepitant, atorvastatin",
     "Warfarin's label lists atorvastatin in its table of drugs that interact with "
     "warfarin through CYP450 enzymes.",
     "Ask his prescriber whether this pairing calls for extra INR checks."),
]


def _load_sections() -> dict[str, dict]:
    out: dict[str, dict] = {}
    for line in SECTIONS.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        d = json.loads(line)
        if d["section"] == "Drug Interactions":
            out[d["ingredient"]] = d
    return out


def _span_for(section: dict, must_contain: list[str]):
    raw = RawSection(
        setid=section["setid"], loinc=section["loinc"], section=section["section"],
        text=section["text"], source_url=section["source_url"],
    )
    for span in chunk_section(raw):
        if all(m in span.text for m in must_contain):
            return span
    raise SystemExit(
        f"no single span of the {section['ingredient']} label contains all of "
        f"{must_contain!r} - the demo would cite text that does not show its claim"
    )


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
            f"{len(found)} documented interactions were found; showing the "
            f"{MAX_RISKS} most severe."
        )
    risks = []
    for a in top:
        span, mechanism, action = by_span[a.span_id]
        risks.append(RankedRisk(
            subject=a.subject_rxcui, object=a.object_rxcui,
            subject_name=names[a.subject_rxcui], object_name=names[a.object_rxcui],
            severity=a.severity, mechanism=mechanism, span_id=a.span_id,
            source_url=span.source_url, action=action,
        ))
    return SessionResult(
        risks=risks, excluded_drugs=left_out,
        status="partial" if left_out else "ok", notes=notes,
    )


def main() -> None:
    if not SECTIONS.exists():
        sys.exit("data/spl/sections.jsonl is missing - run scripts/fetch_spl.py first")
    sections = _load_sections()

    assertions, by_span, spans = [], {}, {}
    for subj, obj, sev, label, highlight, mechanism, action in PAIRS:
        span = _span_for(sections[label], [highlight])
        assertions.append(InteractionAssertion(
            subject_rxcui=subj, object_rxcui=obj, severity=sev, span_id=span.span_id,
        ))
        by_span[span.span_id] = (span, mechanism, action)
        spans[span.span_id] = {
            "text": span.text, "highlight": highlight, "setid": span.setid,
            "section": span.section, "label": label, "source_url": span.source_url,
        }

    table = InteractionTable(assertions)
    names = {d["rxcui"]: d["display_name"] for d in DRUGS if d["rxcui"]}
    names[WARFARIN] = "Warfarin"

    confirmed = sorted(names)
    without = sorted(c for c in names if c != WARFARIN)
    variants = {
        ",".join(confirmed): _result(confirmed, table, by_span, names, []),
        ",".join(without): _result(without, table, by_span, names, ["WARFARIN SOD"]),
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "about": "Seeded demo built by scripts/build_demo.py from FDA label text in "
                 "the Tessera corpus. Explanations are written from the quoted span "
                 "only; ranking and the five-risk cap come from the real resolver.",
        "drugs": DRUGS,
        "variants": {k: v.model_dump() for k, v in variants.items()},
        "spans": spans,
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}: {len(spans)} spans, "
          + ", ".join(f"{len(v.risks)} risks/{v.status}" for v in variants.values()))


if __name__ == "__main__":
    main()
