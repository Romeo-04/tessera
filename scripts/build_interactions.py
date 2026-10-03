"""One-off: derive interaction assertions from FDA label text, then freeze them.

Runtime never calls this. It reads the reviewed CSV this produces, so the
safety-critical lookup is pure data and cannot hallucinate.

This exists because the NLM/RxNav Drug Interaction API was discontinued on
2 January 2024. Deriving assertions from the SPL "Drug Interactions" section is
not a workaround but an improvement: the assertion and the citation become the
same object, instead of asserting from one source and citing another.
"""
from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

from tessera.router import Tier
from tessera.schemas import InteractionAssertion

ROOT = Path(__file__).resolve().parents[1]
SECTIONS = ROOT / "data" / "spl" / "sections.jsonl"
FORMULARY = ROOT / "data" / "formulary.csv"
OUT = ROOT / "data" / "interactions.csv"

PROMPT = """You are reading one section of an FDA-approved drug label.

Subject drug: {subject_name}

List ONLY drugs or drug ingredients that this text explicitly says interact
with the subject drug. Do not infer. Do not add drugs that are not named here.

Grade severity using the text's own wording:
  "contraindicated" - the text says do not co-administer
  "warning"         - the text warns of a clinically significant effect
  "monitor"         - the text advises monitoring or dose adjustment

Return strict JSON only:
{{"interactions": [{{"drug": "<name>", "severity": "<grade>"}}]}}

If the text names no interacting drugs, return {{"interactions": []}}.

TEXT:
{text}
"""

VALID_SEVERITY = {"contraindicated", "warning", "monitor"}


def _resolve_object(name: str, by_name: dict[str, str]) -> str | None:
    """Map a drug name from label text to a formulary RXCUI.

    Labels do not write bare ingredient names. They write "warfarin sodium",
    "aspirin 81 mg", "metformin-containing products". Exact matching drops
    nearly all of those, so an ingredient is also accepted when it appears as a
    whole word inside the returned name.

    Whole-word only, and longest ingredient first, so "aspirin" does not claim
    a string that a longer formulary name matches better. A drug *class* such
    as "CYP3A4 inhibitors" matches nothing and is correctly dropped - we can
    only assert about drugs we can resolve to a code.
    """
    name = name.strip().lower()
    if not name:
        return None
    if name in by_name:
        return by_name[name]
    for ingredient in sorted(by_name, key=len, reverse=True):
        if re.search(rf"\b{re.escape(ingredient)}\b", name):
            return by_name[ingredient]
    return None


def extract_assertions(
    section_text: str,
    subject_rxcui: str,
    span_id: str,
    formulary: dict[str, str],
    router,
) -> list[InteractionAssertion]:
    """Named drugs in one label section -> assertions, restricted to formulary.

    Every path that cannot produce a confident, in-scope, well-graded assertion
    returns nothing. Unreadable model output, a drug we do not carry, an
    invented severity grade, and a label that simply names no interactions all
    collapse to the same empty result - because the alternative is inventing a
    safety claim, and no downstream consumer could tell the difference.
    """
    by_name = {name.lower(): rxcui for rxcui, name in formulary.items()}
    # The model is told "do not infer", so it must at least be told what the
    # subject drug IS. A bare RXCUI gives it nothing to reason from.
    subject_name = formulary.get(subject_rxcui, subject_rxcui)
    raw = router.complete(
        Tier.TOOL,
        [{"role": "user",
          "content": PROMPT.format(
              subject_name=subject_name, text=section_text[:6000])}],
        response_format={"type": "json_object"},
    )
    try:
        items = json.loads(raw).get("interactions", [])
    except (json.JSONDecodeError, AttributeError, TypeError):
        return []
    if not isinstance(items, list):
        return []

    out: list[InteractionAssertion] = []
    seen: set[tuple[str, str]] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        name = str(item.get("drug", ""))
        severity = str(item.get("severity", "")).strip().lower()
        obj = _resolve_object(name, by_name)
        if not obj or severity not in VALID_SEVERITY or obj == subject_rxcui:
            continue
        key = (subject_rxcui, obj)
        if key in seen:
            continue
        seen.add(key)
        out.append(
            InteractionAssertion(
                subject_rxcui=subject_rxcui,
                object_rxcui=obj,
                severity=severity,
                span_id=span_id,
            )
        )
    return out


def main() -> int:
    from tessera.corpus.chunks import chunk_section
    from tessera.router import Router
    from tessera.sources.dailymed import RawSection

    formulary = {
        r["rxcui"]: r["ingredient"] for r in csv.DictReader(FORMULARY.open(encoding="utf-8"))
    }
    router = Router()

    rows = [json.loads(l) for l in SECTIONS.read_text(encoding="utf-8").splitlines() if l.strip()]
    interaction_rows = [r for r in rows if r["loinc"] == "34073-7"]
    assertions: list[InteractionAssertion] = []

    for i, r in enumerate(interaction_rows, 1):
        spans = chunk_section(
            RawSection(
                setid=r["setid"], loinc=r["loinc"], section=r["section"],
                text=r["text"], source_url=r["source_url"],
            )
        )
        for span in spans:
            assertions.extend(
                extract_assertions(span.text, r["rxcui"], span.span_id, formulary, router)
            )
        print(f"[{i}/{len(interaction_rows)}] {r['ingredient']}: "
              f"{len(assertions)} assertions so far", flush=True)

    with OUT.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(
            fh, fieldnames=["subject_rxcui", "object_rxcui", "severity", "span_id"]
        )
        w.writeheader()
        for a in assertions:
            w.writerow(a.model_dump())

    print(f"\nwrote {len(assertions)} assertions to {OUT}")
    print(f"extraction cost: ${sum(c.cost_usd for c in router.calls()):.4f}")
    print("\nNOW REVIEW IT. Hand-check 20 rows against their cited span before "
          "committing; everything this product asserts flows from this table.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
