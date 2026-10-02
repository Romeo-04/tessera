import json

from tessera.router import Tier
from tessera.schemas import EvidenceSpan, RankedRisk
from tessera.verify import verify_risks


class FakeIndex:
    def by_id(self, span_id):
        return EvidenceSpan(
            span_id=span_id, setid="set", section="Drug Interactions",
            text="Concomitant use increases the risk of bleeding.",
            source_url="https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=set",
        )


def risk(span_id, mechanism):
    return RankedRisk(
        subject="RXCUI:1", object="RXCUI:2", severity="warning",
        mechanism=mechanism, span_id=span_id,
        source_url="https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=set",
        action="Ask a pharmacist.",
    )


def router_saying(*verdicts, capture=None):
    seq = iter(verdicts)

    class R:
        def complete(self, tier, messages, **kw):
            if capture is not None:
                capture["tier"] = tier
            return json.dumps({"supported": next(seq)})

    return R()


def test_supported_claim_is_kept():
    kept, dropped = verify_risks(
        [risk("s1", "Raises bleeding risk.")], FakeIndex(), router_saying(True)
    )
    assert len(kept) == 1
    assert dropped == []


def test_unsupported_claim_is_dropped_not_flagged():
    """A warning the user cannot verify is worse than no warning."""
    kept, dropped = verify_risks(
        [risk("s1", "Causes permanent liver failure.")],
        FakeIndex(), router_saying(False),
    )
    assert kept == []
    assert dropped == ["s1"]


def test_each_risk_is_checked_independently():
    kept, dropped = verify_risks(
        [risk("s1", "ok"), risk("s2", "invented"), risk("s3", "ok")],
        FakeIndex(), router_saying(True, False, True),
    )
    assert [k.span_id for k in kept] == ["s1", "s3"]
    assert dropped == ["s2"]


def test_unreadable_verdict_is_treated_as_unsupported():
    """Fail closed: if support cannot be confirmed, the claim does not ship."""
    class Broken:
        def complete(self, tier, messages, **kw):
            return "maybe?"

    kept, dropped = verify_risks([risk("s1", "x")], FakeIndex(), Broken())
    assert kept == []
    assert dropped == ["s1"]


def test_verification_uses_the_cheap_tool_tier_not_the_deep_one():
    capture = {}
    verify_risks([risk("s1", "x")], FakeIndex(), router_saying(True, capture=capture))
    assert capture["tier"] is Tier.TOOL


def test_the_source_text_is_actually_put_in_front_of_the_model():
    seen = {}

    class R:
        def complete(self, tier, messages, **kw):
            seen["content"] = messages[0]["content"]
            return json.dumps({"supported": True})

    verify_risks([risk("s1", "Raises bleeding risk.")], FakeIndex(), R())
    assert "Concomitant use increases the risk of bleeding." in seen["content"]
    assert "Raises bleeding risk." in seen["content"]


def test_nothing_to_verify_is_not_an_error():
    kept, dropped = verify_risks([], FakeIndex(), router_saying())
    assert kept == [] and dropped == []
