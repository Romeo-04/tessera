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

try:
    from scripts.class_map import match_class
except ImportError:  # run as `python scripts/build_interactions.py`
    from class_map import match_class

ROOT = Path(__file__).resolve().parents[1]
SECTIONS = ROOT / "data" / "spl" / "sections.jsonl"
FORMULARY = ROOT / "data" / "formulary.csv"
OUT = ROOT / "data" / "interactions.csv"
PROGRESS = ROOT / "data" / "interactions.raw.jsonl"
FAILED = ROOT / "data" / "interactions.failed.txt"
CLASS_MEMBERS = ROOT / "data" / "class_members.json"

PROMPT = """You are reading one section of an FDA-approved drug label.

Subject drug: {subject_name}

List what this text explicitly says interacts with the subject drug. Do not
infer. Do not add anything that is not written here.

  "interactions": drugs or drug ingredients named individually.
  "classes": drug classes named as a class, written exactly as the text
             writes them (e.g. "ACE inhibitors", "potassium-sparing diuretics").

Grade severity using the text's own wording:
  "contraindicated" - the text says do not co-administer
  "warning"         - the text warns of a clinically significant effect
  "monitor"         - the text advises monitoring or dose adjustment

Return strict JSON only:
{{"interactions": [{{"drug": "<name>", "severity": "<grade>"}}],
  "classes": [{{"class": "<class as written>", "severity": "<grade>"}}]}}

If the text names nothing, return {{"interactions": [], "classes": []}}.

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
    a string that a longer formulary name matches better. A class such as
    "CYP3A4 inhibitors" matches nothing here; classes go through class_map.
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


def extract_raw(section_text: str, subject_name: str, router) -> dict | None:
    """The model's reading of one label section, kept exactly as returned.

    This is the only step that costs money, so its output is stored raw and
    everything after it (formulary matching, class expansion) can be redone
    offline. An unreadable verdict returns None, "not checked": reporting it as
    empty would turn a failed read into a silent gap in the safety table.
    """
    raw = router.complete(
        Tier.TOOL,
        [{"role": "user",
          "content": PROMPT.format(subject_name=subject_name, text=section_text[:6000])}],
        response_format={"type": "json_object"},
    )
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):  # TypeError: an empty reply (None)
        return None
    if not isinstance(parsed, dict) or not isinstance(parsed.get("interactions", []), list):
        return None
    classes = parsed.get("classes", [])
    return {"interactions": parsed.get("interactions", []),
            "classes": classes if isinstance(classes, list) else []}


def _items(raw: dict, list_key: str, name_key: str):
    for item in raw.get(list_key) or []:
        if isinstance(item, dict):
            yield str(item.get(name_key, "")), str(item.get("severity", "")).strip().lower()


def assertions_from(
    raw: dict,
    subject_rxcui: str,
    span_id: str,
    by_name: dict[str, str],
    class_members: dict[str, list[str]],
) -> list[InteractionAssertion]:
    """One raw reading -> assertions about formulary drugs, offline.

    A drug we do not carry, an invented severity grade, a class we have not
    mapped, or a label that names nothing all yield no assertion - the
    alternative is inventing a safety claim. Named drugs come first, so a drug
    the label both names and covers by class is cited for its name.
    """
    out: list[InteractionAssertion] = []
    seen: set[str] = {subject_rxcui}

    def add(obj: str, severity: str, via_class: str | None) -> None:
        if obj in seen or severity not in VALID_SEVERITY:
            return
        seen.add(obj)
        out.append(InteractionAssertion(subject_rxcui=subject_rxcui, object_rxcui=obj,
                                        severity=severity, span_id=span_id,
                                        via_class=via_class))

    for name, severity in _items(raw, "interactions", "drug"):
        obj = _resolve_object(name, by_name)
        if obj:
            add(obj, severity, None)
    for phrase, severity in _items(raw, "classes", "class"):
        key = match_class(phrase)
        for obj in class_members.get(key, []) if key else []:
            add(obj, severity, phrase.strip())
    return out


def extract_assertions(
    section_text: str,
    subject_rxcui: str,
    span_id: str,
    formulary: dict[str, str],
    router,
    class_members: dict[str, list[str]] | None = None,
) -> list[InteractionAssertion] | None:
    """extract_raw then assertions_from, for one section in one call."""
    # The model is told "do not infer", so it must at least be told what the
    # subject drug IS. A bare RXCUI gives it nothing to reason from.
    raw = extract_raw(section_text, formulary.get(subject_rxcui, subject_rxcui), router)
    if raw is None:
        return None
    by_name = {name.lower(): rxcui for rxcui, name in formulary.items()}
    return assertions_from(raw, subject_rxcui, span_id, by_name, class_members or {})


def build_table(jobs, extract, progress: Path, workers: int = 6, retries: int = 3,
                sleep=time.sleep) -> tuple[dict, list]:
    """Run `extract(job)` for every job; return ({job: result}, failed jobs).

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
                if rec["result"] is not None:
                    finished[rec["job"]] = rec["result"]
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
            with lock, progress.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps({"job": job, "result": result}) + "\n")
            if result is None:
                failed.append(job)
            else:
                finished[job] = result
    return {j: finished[j] for j in jobs if j in finished}, failed


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
        return extract_raw(text, formulary.get(subject, subject), router)

    raws, failed = build_table(list(spans), extract, PROGRESS)

    # Offline from here: re-running with a changed class map costs nothing.
    members = (json.loads(CLASS_MEMBERS.read_text(encoding="utf-8"))
               if CLASS_MEMBERS.exists() else {})
    if not members:
        print(f"no {CLASS_MEMBERS.name}: class warnings are skipped."
              " Run scripts/build_class_members.py first.")
    by_name = {name.lower(): rxcui for rxcui, name in formulary.items()}
    assertions = [a for span_id, raw in raws.items()
                  for a in assertions_from(raw, spans[span_id][1], span_id, by_name, members)]

    with OUT.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(
            fh, fieldnames=["subject_rxcui", "object_rxcui", "severity", "span_id", "via_class"]
        )
        w.writeheader()
        for a in assertions:
            w.writerow(a.model_dump())

    named = sum(a.via_class is None for a in assertions)
    print(f"\nwrote {len(assertions)} assertions to {OUT}"
          f" ({named} named, {len(assertions) - named} through a class)")
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
