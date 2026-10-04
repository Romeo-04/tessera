import csv

import pytest

from tessera.resolve import InteractionTable
from tessera.schemas import CodeSet

ROWS = [
    {"subject_rxcui": "RXCUI:11289", "object_rxcui": "RXCUI:1191",
     "severity": "warning", "span_id": "s1"},
    {"subject_rxcui": "RXCUI:1191", "object_rxcui": "RXCUI:11289",
     "severity": "warning", "span_id": "s2"},
    {"subject_rxcui": "RXCUI:11289", "object_rxcui": "RXCUI:9999",
     "severity": "contraindicated", "span_id": "s3"},
]


def _table(tmp_path, rows):
    p = tmp_path / "interactions.csv"
    with p.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    return InteractionTable.load(p)


@pytest.fixture
def table(tmp_path):
    return _table(tmp_path, ROWS)


def test_resolves_only_pairs_both_present_in_the_code_set(table):
    out = table.resolve(CodeSet(codes=["RXCUI:11289", "RXCUI:1191"]))
    assert {(a.subject_rxcui, a.object_rxcui) for a in out} == {
        ("RXCUI:11289", "RXCUI:1191")
    }


def test_a_single_drug_produces_no_pairs(table):
    assert table.resolve(CodeSet(codes=["RXCUI:11289"])) == []


def test_an_empty_code_set_produces_no_pairs(table):
    assert table.resolve(CodeSet(codes=[])) == []


def test_reciprocal_duplicates_collapse_to_one_assertion(table):
    out = table.resolve(CodeSet(codes=["RXCUI:11289", "RXCUI:1191"]))
    assert len(out) == 1


def test_the_more_severe_grade_wins_when_both_directions_disagree(tmp_path):
    """One label calling a pair contraindicated outranks another calling it
    merely monitorable."""
    table = _table(tmp_path, [
        {"subject_rxcui": "RXCUI:1", "object_rxcui": "RXCUI:2",
         "severity": "monitor", "span_id": "a"},
        {"subject_rxcui": "RXCUI:2", "object_rxcui": "RXCUI:1",
         "severity": "contraindicated", "span_id": "b"},
    ])
    out = table.resolve(CodeSet(codes=["RXCUI:1", "RXCUI:2"]))
    assert len(out) == 1
    assert out[0].severity == "contraindicated"
    assert out[0].span_id == "b", "the citation must follow the grade that won"


def test_a_drug_with_no_entries_at_all_is_simply_quiet(table):
    out = table.resolve(CodeSet(codes=["RXCUI:777", "RXCUI:888"]))
    assert out == []


def test_three_drugs_resolve_every_known_pair(tmp_path):
    table = _table(tmp_path, [
        {"subject_rxcui": "RXCUI:1", "object_rxcui": "RXCUI:2",
         "severity": "warning", "span_id": "a"},
        {"subject_rxcui": "RXCUI:2", "object_rxcui": "RXCUI:3",
         "severity": "monitor", "span_id": "b"},
    ])
    out = table.resolve(CodeSet(codes=["RXCUI:1", "RXCUI:2", "RXCUI:3"]))
    assert len(out) == 2


def test_on_equal_severity_a_named_citation_beats_a_class_one(tmp_path):
    """Either direction may cite the pair; the label that names the drug is
    the stronger evidence, whichever side it sits on."""
    table = _table(tmp_path, [
        {"subject_rxcui": "RXCUI:1", "object_rxcui": "RXCUI:2",
         "severity": "warning", "span_id": "by-class", "via_class": "ACE inhibitors"},
        {"subject_rxcui": "RXCUI:2", "object_rxcui": "RXCUI:1",
         "severity": "warning", "span_id": "by-name", "via_class": ""},
    ])
    (a,) = table.resolve(CodeSet(codes=["RXCUI:1", "RXCUI:2"]))
    assert a.span_id == "by-name" and a.via_class is None


def test_a_more_severe_class_warning_still_outranks_a_milder_named_one(tmp_path):
    table = _table(tmp_path, [
        {"subject_rxcui": "RXCUI:1", "object_rxcui": "RXCUI:2",
         "severity": "contraindicated", "span_id": "by-class", "via_class": "MAOIs"},
        {"subject_rxcui": "RXCUI:2", "object_rxcui": "RXCUI:1",
         "severity": "monitor", "span_id": "by-name", "via_class": ""},
    ])
    (a,) = table.resolve(CodeSet(codes=["RXCUI:1", "RXCUI:2"]))
    assert a.span_id == "by-class"


def test_a_table_without_the_class_column_still_loads(table):
    assert all(a.via_class is None for a in table.resolve(CodeSet(codes=["RXCUI:11289", "RXCUI:1191"])))
