from __future__ import annotations

import json
from pathlib import Path

from tessera.corpus.chunks import chunk_section
from tessera.errors import EvidenceMissing
from tessera.schemas import EvidenceSpan
from tessera.sources.dailymed import RawSection


class SpanStore:
    """Citable label spans, looked up by ID.

    The runtime only ever asks "what is the text and source of span X?" - the
    interaction table already says which span supports which pair - so there
    is no search here and no embeddings. The store is built at startup from
    the fetched label sections with the same chunker the interaction builder
    uses, so the IDs the table cites are the IDs found here. No build step, no
    stored index, no API key.
    """

    def __init__(self, spans: list[EvidenceSpan]):
        self._by_id = {s.span_id: s for s in spans}

    def __len__(self) -> int:
        return len(self._by_id)

    @classmethod
    def from_sections(cls, path: Path) -> "SpanStore":
        spans: list[EvidenceSpan] = []
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            d = json.loads(line)
            spans.extend(chunk_section(RawSection(
                setid=d["setid"], loinc=d["loinc"], section=d["section"],
                text=d["text"], source_url=d["source_url"],
            )))
        return cls(spans)

    def by_id(self, span_id: str) -> EvidenceSpan:
        """Look up a span, or fail in a way the caller can act on.

        Span IDs hash the span's text, so re-fetching after DailyMed revises a
        label changes every ID for that label and leaves a frozen interaction
        table pointing at nothing. That must not surface as a bare KeyError
        three frames deep in adjudication.
        """
        try:
            return self._by_id[span_id]
        except KeyError as exc:
            raise EvidenceMissing(
                f"span {span_id!r} is not in the label corpus - the interaction "
                "table is probably stale; rebuild it against the current corpus"
            ) from exc
