from __future__ import annotations

import csv
from itertools import combinations
from pathlib import Path

from tessera.schemas import CodeSet, InteractionAssertion

SEVERITY_RANK = {"monitor": 1, "warning": 2, "contraindicated": 3}


def _strength(a: InteractionAssertion) -> tuple[int, bool]:
    """Severity first; on a tie, a label naming the drug beats one naming its class."""
    return SEVERITY_RANK[a.severity], a.via_class is None


class InteractionTable:
    """Frozen, reviewed interaction assertions. Pure lookup, no inference.

    This is the safety-critical step, and it is deliberately the dumbest module
    in the system: a dictionary and a pairwise scan. There is no model here, so
    there is nothing here that can hallucinate an interaction that no label
    documents.
    """

    def __init__(self, assertions: list[InteractionAssertion]):
        self._by_pair: dict[tuple[str, str], InteractionAssertion] = {}
        for a in assertions:
            key = (a.subject_rxcui, a.object_rxcui)
            prev = self._by_pair.get(key)
            if prev is None or _strength(a) > _strength(prev):
                self._by_pair[key] = a

    @classmethod
    def load(cls, path: Path) -> "InteractionTable":
        with Path(path).open(encoding="utf-8") as fh:
            return cls([InteractionAssertion(**row) for row in csv.DictReader(fh)])

    def known_subjects(self) -> set[str]:
        return {subject for subject, _ in self._by_pair}

    def resolve(self, codes: CodeSet) -> list[InteractionAssertion]:
        """Every unordered pair in the code set that the table knows about.

        Labels document interactions from both sides, so the same pair often
        appears twice with different grades. Those collapse to one assertion
        keeping the more severe grade - and crucially the citation follows the
        grade that won, so the evidence shown always supports the severity
        claimed. On equal grades the citation that names the drug wins over one
        that only names its class.
        """
        found: list[InteractionAssertion] = []
        for a, b in combinations(sorted(set(codes.codes)), 2):
            candidates = [
                x
                for x in (self._by_pair.get((a, b)), self._by_pair.get((b, a)))
                if x is not None
            ]
            if candidates:
                found.append(max(candidates, key=_strength))
        return found
