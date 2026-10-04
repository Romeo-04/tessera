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
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from tessera.errors import TesseraError
from tessera.router import Tier
from tessera.schemas import InteractionAssertion

ROOT = Path(__file__).resolve().parents[1]
SECTIONS = ROOT / "data" / "spl" / "sections.jsonl"
FORMULARY = ROOT / "data" / "formulary.csv"
OUT = ROOT / "data" / "interactions.csv"
PROGRESS = ROOT / "data" / "interactions.progress.jsonl"
FAILED = ROOT / "data" / "interactions.failed.txt"

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
) -> list[InteractionAssertion] | None:
    """Named drugs in one label section -> assertions, restricted to formulary.

    A drug we do not carry, an invented severity grade, or a label that names
    no interactions all yield an empty list - the alternative is inventing a
    safety claim. An unreadable verdict is different: it returns None, "not
    checked", because reporting it as empty would turn a failed read into a
    silent gap in the safety table.
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
        return None
    if not isinstance(items, list):
        return None

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


def build_table(jobs, extract, progress: Path, workers: int = 6, retries: int = 3,
                sleep=time.sleep) -> tuple[list[InteractionAssertion], list]:
    """Run `extract(job)` for every job; return (assertions, failed jobs).

    ~940 model calls must survive a rate limit at call 600, so: each result is
    appended to `progress` as it lands and a re-run skips jobs already done;
    an upstream error is retried with backoff and then recorded, never fatal;
    and a job that could not be read is listed by name rather than counted as
    "no interactions".
    """
    finished: dict = {}
    if progress.exists():
        for line in progress.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rec = json.loads(line)
                if rec["assertions"] is not None:
                    finished[rec["job"]] = [InteractionAssertion(**a) for a in rec["assertions"]]
    lock = threading.Lock()

    def one(job):
        for attempt in range(retries):
            try:
                return job, extract(job)
            except TesseraError:
                if attempt < retries - 1:
                    sleep(2 ** attempt)
        return job, None

    todo = [j for j in jobs if j not in finished]
    failed = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for job, result in pool.map(one, todo):
            record = {"job": job, "assertions": None if result is None
                      else [a.model_dump() for a in result]}
            with lock, progress.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record) + "\n")
            if result is None:
                failed.append(job)
            else:
                finished[job] = result
    done = [a for j in jobs if j in finished for a in finished[j]]
    return done, failed


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
    spans = {}
    for r in interaction_rows:
        for span in chunk_section(RawSection(
                setid=r["setid"], loinc=r["loinc"], section=r["section"],
                text=r["text"], source_url=r["source_url"])):
            spans[span.span_id] = (span.text, r["rxcui"])
    print(f"{len(interaction_rows)} interaction sections, {len(spans)} spans", flush=True)

    def extract(span_id):
        text, subject = spans[span_id]
        return extract_assertions(text, subject, span_id, formulary, router)

    assertions, failed = build_table(list(spans), extract, PROGRESS)

    with OUT.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(
            fh, fieldnames=["subject_rxcui", "object_rxcui", "severity", "span_id"]
        )
        w.writeheader()
        for a in assertions:
            w.writerow(a.model_dump())

    print(f"\nwrote {len(assertions)} assertions to {OUT}")
    if failed:
        FAILED.write_text("\n".join(failed) + "\n", encoding="utf-8")
        print(f"{len(failed)} spans could not be read and are NOT in the table: {FAILED}."
              " Re-run to retry only those.")
    print(f"extraction cost: ${sum(c.cost_usd for c in router.calls()):.4f}")
    print("\nNOW REVIEW IT. Hand-check 20 rows against their cited span before "
          "committing; everything this product asserts flows from this table.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
