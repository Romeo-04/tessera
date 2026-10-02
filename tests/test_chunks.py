from tessera.corpus.chunks import chunk_section
from tessera.sources.dailymed import RawSection

SEC = RawSection(
    setid="set-1",
    loinc="34073-7",
    section="Drug Interactions",
    text=". ".join(f"Sentence number {i} about an interaction" for i in range(80)),
    source_url="https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=set-1",
)


def test_long_section_splits_into_several_spans():
    spans = chunk_section(SEC, max_chars=400)
    assert len(spans) > 1


def test_every_span_keeps_a_stable_unique_id_and_its_citation():
    spans = chunk_section(SEC, max_chars=400)
    assert len({s.span_id for s in spans}) == len(spans)
    for s in spans:
        assert s.setid == "set-1"
        assert s.source_url.endswith("setid=set-1")
        assert s.text.strip()


def test_span_ids_are_deterministic_across_runs():
    assert [s.span_id for s in chunk_section(SEC, max_chars=400)] == [
        s.span_id for s in chunk_section(SEC, max_chars=400)
    ]


def test_section_without_a_source_url_produces_no_spans():
    """The citation invariant: a span that cannot be cited is never created."""
    uncitable = RawSection(
        setid="set-1", loinc="34073-7", section="Drug Interactions",
        text="Real interaction text here.", source_url="",
    )
    assert chunk_section(uncitable) == []


def test_short_section_stays_a_single_span():
    short = RawSection(
        setid="set-2", loinc="34073-7", section="Drug Interactions",
        text="Concomitant use increases bleeding risk.",
        source_url="https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=set-2",
    )
    spans = chunk_section(short, max_chars=1200)
    assert len(spans) == 1
    assert spans[0].text == "Concomitant use increases bleeding risk."
