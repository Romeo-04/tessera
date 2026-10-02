from pathlib import Path

from tessera.sources.dailymed import CITED_SECTIONS, parse_sections

XML = (Path(__file__).parent / "fixtures" / "sample_spl.xml").read_bytes()


def test_only_the_three_cited_sections_are_extracted():
    secs = parse_sections(XML, setid="abc-123")
    assert secs, "fixture should contain at least one cited section"
    assert {s.loinc for s in secs} <= set(CITED_SECTIONS)


def test_every_section_carries_a_resolvable_source_url():
    for s in parse_sections(XML, setid="abc-123"):
        assert s.source_url == (
            "https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=abc-123"
        )
        assert s.text.strip(), "a section with no text must not be emitted"


def test_the_drug_interactions_section_is_present_and_substantial():
    """The interaction table (Task 6) is derived from exactly this section."""
    secs = parse_sections(XML, setid="abc-123")
    interactions = [s for s in secs if s.loinc == "34073-7"]
    assert len(interactions) == 1
    assert len(interactions[0].text) > 200
    assert interactions[0].section == "Drug Interactions"


def test_label_without_cited_sections_yields_nothing_rather_than_empty_text():
    """Absence of evidence must never reach the index as evidence."""
    empty = b"<document xmlns='urn:hl7-org:v3'><component/></document>"
    assert parse_sections(empty, setid="x") == []


def test_section_whose_text_is_only_whitespace_is_dropped():
    blank = (
        b"<document xmlns='urn:hl7-org:v3'><section>"
        b"<code code='34073-7'/><text>   </text>"
        b"</section></document>"
    )
    assert parse_sections(blank, setid="x") == []
