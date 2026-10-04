import json

import pytest

from tessera.adjudicate import MAX_RISKS, adjudicate, rank_assertions
from tessera.errors import RateLimitedError
from tessera.router import Tier
from tessera.schemas import EvidenceSpan, InteractionAssertion


class FakeIndex:
    def by_id(self, span_id):
        return EvidenceSpan(
            span_id=span_id, setid="set", section="Drug Interactions",
            text="Co-administration increases bleeding risk.",
            source_url="https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=set",
        )


def assertion(sev, i=0):
    return InteractionAssertion(
        subject_rxcui=f"RXCUI:{i}", object_rxcui="RXCUI:99",
        severity=sev, span_id=f"s{i}",
    )


def router_returning(risks, capture=None):
    class R:
        def complete(self, tier, messages, **kw):
            if capture is not None:
                capture["tier"] = tier
            return json.dumps({"risks": risks})

    return R()


def test_more_severe_interactions_rank_first():
    ranked = rank_assertions(
        [assertion("monitor", 1), assertion("contraindicated", 2),
         assertion("warning", 3)],
        FakeIndex(),
    )
    assert [a.severity for a in ranked] == ["contraindicated", "warning", "monitor"]


def test_never_surfaces_more_than_five_risks():
    """Alert fatigue is how real interaction checkers fail; the cap is clinical."""
    many = [assertion("warning", i) for i in range(14)]
    router = router_returning([
        {"span_id": a.span_id, "mechanism": "m", "action": "Ask a pharmacist."}
        for a in many
    ])
    assert len(adjudicate(many, FakeIndex(), router)) <= MAX_RISKS


def test_output_carries_the_citation_url_through():
    router = router_returning([
        {"span_id": "s1", "mechanism": "Additive bleeding risk.",
         "action": "Ask a pharmacist before combining."}
    ])
    (risk,) = adjudicate([assertion("warning", 1)], FakeIndex(), router)
    assert risk.source_url.startswith("https://dailymed.nlm.nih.gov/")
    assert risk.span_id == "s1"
    assert risk.mechanism == "Additive bleeding risk."


def test_adjudication_uses_the_deep_tier_once():
    capture = {}
    adjudicate([assertion("warning", 1)], FakeIndex(),
               router_returning([{"span_id": "s1", "mechanism": "m", "action": "a"}],
                                capture))
    assert capture["tier"] is Tier.DEEP


def test_no_assertions_means_no_model_call_at_all():
    class Exploding:
        def complete(self, tier, messages, **kw):
            raise AssertionError("must not call the model with nothing to explain")

    assert adjudicate([], FakeIndex(), Exploding()) == []


def test_a_risk_the_model_did_not_explain_is_dropped():
    router = router_returning([])  # model returned nothing for s1
    assert adjudicate([assertion("warning", 1)], FakeIndex(), router) == []


def test_upstream_failure_propagates_rather_than_returning_an_empty_list():
    """Review Focus 4: 'the API failed' must never look like 'no risks found'."""
    class Failing:
        def complete(self, tier, messages, **kw):
            raise RateLimitedError("429")

    with pytest.raises(RateLimitedError):
        adjudicate([assertion("warning", 1)], FakeIndex(), Failing())


def test_an_action_that_recommends_a_dose_change_is_replaced():
    """The safety boundary cannot live only in the prompt. Ultra returning
    dosing advice must not reach a caregiver verbatim."""
    router = router_returning([{
        "span_id": "s1", "mechanism": "Additive bleeding risk.",
        "action": "Reduce the warfarin to 2.5 mg until you see your doctor.",
    }])
    (risk,) = adjudicate([assertion("warning", 1)], FakeIndex(), router)
    assert "2.5 mg" not in risk.action
    assert "reduce" not in risk.action.lower()
    assert "pharmacist" in risk.action.lower()


def test_a_safe_routing_action_is_preserved():
    router = router_returning([{
        "span_id": "s1", "mechanism": "Additive bleeding risk.",
        "action": "Ask a pharmacist before taking these together.",
    }])
    (risk,) = adjudicate([assertion("warning", 1)], FakeIndex(), router)
    assert risk.action == "Ask a pharmacist before taking these together."


def test_a_risk_with_no_mechanism_text_is_dropped():
    """A severity grade under a blank sentence is not actionable, and would
    then be sent to the verifier to check whether a source supports ''."""
    router = router_returning([{"span_id": "s1", "mechanism": "  ", "action": "Ask."}])
    assert adjudicate([assertion("warning", 1)], FakeIndex(), router) == []


def class_assertion(sev, i, phrase):
    return assertion(sev, i).model_copy(update={"via_class": phrase})


def test_at_equal_severity_named_interactions_outrank_class_ones():
    """Under the five-risk cap, the inference from a class is what gives way."""
    ranked = rank_assertions(
        [class_assertion("warning", 1, "NSAIDs"), assertion("warning", 2),
         class_assertion("contraindicated", 3, "MAOIs")],
        FakeIndex(),
    )
    assert [a.span_id for a in ranked] == ["s3", "s2", "s1"]


def test_a_class_risk_says_which_class_the_label_named():
    capture = {}

    class R:
        def complete(self, tier, messages, **kw):
            capture["prompt"] = messages[0]["content"]
            return json.dumps({"risks": [{"span_id": "s1", "mechanism": "m",
                                          "action": "Ask a pharmacist."}]})

    (risk,) = adjudicate([class_assertion("warning", 1, "ACE inhibitors")], FakeIndex(), R())
    assert risk.via_class == "ACE inhibitors"
    assert "ACE inhibitors" in capture["prompt"]
