from __future__ import annotations

from pathlib import Path

from tessera.adjudicate import adjudicate
from tessera.extract import extract_drugs
from tessera.normalize import normalize_drugs
from tessera.privacy import to_code_set
from tessera.schemas import SessionResult
from tessera.sources.rxnorm import approximate_match
from tessera.verify import verify_risks


def run_session(
    image_paths: list[Path],
    index,
    table,
    router,
    formulary_rxcuis: set[str],
    match_fn=approximate_match,
) -> SessionResult:
    """Photographs in, cited risks out. The whole product in one function.

    The status field exists because an empty risk list is ambiguous and the
    ambiguity is dangerous. "We found nothing" and "we could not check" look
    identical to a caregiver unless the system says which one happened, so
    every return here carries a status and the notes that explain it.
    """
    records = extract_drugs(image_paths, router)
    drugs = normalize_drugs(records, formulary_rxcuis, match_fn)

    excluded = [d.record.raw_name for d in drugs if not d.in_formulary]
    unconfirmed = [
        d.record.raw_name
        for d in drugs
        if d.in_formulary and d.needs_confirmation
    ]

    # ---- everything below this line sees codes only ------------------------
    codes = to_code_set(drugs)

    notes: list[str] = []
    if excluded:
        notes.append(
            f"{len(excluded)} medication(s) are outside Tessera's checked list, "
            "so this result is incomplete: " + ", ".join(excluded)
        )
    if unconfirmed:
        notes.append(
            "Confirm these before relying on the result: " + ", ".join(unconfirmed)
        )

    if len(codes.codes) < 2:
        return SessionResult(
            risks=[],
            excluded_drugs=excluded,
            status="insufficient_drugs",
            notes=notes
            + [
                "At least two identified medications are needed to check for "
                "interactions."
            ],
        )

    assertions = table.resolve(codes)
    risks = adjudicate(assertions, index, router)
    kept, dropped = verify_risks(risks, index, router)
    if dropped:
        notes.append(
            f"{len(dropped)} statement(s) were withheld because the cited label "
            "text did not support them."
        )

    return SessionResult(
        risks=kept,
        excluded_drugs=excluded,
        status="partial" if excluded else "ok",
        notes=notes,
    )
