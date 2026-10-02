from __future__ import annotations

from pathlib import Path

from tessera.adjudicate import MAX_RISKS, adjudicate
from tessera.extract import extract_drugs
from tessera.normalize import normalize_drugs
from tessera.privacy import to_code_set
from tessera.schemas import ConfirmationRequest, SessionResult
from tessera.sources.rxnorm import approximate_match
from tessera.verify import verify_risks


def run_session(
    image_paths: list[Path],
    index,
    table,
    router,
    formulary_rxcuis: set[str],
    match_fn=approximate_match,
    covered_rxcuis: set[str] | None = None,
) -> SessionResult:
    """Photographs in, cited risks out. The whole product in one function.

    Every return carries a status, because an empty risk list is ambiguous and
    the ambiguity is what hurts people. "We found nothing", "we could not read
    your photos", "we found something and could not explain it", and "we have
    no evidence for this drug" are four different situations that all produce
    zero risks, and a caregiver cannot tell them apart unless the system says
    which one happened.

    `covered_rxcuis`, when given, is the set of drugs the evidence corpus
    actually holds label sections for. Membership in the formulary is not the
    same thing: a drug can be in scope and still have nothing we can cite.
    """
    records = extract_drugs(image_paths, router)

    if not records:
        return SessionResult(
            risks=[], status="no_drugs_detected",
            notes=["We could not read any medication labels in these photographs. "
                   "Try again with the labels facing the camera in good light."],
        )

    drugs = normalize_drugs(records, formulary_rxcuis, match_fn)

    excluded = [d.record.raw_name for d in drugs if not d.in_formulary]
    confirmations = [
        ConfirmationRequest(raw_name=d.record.raw_name, options=d.candidates)
        for d in drugs
        if d.in_formulary and d.rxcui is None
    ]

    # ---- everything below this line sees codes only ------------------------
    codes = to_code_set(drugs)

    unchecked: list[str] = []
    if covered_rxcuis is not None:
        unchecked = [c for c in codes.codes if c not in covered_rxcuis]

    notes: list[str] = []
    if excluded:
        notes.append(
            f"{len(excluded)} medication(s) are outside Tessera's checked list, "
            "so this result is incomplete: " + ", ".join(excluded)
        )
    if confirmations:
        notes.append(
            "We could not identify these confidently and did not guess: "
            + ", ".join(c.raw_name for c in confirmations)
            + ". Confirm them to include them."
        )
    if unchecked:
        notes.append(
            f"{len(unchecked)} medication(s) are recognised but we hold no label "
            "evidence for them, so they were not checked."
        )

    if len(codes.codes) < 2:
        return SessionResult(
            risks=[], excluded_drugs=excluded, unchecked_drugs=unchecked,
            needs_confirmation=confirmations, status="insufficient_drugs",
            notes=notes + ["At least two identified medications are needed to "
                           "check for interactions."],
        )

    assertions = table.resolve(codes)
    considered = min(len(assertions), MAX_RISKS)
    if len(assertions) > MAX_RISKS:
        notes.append(
            f"{len(assertions)} documented interactions were found; showing the "
            f"{MAX_RISKS} most severe."
        )

    risks = adjudicate(assertions, index, router)
    unexplained = considered - len(risks)

    kept, dropped = verify_risks(risks, index, router)

    # Re-attach names on the device side. The server only ever saw codes; the
    # names were here the whole time, so joining them back costs nothing and
    # gives the user something they can match to a bottle in their hand.
    names = {d.rxcui: d.display_name for d in drugs if d.rxcui}
    for r in kept:
        r.subject_name = names.get(r.subject)
        r.object_name = names.get(r.object)

    if dropped:
        notes.append(
            f"{len(dropped)} statement(s) were withheld because the cited label "
            "text did not support them."
        )

    if unexplained > 0:
        # The table found interactions the model failed to put into words.
        # Silence here would read as "no interactions found", which is the
        # opposite of what happened.
        notes.append(
            f"{unexplained} documented interaction(s) could not be explained and "
            "are not shown. This result is incomplete - please ask a pharmacist."
        )
        status = "analysis_incomplete"
    elif excluded or unchecked or confirmations:
        status = "partial"
    else:
        status = "ok"

    return SessionResult(
        risks=kept, excluded_drugs=excluded, unchecked_drugs=unchecked,
        needs_confirmation=confirmations, status=status, notes=notes,
    )
