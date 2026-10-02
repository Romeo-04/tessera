import json

from tessera.pipeline import run_session
from tessera.router import Tier
from tessera.schemas import Candidate, EvidenceSpan, InteractionAssertion


class FakeIndex:
    def by_id(self, span_id):
        return EvidenceSpan(
            span_id=span_id, setid="set", section="Drug Interactions",
            text="Concomitant use increases the risk of bleeding.",
            source_url="https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=set",
        )


class FakeTable:
    def __init__(self, assertions):
        self._a = assertions

    def resolve(self, codes):
        return self._a if len(codes.codes) > 1 else []


class ScriptedRouter:
    """Canned payload per tier, so the whole flow runs with no network."""

    def __init__(self, extracted):
        self.extracted = extracted

    def complete(self, tier, messages, **kw):
        if tier is Tier.OMNI:
            return json.dumps({"drugs": self.extracted})
        if tier is Tier.DEEP:
            return json.dumps({"risks": [{
                "span_id": "s1",
                "mechanism": "Increases bleeding risk.",
                "action": "Ask a pharmacist.",
            }]})
        return json.dumps({"supported": True})


def fake_match(term, max_entries=20):
    table = {
        "WARFARIN": ("RXCUI:11289", "warfarin"),
        "ASPIRIN": ("RXCUI:1191", "aspirin"),
        "PHENPROCOUMON": ("RXCUI:999999", "phenprocoumon"),
    }
    for key, (rxcui, name) in table.items():
        if key in term.upper():
            return [Candidate(rxcui=rxcui, display_name=name, score=1.0)]
    return []


FORMULARY = {"RXCUI:11289", "RXCUI:1191"}
ASSERTION = InteractionAssertion(
    subject_rxcui="RXCUI:11289", object_rxcui="RXCUI:1191",
    severity="warning", span_id="s1",
)


def _img(tmp_path):
    p = tmp_path / "a.jpg"
    p.write_bytes(b"x")
    return p


def test_two_interacting_drugs_produce_one_cited_risk(tmp_path):
    result = run_session(
        [_img(tmp_path)], FakeIndex(), FakeTable([ASSERTION]),
        ScriptedRouter([{"raw_name": "WARFARIN"}, {"raw_name": "ASPIRIN"}]),
        FORMULARY, match_fn=fake_match,
    )
    assert result.status == "ok"
    assert len(result.risks) == 1
    assert result.risks[0].source_url.startswith("https://dailymed.nlm.nih.gov/")


def test_a_single_drug_reports_insufficient_rather_than_no_risks(tmp_path):
    """Review Focus 3: an empty list must not read as 'checked, all clear'."""
    result = run_session(
        [_img(tmp_path)], FakeIndex(), FakeTable([ASSERTION]),
        ScriptedRouter([{"raw_name": "WARFARIN"}]), FORMULARY, match_fn=fake_match,
    )
    assert result.status == "insufficient_drugs"
    assert result.risks == []
    assert any("two" in n.lower() for n in result.notes)


def test_out_of_formulary_drug_marks_the_result_partial(tmp_path):
    """Review Focus 1, end to end."""
    result = run_session(
        [_img(tmp_path)], FakeIndex(), FakeTable([ASSERTION]),
        ScriptedRouter([
            {"raw_name": "WARFARIN"}, {"raw_name": "ASPIRIN"},
            {"raw_name": "PHENPROCOUMON"},
        ]),
        FORMULARY, match_fn=fake_match,
    )
    assert result.status == "partial"
    assert "PHENPROCOUMON" in result.excluded_drugs
    assert any("incomplete" in n.lower() for n in result.notes)


def test_one_identified_drug_is_insufficient_not_ok(tmp_path):
    """Distinct from reading nothing at all - see
    test_reading_no_labels_is_distinct_from_photographing_one_bottle."""
    result = run_session(
        [_img(tmp_path)], FakeIndex(), FakeTable([ASSERTION]),
        ScriptedRouter([{"raw_name": "WARFARIN"}]), FORMULARY, match_fn=fake_match,
    )
    assert result.status == "insufficient_drugs"
    assert result.risks == []


def test_a_withheld_claim_is_reported_to_the_user(tmp_path):
    class DroppingRouter(ScriptedRouter):
        def complete(self, tier, messages, **kw):
            if tier is Tier.TOOL:
                return json.dumps({"supported": False})
            return super().complete(tier, messages, **kw)

    result = run_session(
        [_img(tmp_path)], FakeIndex(), FakeTable([ASSERTION]),
        DroppingRouter([{"raw_name": "WARFARIN"}, {"raw_name": "ASPIRIN"}]),
        FORMULARY, match_fn=fake_match,
    )
    assert result.risks == []
    assert any("withheld" in n.lower() for n in result.notes)


def test_an_adjudicator_that_explains_nothing_is_not_reported_as_all_clear(tmp_path):
    """C3: the deterministic table found a real interaction and the model
    failed to explain it. Reporting 'no documented interactions' there turns a
    model hiccup into a clean bill of health."""
    class SilentAdjudicator(ScriptedRouter):
        def complete(self, tier, messages, **kw):
            if tier is Tier.DEEP:
                return json.dumps({"risks": []})
            return super().complete(tier, messages, **kw)

    result = run_session(
        [_img(tmp_path)], FakeIndex(), FakeTable([ASSERTION]),
        SilentAdjudicator([{"raw_name": "WARFARIN"}, {"raw_name": "ASPIRIN"}]),
        FORMULARY, match_fn=fake_match,
    )
    assert result.status == "analysis_incomplete"
    assert result.risks == []
    assert any("could not be explained" in n.lower() for n in result.notes)


def test_truncated_adjudication_reports_how_many_were_lost(tmp_path):
    """I4: three of five explained. The two missing may be the severe ones."""
    assertions = [
        InteractionAssertion(subject_rxcui=f"RXCUI:{i}", object_rxcui="RXCUI:9",
                             severity="warning", span_id=f"s{i}")
        for i in range(3)
    ]

    class PartialAdjudicator(ScriptedRouter):
        def complete(self, tier, messages, **kw):
            if tier is Tier.DEEP:
                return json.dumps({"risks": [
                    {"span_id": "s0", "mechanism": "m", "action": "Ask."}
                ]})
            return super().complete(tier, messages, **kw)

    result = run_session(
        [_img(tmp_path)], FakeIndex(), FakeTable(assertions),
        PartialAdjudicator([{"raw_name": "WARFARIN"}, {"raw_name": "ASPIRIN"}]),
        FORMULARY, match_fn=fake_match,
    )
    assert result.status == "analysis_incomplete"
    assert len(result.risks) == 1
    assert any("2" in n and "could not be explained" in n.lower()
               for n in result.notes)


def test_more_interactions_than_the_cap_says_so(tmp_path):
    """I3: five shown out of twelve must not read as exhaustive."""
    assertions = [
        InteractionAssertion(subject_rxcui=f"RXCUI:{i}", object_rxcui="RXCUI:9",
                             severity="warning", span_id=f"s{i}")
        for i in range(12)
    ]

    class AllExplained(ScriptedRouter):
        def complete(self, tier, messages, **kw):
            if tier is Tier.DEEP:
                return json.dumps({"risks": [
                    {"span_id": f"s{i}", "mechanism": "m", "action": "Ask."}
                    for i in range(12)
                ]})
            return super().complete(tier, messages, **kw)

    result = run_session(
        [_img(tmp_path)], FakeIndex(), FakeTable(assertions),
        AllExplained([{"raw_name": "WARFARIN"}, {"raw_name": "ASPIRIN"}]),
        FORMULARY, match_fn=fake_match,
    )
    assert len(result.risks) == 5
    assert any("12" in n for n in result.notes), "the user must learn 7 were cut"


def test_reading_no_labels_is_distinct_from_photographing_one_bottle(tmp_path):
    """I7: an Omni failure told the user their photos held too few drugs."""
    result = run_session(
        [_img(tmp_path)], FakeIndex(), FakeTable([ASSERTION]),
        ScriptedRouter([]), FORMULARY, match_fn=fake_match,
    )
    assert result.status == "no_drugs_detected"
    assert any("could not read" in n.lower() for n in result.notes)


def test_a_drug_we_hold_no_label_evidence_for_is_reported_as_unchecked(tmp_path):
    """I2: in the formulary is not the same as having evidence. 62 of 358
    formulary drugs currently have an interactions section."""
    result = run_session(
        [_img(tmp_path)], FakeIndex(), FakeTable([ASSERTION]),
        ScriptedRouter([{"raw_name": "WARFARIN"}, {"raw_name": "ASPIRIN"}]),
        FORMULARY, match_fn=fake_match,
        covered_rxcuis={"RXCUI:11289"},      # aspirin has no corpus coverage
    )
    assert "RXCUI:1191" in result.unchecked_drugs
    assert result.status == "partial"
    assert any("no label evidence" in n.lower() for n in result.notes)


def test_an_ambiguous_drug_is_surfaced_for_confirmation(tmp_path):
    """C1's other half: abstaining is only useful if the caller can ask."""
    def ambiguous_match(term, max_entries=20):
        if "WARFARIN" in term.upper():
            return [
                Candidate(rxcui="RXCUI:11289", display_name="warfarin 5 MG",
                          score=1.0, raw_score=12.0),
                Candidate(rxcui="RXCUI:1191", display_name="warfarin 2 MG",
                          score=0.99, raw_score=11.9),
            ]
        return fake_match(term, max_entries)

    result = run_session(
        [_img(tmp_path)], FakeIndex(), FakeTable([ASSERTION]),
        ScriptedRouter([{"raw_name": "WARFARIN"}, {"raw_name": "ASPIRIN"}]),
        FORMULARY, match_fn=ambiguous_match,
    )
    assert result.needs_confirmation, "the options must reach the caller"
    asked = result.needs_confirmation[0]
    assert asked.raw_name == "WARFARIN"
    assert len(asked.options) == 2
    assert {o.display_name for o in asked.options} == {
        "warfarin 5 MG", "warfarin 2 MG"
    }


def test_raw_label_text_never_reaches_the_resolver(tmp_path):
    """The privacy split, asserted end to end rather than at the gate alone."""
    seen = {}

    class SpyTable(FakeTable):
        def resolve(self, codes):
            seen["codes"] = list(codes.codes)
            return self._a

    run_session(
        [_img(tmp_path)], FakeIndex(), SpyTable([ASSERTION]),
        ScriptedRouter([
            {"raw_name": "WARFARIN", "strength": "5 mg",
             "directions": "Take one at night"},
            {"raw_name": "ASPIRIN"},
        ]),
        FORMULARY, match_fn=fake_match,
    )
    # Lexicographic, not numeric: "RXCUI:11289" < "RXCUI:1191" because '2' < '9'.
    # The ordering only needs to be canonical, not meaningful.
    assert seen["codes"] == ["RXCUI:11289", "RXCUI:1191"]
    blob = json.dumps(seen["codes"])
    for leak in ("WARFARIN", "5 mg", "night"):
        assert leak not in blob


def test_risks_are_labelled_with_drug_names_not_bare_codes(tmp_path):
    """I1: a caregiver holding seven bottles cannot act on
    "RXCUI:11289 + RXCUI:1191". The names never left the device, so
    re-attaching them locally costs nothing and breaks no privacy property."""
    result = run_session(
        [_img(tmp_path)], FakeIndex(), FakeTable([ASSERTION]),
        ScriptedRouter([{"raw_name": "WARFARIN"}, {"raw_name": "ASPIRIN"}]),
        FORMULARY, match_fn=fake_match,
    )
    risk = result.risks[0]
    assert {risk.subject_name, risk.object_name} == {"warfarin", "aspirin"}


def test_a_name_is_omitted_rather_than_invented_when_unknown(tmp_path):
    """A code we cannot name locally shows as the code, not a guess."""
    result = run_session(
        [_img(tmp_path)], FakeIndex(),
        FakeTable([InteractionAssertion(
            subject_rxcui="RXCUI:11289", object_rxcui="RXCUI:55555",
            severity="warning", span_id="s1")]),
        ScriptedRouter([{"raw_name": "WARFARIN"}, {"raw_name": "ASPIRIN"}]),
        FORMULARY, match_fn=fake_match,
    )
    risk = result.risks[0]
    assert risk.subject_name == "warfarin"
    assert risk.object_name is None
