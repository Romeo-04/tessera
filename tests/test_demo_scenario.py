"""The seeded demo is the first thing a judge sees, so it is held to the same
invariants as a live answer: every claim cited, every citation real, no dose
advice, never more than five risks.
"""
import json
from pathlib import Path

import pytest

from tessera.adjudicate import MAX_RISKS, UNSAFE_ACTION
from tessera.schemas import RXCUI_RE, SessionResult

ROOT = Path(__file__).resolve().parents[1]
SCENARIO = ROOT / "app" / "src" / "demo" / "scenario.json"
SECTIONS = ROOT / "data" / "spl" / "sections.jsonl"


@pytest.fixture(scope="module")
def scenario():
    return json.loads(SCENARIO.read_text(encoding="utf-8"))


def _variants(scenario):
    return [SessionResult(**v) for v in scenario["variants"].values()]


def test_every_variant_is_a_valid_session_result(scenario):
    assert len(scenario["variants"]) == 2
    for v in _variants(scenario):
        assert len(v.risks) <= MAX_RISKS


def test_variant_keys_are_the_sorted_code_sets_they_answer(scenario):
    for key in scenario["variants"]:
        codes = key.split(",")
        assert codes == sorted(codes)
        assert all(RXCUI_RE.match(c) for c in codes)


def test_every_risk_cites_a_span_whose_text_contains_its_highlight(scenario):
    spans = scenario["spans"]
    for v in _variants(scenario):
        for r in v.risks:
            span = spans[r.span_id]
            assert span["highlight"] in span["text"]
            assert span["source_url"] == r.source_url


def test_every_citation_points_at_dailymed(scenario):
    for v in _variants(scenario):
        for r in v.risks:
            assert r.source_url.startswith("https://dailymed.nlm.nih.gov/")


def test_no_action_reads_as_dose_advice(scenario):
    for v in _variants(scenario):
        for r in v.risks:
            assert not UNSAFE_ACTION.search(r.action), r.action


def test_every_risk_is_named_for_the_caregiver(scenario):
    for v in _variants(scenario):
        for r in v.risks:
            assert r.subject_name and r.object_name


def test_the_cap_is_stated_only_when_it_applies(scenario):
    for v in _variants(scenario):
        if any("most severe" in n for n in v.notes):
            assert len(v.risks) == MAX_RISKS


TABLE = ROOT / "data" / "interactions.csv"


@pytest.mark.skipif(not TABLE.exists(), reason="the interaction table is built locally")
def test_every_demo_risk_is_one_the_live_table_documents(scenario):
    """The demo must never show judges a pair the live product cannot find."""
    import csv
    with TABLE.open(encoding="utf-8") as fh:
        rows = {(r["subject_rxcui"], r["object_rxcui"], r["span_id"]) for r in csv.DictReader(fh)}
    for v in _variants(scenario):
        for r in v.risks:
            assert (r.subject, r.object, r.span_id) in rows, (r.subject_name, r.object_name)


def test_leaving_the_ambiguous_drug_out_is_reported_as_partial(scenario):
    statuses = sorted(v.status for v in _variants(scenario))
    assert statuses == ["ok", "partial"]


@pytest.mark.skipif(not SECTIONS.exists(), reason="corpus is gitignored")
def test_every_span_is_verbatim_label_text(scenario):
    corpus = [json.loads(line) for line in SECTIONS.read_text(encoding="utf-8").splitlines()
              if line.strip()]
    for span_id, span in scenario["spans"].items():
        assert any(span["text"] in s["text"] and s["setid"] == span["setid"]
                   for s in corpus), span_id


def test_every_risk_carries_exactly_its_span_text(scenario):
    for v in _variants(scenario):
        for r in v.risks:
            assert r.quote == scenario["spans"][r.span_id]["text"]
