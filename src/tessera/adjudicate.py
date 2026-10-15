from __future__ import annotations

import json
import re

from tessera.resolve import SEVERITY_RANK
from tessera.router import Tier
from tessera.schemas import InteractionAssertion, RankedRisk

SAFE_ACTION = "Ask a pharmacist before combining these."

# The safety boundary cannot live only in the prompt. NeMo Guardrails is Plan 2,
# but the CLI ships now, so a deterministic backstop runs today: any action that
# reads as dosing or treatment advice is replaced rather than shown.
UNSAFE_ACTION = re.compile(
    r"\b("
    r"reduce|increase|lower|raise|double|halve|adjust|titrate"
    r"|stop|discontinue|start|begin|switch|replace|skip|split"
    r"|\d+\s*(mg|mcg|ml|g|units?)"
    r"|take\s+(only|just|fewer|less|more|half|one|two|\d)"
    r")\b",
    re.IGNORECASE,
)

# Showing fourteen warnings is the same as showing none. Alert fatigue is the
# documented failure mode of clinical decision support, so this is a clinical
# decision, not a UI constant.
MAX_RISKS = 5

PROMPT = """You are explaining documented drug interactions to a family
caregiver with no clinical training.

For each interaction below you are given the EXACT text of the FDA-approved
label section that documents it. Write the mechanism in one plain sentence,
using ONLY what that text says. Do not add pharmacology it does not state.
When the sentences about the interaction are given, explain only what those
sentences say, not the rest of the passage.

You must NEVER recommend starting, stopping, or changing a dose. Every action
must direct the reader to a pharmacist or prescriber.

Return strict JSON only:
{{"risks": [{{"span_id": "...", "mechanism": "...", "action": "..."}}]}}

INTERACTIONS:
{block}
"""


def rank_assertions(assertions, index) -> list[InteractionAssertion]:
    """Most severe first, then named before class-inferred, so under the cap
    an inference gives way to a label that names the drug. Deterministic - the
    model never decides ordering."""
    return sorted(assertions, key=lambda a: (-SEVERITY_RANK[a.severity], a.via_class is not None))


# Sentence ends, but not "e.g. ", "i.e. " or "approx. " inside one.
_SENTENCE = re.compile(r"(?<!e\.g\.)(?<!i\.e\.)(?<!approx\.)(?<=[.;])\s+")
# Words that, right before a class term, make it a narrower class.
_NARROWER = re.compile(
    r"(potassium-sparing|potassium-depleting|sparing|depleting|loop|thiazide(-type|-like)?"
    r"|strong|moderate|weak|potent|mild"
    r"|dihydropyridine|cardioselective|selective|non)\s+$", re.IGNORECASE)


def focus_sentences(text: str, term: str | None, is_class: bool = False) -> str:
    """The sentences of a cited passage that mention `term`, verbatim.

    A Drug Interactions passage often covers several drugs. Given all of it,
    the model summarised all of it, and the verifier rightly withheld the
    result. Pointing at the sentences about this pair is still label text: the
    model is told which words matter, not anything about the user.
    """
    term = (term or "").strip()
    if not term:
        return ""
    want = re.compile(rf"(?<!\w){re.escape(term)}(?!\w)", re.IGNORECASE)

    def about(sentence: str) -> bool:
        # "diuretics" must not focus on "Potassium-sparing diuretics ...": a
        # qualifier just before the term names a different, narrower class.
        return any(not (is_class and _NARROWER.search(sentence[:m.start()]))
                   for m in want.finditer(sentence))

    return " ".join(x for x in _SENTENCE.split(text) if about(x))


def adjudicate(assertions, index, router, names: dict[str, str] | None = None) -> list[RankedRisk]:
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

    # One passage can cite several of the user's pairs, so the id the model
    # answers to is the span_id only when that is unique in this session.
    # Keyed by span_id alone, every pair from one passage got the last answer.
    shared = {a.span_id for a in top if sum(b.span_id == a.span_id for b in top) > 1}
    keys = [f"{a.span_id}#{i}" if a.span_id in shared else a.span_id
            for i, a in enumerate(top, 1)]

    def entry(key: str, a: InteractionAssertion) -> str:
        text = index.by_id(a.span_id).text
        focus = focus_sentences(text, a.via_class or (names or {}).get(a.object_rxcui),
                                is_class=a.via_class is not None)
        return (f"span_id: {key}\nseverity: {a.severity}\n"
                + (f"the label names this drug's class: {a.via_class}\n" if a.via_class else "")
                + (f"the sentences about this interaction: {focus}\n" if focus else "")
                + f"label text: {text}")

    block = "\n\n".join(entry(k, a) for k, a in zip(keys, top))

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
    for key, a in zip(keys, top):
        got = items.get(key)
        if not got:
            # No explanation means no risk shown. A severity grade with no
            # plain-language mechanism is not something a caregiver can act on.
            # The caller counts what went missing and says so - see pipeline.
            continue

        mechanism = str(got.get("mechanism", "")).strip()
        if not mechanism:
            continue

        action = str(got.get("action") or "").strip()
        if not action or UNSAFE_ACTION.search(action):
            action = SAFE_ACTION

        span = index.by_id(a.span_id)
        out.append(
            RankedRisk(
                subject=a.subject_rxcui,
                object=a.object_rxcui,
                severity=a.severity,
                mechanism=mechanism,
                span_id=a.span_id,
                source_url=span.source_url,
                action=action,
                via_class=a.via_class,
            )
        )
    return out
