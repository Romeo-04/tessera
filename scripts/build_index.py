"""One-off: chunk every fetched section, embed it, and save the index.

Needs NEBIUS_API_KEY (embeddings go through Token Factory). Run after
fetch_spl.py. Cost is well under a cent for the whole corpus.
"""
import json
import sys
from pathlib import Path

from tessera.corpus.chunks import chunk_section
from tessera.corpus.index import EvidenceIndex, embed_texts
from tessera.sources.dailymed import RawSection

ROOT = Path(__file__).resolve().parents[1]
SECTIONS = ROOT / "data" / "spl" / "sections.jsonl"
INTERACTIONS = ROOT / "data" / "interactions.csv"
OUT = ROOT / "data" / "index"


def main() -> int:
    if not SECTIONS.exists():
        print(f"missing {SECTIONS} — run scripts/fetch_spl.py first")
        return 1

    spans = []
    for line in SECTIONS.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        d = json.loads(line)
        spans.extend(
            chunk_section(
                RawSection(
                    setid=d["setid"], loinc=d["loinc"], section=d["section"],
                    text=d["text"], source_url=d["source_url"],
                )
            )
        )

    if not spans:
        print("no spans to index")
        return 1

    print(f"chunked into {len(spans)} spans; embedding…", flush=True)
    vectors = embed_texts([s.text for s in spans])
    EvidenceIndex(spans, vectors).save(OUT)
    print(f"saved index to {OUT} — {vectors.shape}")

    # Span IDs hash the span's text, so re-chunking after DailyMed revises a
    # label silently invalidates every assertion pointing into it. Checking
    # here turns a mid-session EvidenceMissing into a build-time warning.
    if INTERACTIONS.exists():
        import csv

        known = {s.span_id for s in spans}
        with INTERACTIONS.open(encoding="utf-8") as fh:
            referenced = {r["span_id"] for r in csv.DictReader(fh)}
        stale = referenced - known
        if stale:
            print(
                f"\nWARNING: {len(stale)} of {len(referenced)} interaction rows "
                "reference spans that no longer exist. The labels changed under "
                "the frozen table — re-run scripts/build_interactions.py."
            )
        else:
            print(f"\nall {len(referenced)} interaction rows resolve to live spans")

    return 0


if __name__ == "__main__":
    sys.exit(main())
