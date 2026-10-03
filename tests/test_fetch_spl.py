import json

from scripts.fetch_spl import already_fetched


def test_a_missing_output_file_means_nothing_is_done(tmp_path):
    assert already_fetched(tmp_path / "absent.jsonl") == set()


def test_rxcuis_in_the_partial_output_are_reported_as_done(tmp_path):
    p = tmp_path / "sections.jsonl"
    p.write_text(
        "\n".join(
            json.dumps({"rxcui": r, "ingredient": "x", "setid": "s",
                        "loinc": "34073-7", "section": "Drug Interactions",
                        "text": "t", "source_url": "u"})
            for r in ("RXCUI:1", "RXCUI:1", "RXCUI:2")
        ),
        encoding="utf-8",
    )
    assert already_fetched(p) == {"RXCUI:1", "RXCUI:2"}


def test_a_torn_final_line_does_not_abort_the_resume(tmp_path):
    """A process killed mid-write leaves a partial line. That drug is simply
    refetched; losing the other 700 would be the real failure."""
    p = tmp_path / "sections.jsonl"
    p.write_text(
        json.dumps({"rxcui": "RXCUI:1"}) + '\n{"rxcui": "RXCUI:2", "inger',
        encoding="utf-8",
    )
    assert already_fetched(p) == {"RXCUI:1"}
