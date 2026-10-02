from __future__ import annotations

from collections.abc import Callable, Iterable

from tessera.schemas import CONFIRM_THRESHOLD, Candidate, DrugRecord, NormalizedDrug
from tessera.sources.rxnorm import approximate_match

# Scores are normalised per response (top candidate = 1.0), so this margin is
# a share of the best score, not an absolute. Tuned against live RxNorm output:
# "METF0RMIN 500" separates its top two by 0.055 and is accepted; "WARFARIN
# SODIUM 5MG" separates by 0.037 and is sent back for confirmation.
AMBIGUITY_MARGIN = 0.05


def normalize_drugs(
    records: Iterable[DrugRecord],
    formulary_rxcuis: set[str],
    match_fn: Callable[..., list[Candidate]] = approximate_match,
) -> list[NormalizedDrug]:
    """Resolve each read label to one RXCUI, or decline to.

    Two rules here matter more than raw accuracy:

    A drug outside our formulary is reported, never silently dropped. Dropping
    it would yield a confident but incomplete safety answer, and the caller
    could not tell that from a complete one.

    Two near-equal candidates mean we ask rather than guess. A 500 mg
    extended-release and a 500 mg immediate-release look nearly identical to a
    fuzzy string match and are different drugs to a pharmacist.

    Exactly one row comes back per input record, always, so the caller can
    account for every bottle the user photographed.
    """
    out: list[NormalizedDrug] = []
    for rec in records:
        query = " ".join(x for x in (rec.raw_name, rec.strength) if x)
        candidates = match_fn(query, max_entries=20)

        if not candidates:
            out.append(NormalizedDrug(record=rec, rxcui=None, display_name=None,
                                      confidence=0.0, candidates=[]))
            continue

        in_scope = [c for c in candidates if c.rxcui in formulary_rxcuis]
        if not in_scope:
            # Matched something real, but nothing we carry evidence for.
            out.append(NormalizedDrug(
                record=rec, rxcui=None, display_name=candidates[0].display_name,
                confidence=0.0, candidates=candidates[:3], in_formulary=False,
            ))
            continue

        best = in_scope[0]
        ambiguous = (
            len(in_scope) > 1
            and (best.score - in_scope[1].score) < AMBIGUITY_MARGIN
        )
        confidence = 0.0 if ambiguous else best.score
        out.append(NormalizedDrug(
            record=rec,
            rxcui=best.rxcui,
            display_name=best.display_name,
            confidence=confidence,
            # Surface the options only when we are going to ask about them.
            candidates=in_scope[:3] if confidence < CONFIRM_THRESHOLD else [],
        ))
    return out
