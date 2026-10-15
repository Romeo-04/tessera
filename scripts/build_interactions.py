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
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from tessera.errors import TesseraError
from tessera.router import Tier
from tessera.schemas import InteractionAssertion

try:
    from scripts.class_map import excluded_text, match_classes
except ImportError:  # run as `python scripts/build_interactions.py`
    from class_map import excluded_text, match_classes

ROOT = Path(__file__).resolve().parents[1]
SECTIONS = ROOT / "data" / "spl" / "sections.jsonl"
FORMULARY = ROOT / "data" / "formulary.csv"
OUT = ROOT / "data" / "interactions.csv"
PROGRESS = ROOT / "data" / "interactions.raw.jsonl"
FAILED = ROOT / "data" / "interactions.failed.txt"
CLASS_MEMBERS = ROOT / "data" / "class_members.json"
REJECTED = ROOT / "data" / "interactions.rejected.csv"
CONFLICTS = ROOT / "data" / "review" / "grade-conflicts.csv"

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


SEVERITY_ORDER = {"monitor": 1, "warning": 2, "contraindicated": 3}


def assertions_from(
    raw: dict,
    subject_rxcui: str,
    span_id: str,
    by_name: dict[str, str],
    class_members: dict[str, list[str]],
    on_conflict=lambda conflict: None,
    context: str = "",
) -> list[InteractionAssertion]:
    """One raw reading -> assertions about formulary drugs, offline.

    A drug we do not carry, an invented severity grade, a class we have not
    mapped, or a label that names nothing all yield no assertion - the
    alternative is inventing a safety claim.

    One drug can be reached several ways in one passage. A grade from a named
    mention beats any grade from a class; among grades of the same kind the most
    severe wins, as it does across labels in the resolver. Emission order never
    decides. When named grades disagree, `on_conflict` receives
    (subject, object, span_id, grades) so a reviewer sees it. `context` is the
    passage itself, which can narrow a class phrase (class_map._CONTEXT).
    """
    name_of = {code: name for name, code in by_name.items()}
    named: dict[str, set[str]] = {}
    by_class: dict[str, list[tuple[str, str]]] = {}

    for name, severity in _items(raw, "interactions", "drug"):
        obj = _resolve_object(name, by_name)
        if obj and obj != subject_rxcui and severity in VALID_SEVERITY:
            named.setdefault(obj, set()).add(severity)
    for phrase, severity in _items(raw, "classes", "class"):
        if severity not in VALID_SEVERITY:
            continue
        excluded = excluded_text(phrase)
        members = {m for key in match_classes(phrase, context) for m in class_members.get(key, [])}
        # "diuretics except potassium-sparing diuretics": a class can be excluded too.
        members -= {m for key in match_classes(excluded) for m in class_members.get(key, [])}
        for obj in sorted(members):
            if obj == subject_rxcui or obj in named:
                continue
            if excluded and re.search(rf"\b{re.escape(name_of.get(obj, '~'))}\b", excluded):
                continue
            by_class.setdefault(obj, []).append((severity, phrase.strip()))

    out: list[InteractionAssertion] = []
    for obj, grades in named.items():
        if len(grades) > 1:
            on_conflict((subject_rxcui, obj, span_id,
                         sorted(grades, key=lambda g: -SEVERITY_ORDER[g])))
        out.append(InteractionAssertion(subject_rxcui=subject_rxcui, object_rxcui=obj,
                                        severity=max(grades, key=SEVERITY_ORDER.get),
                                        span_id=span_id))
    for obj, options in by_class.items():
        severity, phrase = max(options, key=lambda o: SEVERITY_ORDER[o[0]])
        out.append(InteractionAssertion(subject_rxcui=subject_rxcui, object_rxcui=obj,
                                        severity=severity, span_id=span_id, via_class=phrase))
    return out


_HYPHENS = re.compile(r"[\u00ad\u2010-\u2015\u2212]")


def claim_key(span_id: str, subject: str, claim: str) -> tuple[str, str, str]:
    """How a claim is identified everywhere: rebuild, review sheet, rejections.
    Case, spacing and typographic hyphens are ignored, so a reviewer's tool
    re-saving "Beta‑blockers" as "Beta-blockers" still matches."""
    return span_id, subject, " ".join(_HYPHENS.sub("-", claim).split()).casefold()


def apply_rejections(assertions: list[InteractionAssertion], rejected: list[dict],
                     unused=lambda rejection: None) -> list[InteractionAssertion]:
    """Drop claims a reviewer rejected, keyed by span, subject and claim.

    `claim` is the class phrase for a class claim, so one rejection removes
    every drug that phrase expanded to, or the object code for a named one. A
    row with `corrected_severity` regrades the claim instead of removing it,
    for a real interaction the model graded wrongly. Phrases compare case- and space-insensitively, because a rebuild may
    re-read the same label with different capitalisation; a rejection that no
    longer matches anything goes to `unused` instead of failing silently.
    Rejections live in a committed file so a rebuild cannot bring them back.
    """
    gone = {claim_key(r["span_id"], r["subject_rxcui"], r["claim"]): r for r in rejected}
    hit = set()
    kept = []
    for a in assertions:
        key = claim_key(a.span_id, a.subject_rxcui, a.via_class or a.object_rxcui)
        if key not in gone:
            kept.append(a)
            continue
        hit.add(key)
        corrected = (gone[key].get("corrected_severity") or "").strip()
        if corrected:
            kept.append(a.model_copy(update={"severity": corrected}))
    for key, r in gone.items():
        if key not in hit:
            unused(r)
    return kept


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
        # as_completed, not map: a finished call is saved the moment it lands,
        # not held in memory behind a slower one.
        for future in as_completed([pool.submit(one, j) for j in todo]):
            job, result = future.result()
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
    conflicts: list[tuple] = []
    assertions = [a for span_id in spans if span_id in raws
                  for a in assertions_from(raws[span_id], spans[span_id][1], span_id, by_name,
                                           members, on_conflict=conflicts.append,
                                           context=spans[span_id][0])]
    rejected = (list(csv.DictReader(REJECTED.open(encoding="utf-8")))
                if REJECTED.exists() else [])
    unused: list[dict] = []
    before = len(assertions)
    assertions = apply_rejections(assertions, rejected, unused=unused.append)
    print(f"{len(rejected)} reviewed rejections removed {before - len(assertions)} rows")
    for r in unused:
        print(f"  WARNING: rejection no longer matches any row: {r['subject_rxcui']} / {r['claim']}"
              f" in {r['span_id']}")

    CONFLICTS.parent.mkdir(parents=True, exist_ok=True)
    with CONFLICTS.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["subject_rxcui", "object_rxcui", "span_id", "grades"])
        w.writerows((s, o, sp, " / ".join(g)) for s, o, sp, g in conflicts)
    print(f"{len(conflicts)} pairs where the model gave one drug two grades; the most severe"
          f" was kept and each is flagged in the review sheet ({CONFLICTS.name})")

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
    FAILED.unlink(missing_ok=True)  # a list from an earlier run is not this run's
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
