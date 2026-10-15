"""The three numbers the submission claims, plus the router ablation.

Each metric returns None rather than a flattering default when it has
nothing to measure. A perfect score on an empty set is the kind of number
this project exists to avoid publishing.
"""
from __future__ import annotations

from collections import defaultdict


def top1_accuracy(preds: dict[str, str | None], gold: dict[str, str]) -> dict:
    """RXCUI normalisation. Abstention is reported separately, never as an answer.

    Two accuracies, because they answer different questions: "when Tessera
    names a drug, is it right?" (when_answered) and "how often does it get
    the drug right at all?" (overall). Abstaining raises the first and costs
    the second; coverage shows the trade.
    """
    n = len(gold)
    answered = {k: preds.get(k) for k in gold if preds.get(k) is not None}
    correct = sum(1 for k, v in answered.items() if v == gold[k])
    return {
        "n": n,
        "abstained": n - len(answered),
        "coverage": len(answered) / n if n else None,
        "accuracy_when_answered": correct / len(answered) if answered else None,
        "accuracy_overall": correct / n if n else None,
    }


def precision_at_k(ranked: list[tuple[str, str]], relevant: set[tuple[str, str]],
                   k: int = 5) -> float | None:
    """Severity ranking. Pairs are unordered: A+B is the same risk as B+A."""
    top = [frozenset(p) for p in ranked[:k]]
    if not top:
        return None
    rel = {frozenset(p) for p in relevant}
    return sum(1 for p in top if p in rel) / len(top)


def citation_support_rate(verdicts: list[bool]) -> float | None:
    """Fraction of rendered sentences their own cited span supports."""
    return sum(verdicts) / len(verdicts) if verdicts else None


def ablation_table(calls) -> str:
    """Per-tier calls, tokens, latency and cost, from router telemetry."""
    by: dict[str, list] = defaultdict(list)
    for c in calls:
        by[c.tier].append(c)
    lines = [
        "| Tier | Model | Calls | Tokens in | Tokens out | Mean latency (ms) | Cost |",
        "|---|---|---|---|---|---|---|",
    ]
    for tier in ("VISION", "CHEAP", "TOOL", "DEEP"):
        cs = by.get(tier)
        if not cs:
            continue
        lines.append(
            f"| {tier} | {cs[0].model} | {len(cs)} | {sum(c.prompt_tokens for c in cs)} | "
            f"{sum(c.completion_tokens for c in cs)} | "
            f"{sum(c.latency_ms for c in cs) / len(cs):.0f} | "
            f"${sum(c.cost_usd for c in cs):.4f} |"
        )
    return "\n".join(lines)
