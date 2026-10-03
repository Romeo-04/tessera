from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache

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

    # Score and name are tracked independently per concept. RxNorm's
    # highest-scoring entry for an rxcui frequently has a null name while a
    # slightly lower-scoring duplicate carries the real one, so taking the top
    # entry wholesale leaves the user confirming a blank.
    best_score: dict[str, float] = {}
    best_name: dict[str, str] = {}
    for c in raw:
        rxcui = c.get("rxcui")
        if not rxcui:
            continue
        try:
            score = float(c.get("score", 0))
        except (TypeError, ValueError):
            continue
        if score > best_score.get(rxcui, float("-inf")):
            best_score[rxcui] = score
        name = (c.get("name") or "").strip()
        if name and not best_name.get(rxcui):
            best_name[rxcui] = name

    best_by_rxcui: dict[str, tuple[float, str]] = {
        rxcui: (score, best_name.get(rxcui, "")) for rxcui, score in best_score.items()
    }

    if not best_by_rxcui:
        return []

    top = max(score for score, _ in best_by_rxcui.values())
    if top <= 0:
        return []

    out = [
        Candidate(
            rxcui=f"RXCUI:{rxcui}",
            display_name=name,
            score=score / top,
            raw_score=score,
        )
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


@lru_cache(maxsize=4096)
def ingredients_of(rxcui: str) -> tuple[tuple[str, str], ...]:
    """The ingredient(s) an RxNorm concept is made of, as (code, name) pairs.

    Labels resolve to strength-level concepts ("metformin 500 MG", an SCDC);
    the formulary and the interaction table are keyed by ingredient. The
    history endpoint is used because it answers for obsolete concepts too -
    approximateTerm still returns some (316256 has been obsolete since 2009).
    """
    num = rxcui.removeprefix("RXCUI:")
    r = httpx.get(f"{BASE}/rxcui/{num}/historystatus.json", timeout=TIMEOUT)
    r.raise_for_status()
    hist = r.json().get("rxcuiStatusHistory") or {}
    attrs = hist.get("attributes") or {}
    if attrs.get("tty") == "IN":
        return ((f"RXCUI:{num}", attrs.get("name") or ""),)

    found: dict[str, str] = {}
    for part in (hist.get("definitionalFeatures") or {}).get("ingredientAndStrength") or []:
        if part.get("baseRxcui"):
            found.setdefault(f"RXCUI:{part['baseRxcui']}", part.get("baseName") or "")
    if found:
        return tuple(found.items())

    r = httpx.get(f"{BASE}/rxcui/{num}/related.json", params={"tty": "IN"}, timeout=TIMEOUT)
    r.raise_for_status()
    for group in (r.json().get("relatedGroup") or {}).get("conceptGroup") or []:
        for p in group.get("conceptProperties") or []:
            found.setdefault(f"RXCUI:{p['rxcui']}", p.get("name") or "")
    return tuple(found.items())


# Only the leading candidates decide the answer and the runner-up margin, and
# each needs a lookup, so the tail is not mapped.
MAP_TOP = 5


def match_ingredients(
    term: str,
    max_entries: int = 20,
    match_fn=approximate_match,
    ingredient_fn=ingredients_of,
) -> list[Candidate]:
    """approximate_match, answered at the level the evidence is keyed by.

    Each candidate is replaced by its ingredient, and candidates sharing an
    ingredient collapse to the best-scoring one - three strengths of metformin
    are one identification, not a three-way ambiguity. Two cases keep the
    candidate's own code instead, so they stay visible rather than vanish:
    a combination product (answering "lisinopril" for lisinopril/HCTZ would
    name a drug the patient does not take alone), and a concept whose
    ingredient lookup failed.
    """
    def lookup(c: Candidate) -> tuple[tuple[str, str], ...]:
        try:
            return ingredient_fn(c.rxcui)
        except httpx.HTTPError:
            return ()

    top = match_fn(term, max_entries=max_entries)[:MAP_TOP]
    # One lookup per candidate, concurrently: sequential lookups made a
    # seven-bottle photo take ~40 seconds against the live service.
    with ThreadPoolExecutor(max_workers=MAP_TOP) as pool:
        mapped = list(pool.map(lookup, top))

    out: dict[str, Candidate] = {}
    for c, ings in zip(top, mapped):
        if len(ings) == 1:
            code, name = ings[0]
            c = c.model_copy(update={"rxcui": code, "display_name": name or c.display_name})
        if c.rxcui not in out:
            out[c.rxcui] = c
    return list(out.values())
