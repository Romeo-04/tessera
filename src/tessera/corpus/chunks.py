from __future__ import annotations

import hashlib
import re

from tessera.schemas import EvidenceSpan
from tessera.sources.dailymed import RawSection

SENTENCE_END = re.compile(r"(?<=[.;])\s+")


def chunk_section(sec: RawSection, max_chars: int = 1200) -> list[EvidenceSpan]:
    """Split a label section on sentence boundaries, never mid-sentence.

    Every span carries its citation forward, and a section that cannot resolve
    to a source URL produces no spans at all. That is what makes the citation
    guarantee structural rather than aspirational: there is no code path that
    creates an uncitable span, so there is none to leak into an answer.

    Span IDs are a hash of (setid, loinc, position, text), so re-running the
    build over unchanged labels produces identical IDs and the frozen
    interaction table keeps pointing at the right evidence.
    """
    if not sec.source_url or not sec.text.strip():
        return []

    parts: list[str] = []
    buf = ""
    for sentence in SENTENCE_END.split(sec.text):
        if len(buf) + len(sentence) + 1 > max_chars and buf:
            parts.append(buf.strip())
            buf = sentence
        else:
            buf = f"{buf} {sentence}".strip()
    if buf.strip():
        parts.append(buf.strip())

    spans: list[EvidenceSpan] = []
    for i, text in enumerate(parts):
        digest = hashlib.sha1(
            f"{sec.setid}|{sec.loinc}|{i}|{text}".encode()
        ).hexdigest()[:12]
        spans.append(
            EvidenceSpan(
                span_id=f"{sec.setid[:8]}-{sec.loinc}-{i}-{digest}",
                setid=sec.setid,
                section=sec.section,
                text=text,
                source_url=sec.source_url,
            )
        )
    return spans
