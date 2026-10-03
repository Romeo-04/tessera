from __future__ import annotations

from pathlib import Path

import numpy as np

from tessera.config import get_settings
from tessera.errors import EvidenceMissing
from tessera.schemas import EvidenceSpan

EMBED_MODEL = "Qwen/Qwen3-Embedding-8B"


def _normalise(m: np.ndarray) -> np.ndarray:
    """Unit-length rows. Zero rows stay zero rather than becoming NaN."""
    norms = np.linalg.norm(m, axis=-1, keepdims=True)
    return m / np.clip(norms, 1e-9, None)


class EvidenceIndex:
    """Brute-force cosine search over the label-span corpus.

    The formulary is ~500 drugs x ~3 cited sections, so the corpus is a few
    thousand spans: a float32 matrix of tens of megabytes, searched in well
    under a millisecond. A vector database would add a service that has to
    stay up unattended until judging closes on 2026-12-15 and would buy
    nothing measurable at this size.
    """

    def __init__(self, spans: list[EvidenceSpan], vectors: np.ndarray):
        if len(spans) != len(vectors):
            raise ValueError(
                f"spans and vectors must be the same length: "
                f"{len(spans)} != {len(vectors)}"
            )
        self.spans = spans
        self.vectors = _normalise(vectors.astype("float32"))
        self._by_id = {s.span_id: s for s in spans}

    def search(self, query: np.ndarray, k: int = 8) -> list[tuple[EvidenceSpan, float]]:
        q = _normalise(query.astype("float32").reshape(1, -1))[0]
        scores = self.vectors @ q
        k = min(k, len(self.spans))
        top = np.argsort(-scores)[:k]
        return [(self.spans[i], float(scores[i])) for i in top]

    def by_id(self, span_id: str) -> EvidenceSpan:
        """Look up a span, or fail in a way the caller can act on.

        Span IDs hash the span's text, so a corpus rebuild after DailyMed
        revises a label changes every ID for that label and leaves a frozen
        interaction table pointing at nothing. That must not surface as a bare
        KeyError three frames deep in adjudication.
        """
        try:
            return self._by_id[span_id]
        except KeyError as exc:
            raise EvidenceMissing(
                f"span {span_id!r} is not in the index — the interaction table "
                "is probably stale; rebuild it against the current corpus"
            ) from exc

    def save(self, directory: Path) -> None:
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        np.save(directory / "vectors.npy", self.vectors)
        with (directory / "spans.jsonl").open("w", encoding="utf-8") as fh:
            for s in self.spans:
                fh.write(s.model_dump_json() + "\n")

    @classmethod
    def load(cls, directory: Path) -> "EvidenceIndex":
        directory = Path(directory)
        vectors = np.load(directory / "vectors.npy")
        spans = [
            EvidenceSpan.model_validate_json(line)
            for line in (directory / "spans.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
            if line.strip()
        ]
        return cls(spans, vectors)


def embed_texts(texts: list[str], batch: int = 64) -> np.ndarray:
    """Embed through Token Factory.

    Deliberately not routed through Router: that wraps chat completions, and
    an embedding is a different endpoint with a different response shape.
    Consequence to be aware of - embedding spend does not appear in the call
    telemetry. Measured at well under a cent for the whole corpus, so it is
    immaterial to the cost story the README tells.
    """
    import openai

    s = get_settings()
    client = openai.OpenAI(api_key=s.nebius_api_key, base_url=s.nebius_base_url)
    out: list[list[float]] = []
    for i in range(0, len(texts), batch):
        resp = client.embeddings.create(model=EMBED_MODEL, input=texts[i : i + batch])
        out.extend(d.embedding for d in resp.data)
    return np.array(out, dtype="float32")
