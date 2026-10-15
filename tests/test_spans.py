import json

import pytest

from tessera.corpus.chunks import chunk_section
from tessera.corpus.spans import SpanStore
from tessera.errors import EvidenceMissing
from tessera.sources.dailymed import RawSection

SECTION = {
    "rxcui": "RXCUI:11289", "ingredient": "warfarin", "setid": "abcd1234-0000",
    "loinc": "34073-7", "section": "Drug Interactions",
    "text": "Inhibitors of CYP3A4 increase the effect of warfarin. Monitor INR closely.",
    "source_url": "https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=abcd1234-0000",
}


def write(tmp_path, rows):
    p = tmp_path / "sections.jsonl"
    p.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return p


def test_span_ids_match_what_the_interaction_builder_cites(tmp_path):
    """The table cites spans by ID; the store must produce the same IDs from the same text."""
    store = SpanStore.from_sections(write(tmp_path, [SECTION]))
    expected = chunk_section(RawSection(SECTION["setid"], SECTION["loinc"], SECTION["section"],
                                        SECTION["text"], SECTION["source_url"]))
    for span in expected:
        assert store.by_id(span.span_id) == span


def test_an_unknown_span_is_a_typed_error_not_a_keyerror(tmp_path):
    store = SpanStore.from_sections(write(tmp_path, [SECTION]))
    with pytest.raises(EvidenceMissing):
        store.by_id("nope")


def test_blank_lines_are_skipped(tmp_path):
    p = write(tmp_path, [SECTION])
    p.write_text(p.read_text(encoding="utf-8") + "\n\n", encoding="utf-8")
    assert len(SpanStore.from_sections(p)) >= 1


def test_a_section_without_a_source_yields_no_citable_span(tmp_path):
    store = SpanStore.from_sections(write(tmp_path, [dict(SECTION, source_url="")]))
    assert len(store) == 0
