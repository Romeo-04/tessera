import json

import pytest

from tessera.adjudicate import MAX_RISKS, adjudicate, focus_sentences, rank_assertions
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


class LongIndex(FakeIndex):
    def by_id(self, span_id):
        span = super().by_id(span_id)
        return span.model_copy(update={"text": (
            "Exercise caution with drugs metabolized by CYP2D6. "
            "Concomitant use with SSRIs, SNRIs or Tryptophan is not recommended. "
            "Use caution with warfarin because of bleeding risk.")})


def _capturing():
    capture = {}

    class R:
        def complete(self, tier, messages, **kw):
            capture["prompt"] = messages[0]["content"]
            return json.dumps({"risks": [{"span_id": "s1", "mechanism": "m",
                                          "action": "Ask a pharmacist."}]})
    return R(), capture


def test_the_sentences_about_the_pair_are_pointed_out_for_a_class_risk():
    """Measured live: given a whole passage, the model summarised all of it and
    the verifier withheld the result. It must be told which part is this pair."""
    router, capture = _capturing()
    adjudicate([class_assertion("warning", 1, "SSRIs")], LongIndex(), router)
    focus = capture["prompt"].split("about this interaction:")[1].split("label text:")[0]
    assert "SSRIs, SNRIs or Tryptophan is not recommended" in focus
    assert "warfarin" not in focus


def test_a_named_risk_is_focused_by_the_drug_name_from_the_server_side_formulary():
    router, capture = _capturing()
    a = assertion("warning", 1).model_copy(update={"object_rxcui": "RXCUI:11289"})
    adjudicate([a], LongIndex(), router, names={"RXCUI:11289": "warfarin"})
    focus = capture["prompt"].split("about this interaction:")[1].split("label text:")[0]
    assert "warfarin because of bleeding risk" in focus and "SSRIs" not in focus


def test_without_a_matching_sentence_there_is_no_focus_line():
    router, capture = _capturing()
    adjudicate([assertion("warning", 1)], LongIndex(), router)
    assert "about this interaction:" not in capture["prompt"]


def test_two_pairs_citing_one_passage_each_get_their_own_explanation():
    """Review finding: answers keyed by span_id alone gave both pairs the last one."""
    capture = {}

    class R:
        def complete(self, tier, messages, **kw):
            prompt = messages[0]["content"]
            ids = [line.split(": ", 1)[1] for line in prompt.splitlines() if line.startswith("span_id: ")]
            capture["ids"] = ids
            return json.dumps({"risks": [{"span_id": i, "mechanism": f"about {i}",
                                          "action": "Ask a pharmacist."} for i in ids]})

    a = assertion("warning", 1).model_copy(update={"object_rxcui": "RXCUI:11289"})
    b = class_assertion("warning", 1, "SSRIs")
    out = adjudicate([a, b], LongIndex(), R(), names={"RXCUI:11289": "warfarin"})
    assert len(set(capture["ids"])) == 2
    assert len({r.mechanism for r in out}) == 2
    assert all(r.span_id == "s1" for r in out)


def test_a_class_term_inside_a_narrower_class_is_not_the_focus():
    text = ("Diuretics: excessive drop in blood pressure. "
            "Potassium-sparing diuretics (spironolactone) can increase the risk of hyperkalemia.")
    focus = focus_sentences(text, "diuretics")
    assert focus == "Diuretics: excessive drop in blood pressure."


def test_focus_does_not_split_on_e_g():
    text = "Use caution with NSAIDs (e.g. ibuprofen) because of bleeding. Other text."
    assert focus_sentences(text, "NSAIDs") == "Use caution with NSAIDs (e.g. ibuprofen) because of bleeding."


def test_a_blank_term_or_one_ending_in_a_bracket_is_handled():
    assert focus_sentences("Anything at all.", "   ") == ""
    assert focus_sentences("Avoid ARBs (losartan). Other.", "ARBs (losartan)") == "Avoid ARBs (losartan)."
