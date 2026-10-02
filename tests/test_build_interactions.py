import json

from scripts.build_interactions import extract_assertions

FORMULARY = {
    "RXCUI:11289": "warfarin",
    "RXCUI:1191": "aspirin",
    "RXCUI:860975": "metformin",
}


class StubRouter:
    def __init__(self, payload):
        self.payload = payload
        self.seen_tier = None

    def complete(self, tier, messages, **kw):
        self.seen_tier = tier
        return json.dumps(self.payload)


def test_named_drugs_become_assertions_against_the_subject():
    router = StubRouter({"interactions": [{"drug": "aspirin", "severity": "warning"}]})
    out = extract_assertions(
        "Concomitant aspirin increases bleeding risk.",
        "RXCUI:11289", "span-1", FORMULARY, router,
    )
    assert len(out) == 1
    assert out[0].subject_rxcui == "RXCUI:11289"
    assert out[0].object_rxcui == "RXCUI:1191"
    assert out[0].severity == "warning"
    assert out[0].span_id == "span-1"


def test_drugs_outside_the_formulary_are_ignored():
    router = StubRouter(
        {"interactions": [{"drug": "phenprocoumon", "severity": "warning"}]}
    )
    assert extract_assertions("text", "RXCUI:11289", "s", FORMULARY, router) == []


def test_section_with_no_interactions_yields_nothing():
    """Silence in the label must never become a fabricated assertion."""
    router = StubRouter({"interactions": []})
    assert extract_assertions(
        "No known interactions.", "RXCUI:11289", "s", FORMULARY, router
    ) == []


def test_unparseable_model_output_yields_nothing_rather_than_guessing():
    class Broken:
        def complete(self, tier, messages, **kw):
            return "not json at all"

    assert extract_assertions("text", "RXCUI:11289", "s", FORMULARY, Broken()) == []


def test_a_drug_cannot_interact_with_itself():
    router = StubRouter({"interactions": [{"drug": "warfarin", "severity": "warning"}]})
    assert extract_assertions("text", "RXCUI:11289", "s", FORMULARY, router) == []


def test_invalid_severity_grade_is_discarded():
    router = StubRouter({"interactions": [{"drug": "aspirin", "severity": "deadly"}]})
    assert extract_assertions("text", "RXCUI:11289", "s", FORMULARY, router) == []


def test_the_same_pair_is_not_asserted_twice_from_one_span():
    router = StubRouter({"interactions": [
        {"drug": "aspirin", "severity": "warning"},
        {"drug": "Aspirin", "severity": "monitor"},
    ]})
    out = extract_assertions("text", "RXCUI:11289", "s", FORMULARY, router)
    assert len(out) == 1
