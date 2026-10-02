import httpx
import pytest

from tessera.errors import RateLimitedError
from tessera.router import MODEL_FOR_TIER, Router, Tier


class FakeCompletions:
    def __init__(self, parent):
        self.parent = parent

    def create(self, **kwargs):
        self.parent.seen.append(kwargs)
        if self.parent.raise_status:
            from openai import RateLimitError

            raise RateLimitError(
                "rate limited", response=self.parent._resp(), body=None
            )

        class Msg:
            content = "hello"

        class Choice:
            message = Msg()

        class Usage:
            prompt_tokens = 100
            completion_tokens = 20

        class Resp:
            choices = [Choice()]
            usage = Usage()

        return Resp()


class FakeClient:
    def __init__(self, raise_status=False):
        self.seen = []
        self.raise_status = raise_status
        self.chat = type("C", (), {"completions": FakeCompletions(self)})()

    def _resp(self):
        return httpx.Response(429, request=httpx.Request("POST", "http://x"))


def test_each_tier_maps_to_its_exact_model_id():
    assert MODEL_FOR_TIER[Tier.CHEAP] == "nvidia/Nemotron-3_5-Lightning"
    assert MODEL_FOR_TIER[Tier.TOOL] == "nvidia/nemotron-3-super-120b-a12b"
    assert MODEL_FOR_TIER[Tier.DEEP] == "nvidia/Nemotron-3-Ultra-550b-a55b"
    assert MODEL_FOR_TIER[Tier.OMNI] == "nvidia/Nemotron-3-Nano-Omni"


def test_router_sends_the_tier_model_and_returns_content(tmp_path):
    client = FakeClient()
    r = Router(client=client, db_path=tmp_path / "t.sqlite")
    out = r.complete(Tier.CHEAP, [{"role": "user", "content": "hi"}])
    assert out == "hello"
    assert client.seen[0]["model"] == "nvidia/Nemotron-3_5-Lightning"


def test_router_records_tokens_and_cost_per_call(tmp_path):
    r = Router(client=FakeClient(), db_path=tmp_path / "t.sqlite")
    r.complete(Tier.DEEP, [{"role": "user", "content": "hi"}])
    (call,) = r.calls()
    assert call.tier == "DEEP"
    assert call.prompt_tokens == 100
    assert call.completion_tokens == 20
    # Ultra: $1.00 in / $3.00 out per 1M
    assert call.cost_usd == pytest.approx(100 / 1e6 * 1.0 + 20 / 1e6 * 3.0)


def test_rate_limit_becomes_a_typed_error_not_a_crash(tmp_path):
    r = Router(client=FakeClient(raise_status=True), db_path=tmp_path / "t.sqlite")
    with pytest.raises(RateLimitedError):
        r.complete(Tier.CHEAP, [{"role": "user", "content": "hi"}])
