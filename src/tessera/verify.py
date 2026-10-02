from __future__ import annotations

import json

from tessera.router import Tier
from tessera.schemas import RankedRisk

PROMPT = """Does the SOURCE text support the CLAIM?

Answer true only if the claim is stated by, or follows directly from, the
source. Answer false if the claim adds anything the source does not say.

Return strict JSON only: {{"supported": true}} or {{"supported": false}}

SOURCE:
{source}

CLAIM:
{claim}
"""


def verify_risks(
    risks: list[RankedRisk], index, router
) -> tuple[list[RankedRisk], list[str]]:
    """Drop any claim its own citation does not support.

    Unsupported sentences are removed rather than flagged. A warning the user
    cannot verify is worse than no warning: it spends the trust that makes the
    verifiable ones worth reading.

    This fails closed. An unreadable verdict counts as unsupported, because the
    alternative is shipping a claim precisely when the check that was meant to
    catch it has broken.

    Runs on the Tool tier, not Deep. Entailment over one short span is a much
    easier question than adjudication, and this is called once per surfaced
    risk rather than once per session.

    Returns the kept risks and the span_ids of what was dropped, so the caller
    can tell the user that something was withheld.
    """
    kept: list[RankedRisk] = []
    dropped: list[str] = []

    for r in risks:
        source = index.by_id(r.span_id).text
        raw = router.complete(
            Tier.TOOL,
            [{"role": "user",
              "content": PROMPT.format(source=source, claim=r.mechanism)}],
            response_format={"type": "json_object"},
        )
        try:
            supported = bool(json.loads(raw).get("supported", False))
        except (json.JSONDecodeError, AttributeError, TypeError):
            supported = False

        if supported:
            kept.append(r)
        else:
            dropped.append(r.span_id)

    return kept, dropped
