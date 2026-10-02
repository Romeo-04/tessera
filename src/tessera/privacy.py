"""The single egress point.

Everything above this line is device-local: photographs, label text, strengths,
directions, names, dates. Everything below sees a list of numeric drug codes
and nothing else. A breach of the server yields an anonymous code list.

This module is deliberately tiny so it can be audited in under a minute. If you
are adding a field to what crosses the network, it goes here, with a test, or
it does not go at all.
"""
from __future__ import annotations

from tessera.errors import TesseraError
from tessera.schemas import RXCUI_RE, CodeSet, NormalizedDrug


class PrivacyViolation(TesseraError):
    """Something that is not an RXCUI code tried to cross the boundary."""


def to_code_set(drugs: list[NormalizedDrug]) -> CodeSet:
    """Reduce resolved drugs to the only payload permitted to leave the device.

    Unresolved drugs stay home rather than being transmitted in some partial
    form; they are reported to the user locally instead.

    A malformed code raises rather than being skipped. Silently dropping it
    would turn a bug in normalisation into a quietly incomplete safety answer,
    and the whole point of this gate is that its failures are loud.
    """
    codes: set[str] = set()
    for d in drugs:
        if d.rxcui is None:
            continue
        if not RXCUI_RE.match(d.rxcui):
            raise PrivacyViolation(f"refusing to transmit {d.rxcui!r}")
        codes.add(d.rxcui)
    return CodeSet(codes=sorted(codes))
