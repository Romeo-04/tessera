from __future__ import annotations

from collections.abc import Callable, Iterable

from tessera.schemas import Candidate, DrugRecord, NormalizedDrug
from tessera.sources.rxnorm import approximate_match

# Scores are normalised per response (top candidate = 1.0), so this margin is a
# share of the best score, not an absolute. Tuned against live RxNorm output:
# "METF0RMIN 500" separates its top two by 0.055 and is accepted; "WARFARIN
# SODIUM 5MG" separates by 0.037 and is sent back for confirmation.
AMBIGUITY_MARGIN = 0.05

# Relative scoring makes the top candidate 1.0 by construction, so it cannot
# say whether ANY match is good - only which is best. The source's own raw
# score is the one absolute signal available. Observed correct matches ran
# 8.67-14.35; this floor is deliberately well below that and is provisional
# until the gold set (Plan 2) can tune it.
MIN_RAW_SCORE = 5.0


def normalize_drugs(
    records: Iterable[DrugRecord],
    formulary_rxcuis: set[str],
    match_fn: Callable[..., list[Candidate]] = approximate_match,
) -> list[NormalizedDrug]:
    """Resolve each read label to one RXCUI, or refuse to.

    **The top candidate is the identification.** The formulary is a property of
    the drug the user actually has, never a filter for choosing a different
    one. Picking the best in-formulary candidate out of a list whose real
    winner we do not carry would answer with a medication the patient does not
    take, which is worse than answering "outside our scope".

    Three conditions each produce `rxcui=None`, and none of them is a soft
    warning - a code that is None cannot cross the privacy gate, so no risk
    list can be computed from a drug we could not name:

    - the best match is not in the formulary (we hold no evidence for it)
    - the best two are too close to tell apart (an extended-release and an
      immediate-release of the same strength look identical to a fuzzy match)
    - the best match is weak in absolute terms (a garbled label still produces
      a 1.0 relative winner)

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

        best = candidates[0]

        # Out of scope: we carry no label evidence for what this actually is.
        if best.rxcui not in formulary_rxcuis:
            out.append(NormalizedDrug(
                record=rec, rxcui=None, display_name=best.display_name,
                confidence=0.0, candidates=candidates[:3], in_formulary=False,
            ))
            continue

        too_weak = best.raw_score is not None and best.raw_score < MIN_RAW_SCORE
        ambiguous = (
            len(candidates) > 1
            and (best.score - candidates[1].score) < AMBIGUITY_MARGIN
        )

        if too_weak or ambiguous:
            out.append(NormalizedDrug(
                record=rec,
                rxcui=None,                 # the abstention has to be real
                display_name=best.display_name,
                confidence=0.0,
                candidates=candidates[:3],  # so a caller can ask
            ))
            continue

        out.append(NormalizedDrug(
            record=rec, rxcui=best.rxcui, display_name=best.display_name,
            confidence=best.score, candidates=[],
        ))
    return out
