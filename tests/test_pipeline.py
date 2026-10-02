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


def test_no_drugs_detected_at_all_is_insufficient_not_ok(tmp_path):
    result = run_session(
        [_img(tmp_path)], FakeIndex(), FakeTable([ASSERTION]),
        ScriptedRouter([]), FORMULARY, match_fn=fake_match,
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
