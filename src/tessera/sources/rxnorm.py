from __future__ import annotations

import httpx

from tessera.schemas import Candidate

BASE = "https://rxnav.nlm.nih.gov/REST"
TIMEOUT = httpx.Timeout(10.0)


def approximate_match(term: str, max_entries: int = 20) -> list[Candidate]:
    """Fuzzy-match a (possibly misread) label string to RxNorm concepts.

    RxNorm's approximateTerm endpoint is built for noisy input, which is what
    OCR off a curved bottle gives us. Observed: "METF0RMIN 500" (digit zero)
    still resolves to metformin 500 MG.

    Two properties of the live response shape this function:

    1. The raw ``score`` is unbounded — roughly 8-15 in practice, not a 0-100
       percentage. Its absolute value says little, so each response is
       normalised against its own best candidate: the top scores 1.0 and the
       rest are their share of it. Downstream only ever asks "is the best
       clearly ahead of the runner-up?", which is what that preserves.
    2. The same ``rxcui`` is returned several times with different scores and
       sometimes a null name. Collapsed here to its best-scoring entry, so
       callers see one row per distinct drug concept.

    Returns best-scoring first; empty when nothing matches.
    """
    r = httpx.get(
        f"{BASE}/approximateTerm.json",
        params={"term": term, "maxEntries": max_entries},
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    raw = r.json().get("approximateGroup", {}).get("candidate", []) or []

    best_by_rxcui: dict[str, tuple[float, str]] = {}
    for c in raw:
        rxcui = c.get("rxcui")
        if not rxcui:
            continue
        try:
            score = float(c.get("score", 0))
        except (TypeError, ValueError):
            continue
        name = c.get("name") or ""
        prev = best_by_rxcui.get(rxcui)
        if prev is None or score > prev[0]:
            # Keep the better score, and prefer a real name over a null one.
            best_by_rxcui[rxcui] = (score, name or (prev[1] if prev else ""))

    if not best_by_rxcui:
        return []

    top = max(score for score, _ in best_by_rxcui.values())
    if top <= 0:
        return []

    out = [
        Candidate(rxcui=f"RXCUI:{rxcui}", display_name=name, score=score / top)
        for rxcui, (score, name) in best_by_rxcui.items()
    ]
    return sorted(out, key=lambda c: -c.score)


def rxcui_name(rxcui: str) -> str | None:
    """Canonical RxNorm name for a code. Accepts 'RXCUI:123' or '123'."""
    bare = rxcui.removeprefix("RXCUI:")
    r = httpx.get(
        f"{BASE}/rxcui/{bare}/property.json",
        params={"propName": "RxNorm Name"},
        timeout=TIMEOUT,
    )
    if r.status_code != 200:
        return None
    props = r.json().get("propConceptGroup", {}).get("propConcept", [])
    return props[0]["propValue"] if props else None
