from __future__ import annotations

import json

from tessera.resolve import SEVERITY_RANK
from tessera.router import Tier
from tessera.schemas import InteractionAssertion, RankedRisk

# Showing fourteen warnings is the same as showing none. Alert fatigue is the
# documented failure mode of clinical decision support, so this is a clinical
# decision, not a UI constant.
MAX_RISKS = 5

PROMPT = """You are explaining documented drug interactions to a family
caregiver with no clinical training.

For each interaction below you are given the EXACT text of the FDA-approved
label section that documents it. Write the mechanism in one plain sentence,
using ONLY what that text says. Do not add pharmacology it does not state.

You must NEVER recommend starting, stopping, or changing a dose. Every action
must direct the reader to a pharmacist or prescriber.

Return strict JSON only:
{{"risks": [{{"span_id": "...", "mechanism": "...", "action": "..."}}]}}

INTERACTIONS:
{block}
"""


def rank_assertions(assertions, index) -> list[InteractionAssertion]:
    """Most severe first. Deterministic — the model never decides ordering."""
    return sorted(assertions, key=lambda a: -SEVERITY_RANK[a.severity])


def adjudicate(assertions, index, router) -> list[RankedRisk]:
    """Rank, cap at five, then explain each strictly from its cited span.

    Ranking happens in code before the model is involved, so what reaches the
    user in which order is a property of the documented severity grades, not of
    a model's preferences.

    Exactly one Deep-tier call is made per session, for every risk at once.
    Ultra is roughly sixteen times the input cost of Lightning, so calling it
    per risk inside a loop is where a session's cost would run away.
    """
    if not assertions:
        return []

    top = rank_assertions(assertions, index)[:MAX_RISKS]
    block = "\n\n".join(
        f"span_id: {a.span_id}\nseverity: {a.severity}\n"
        f"label text: {index.by_id(a.span_id).text}"
        for a in top
    )

    raw = router.complete(
        Tier.DEEP,
        [{"role": "user", "content": PROMPT.format(block=block)}],
        response_format={"type": "json_object"},
    )
    try:
        parsed = json.loads(raw).get("risks", [])
        items = {r["span_id"]: r for r in parsed if isinstance(r, dict) and "span_id" in r}
    except (json.JSONDecodeError, AttributeError, TypeError):
        items = {}

    out: list[RankedRisk] = []
    for a in top:
        got = items.get(a.span_id)
        if not got:
            # No explanation means no risk shown. A severity grade with no
            # plain-language mechanism is not something a caregiver can act on.
            continue
        span = index.by_id(a.span_id)
        out.append(
            RankedRisk(
                subject=a.subject_rxcui,
                object=a.object_rxcui,
                severity=a.severity,
                mechanism=str(got.get("mechanism", "")).strip(),
                span_id=a.span_id,
                source_url=span.source_url,
                action=str(got.get("action") or "").strip()
                or "Ask a pharmacist before combining these.",
            )
        )
    return out
