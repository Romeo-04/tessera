import json

from tessera.router import Tier
from tessera.watch import Hit, prefilter, run_watch, search_safety, triage


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


class FakeTavily:
    def __init__(self, results):
        self.results = results
        self.calls = []

    def post(self, url, json=None, headers=None, timeout=None):
        self.calls.append(json)
        return FakeResponse({"results": self.results})


class FakeRouter:
    def __init__(self, reply):
        self.reply = reply
        self.tiers = []

    def complete(self, tier, messages, **kw):
        self.tiers.append(tier)
        return self.reply


FDA = {"title": "FDA warns about warfarin and bleeding", "url": "https://www.fda.gov/drugs/x",
       "content": "FDA is warning that warfarin ...", "published_date": "2026-09-30"}
BLOG = {"title": "Warfarin tips", "url": "https://example.com/warfarin",
        "content": "warfarin warfarin", "published_date": None}
OFFTOPIC = {"title": "FDA approves new statin", "url": "https://www.fda.gov/y",
            "content": "atorvastatin news", "published_date": None}


def test_search_asks_only_fda_gov_for_the_ingredient_name():
    client = FakeTavily([FDA])
    hits = search_safety("warfarin", client, api_key="k")
    body = client.calls[0]
    assert "warfarin" in body["query"]
    assert body["include_domains"] == ["fda.gov"]
    assert hits[0].url == FDA["url"]


def test_prefilter_drops_hits_not_on_fda_gov():
    hits = [Hit.from_tavily(FDA), Hit.from_tavily(BLOG)]
    assert [h.url for h in prefilter(hits, "warfarin")] == [FDA["url"]]


def test_prefilter_drops_hits_that_do_not_name_the_ingredient():
    hits = [Hit.from_tavily(FDA), Hit.from_tavily(OFFTOPIC)]
    assert [h.url for h in prefilter(hits, "warfarin")] == [FDA["url"]]


def test_prefilter_does_not_accept_lookalike_domains():
    fake = dict(FDA, url="https://fda.gov.example.com/warfarin")
    assert prefilter([Hit.from_tavily(fake)], "warfarin") == []


def test_triage_runs_on_the_cheap_tier_and_keeps_what_it_marks_material():
    router = FakeRouter(json.dumps({"material": [0]}))
    alerts = triage([Hit.from_tavily(FDA)], "warfarin", "RXCUI:11289", router)
    assert router.tiers == [Tier.CHEAP]
    assert [a.rxcui for a in alerts] == ["RXCUI:11289"]
    assert alerts[0].title == FDA["title"]


def test_triage_summary_is_source_text_not_generated_text():
    router = FakeRouter(json.dumps({"material": [0], "summary": "invented words"}))
    alerts = triage([Hit.from_tavily(FDA)], "warfarin", "RXCUI:11289", router)
    assert "invented" not in alerts[0].summary
    assert alerts[0].summary.startswith("FDA is warning")


def test_triage_reports_an_unreadable_verdict_as_unchecked_not_as_clear():
    router = FakeRouter("not json")
    assert triage([Hit.from_tavily(FDA)], "warfarin", "RXCUI:11289", router) is None


def test_triage_ignores_indices_it_was_not_given():
    router = FakeRouter(json.dumps({"material": [0, 7, "x"]}))
    alerts = triage([Hit.from_tavily(FDA)], "warfarin", "RXCUI:11289", router)
    assert len(alerts) == 1


def test_triage_makes_no_call_when_nothing_survives_the_prefilter():
    router = FakeRouter("{}")
    assert triage([], "warfarin", "RXCUI:11289", router) == []
    assert router.tiers == []


def test_run_watch_covers_the_whole_formulary_and_keys_alerts_by_code():
    client = FakeTavily([FDA])
    router = FakeRouter(json.dumps({"material": [0]}))
    out = run_watch([("warfarin", "RXCUI:11289"), ("aspirin", "RXCUI:1191")],
                    client, router, api_key="k", now="2026-10-03T00:00:00Z")
    assert out["generated_at"] == "2026-10-03T00:00:00Z"
    assert len(client.calls) == 2
    # The FDA hit names warfarin, not aspirin, so only warfarin gets an alert.
    assert [a["rxcui"] for a in out["alerts"]] == ["RXCUI:11289"]


def test_triage_does_not_accept_a_boolean_as_an_index():
    router = FakeRouter(json.dumps({"material": [True]}))
    assert triage([Hit.from_tavily(FDA)], "warfarin", "RXCUI:11289", router) == []


def test_one_failing_drug_is_reported_and_does_not_abort_the_pass():
    import httpx

    class Flaky(FakeTavily):
        def post(self, url, json=None, headers=None, timeout=None):
            if "aspirin" in json["query"]:
                raise httpx.ConnectError("down")
            return super().post(url, json=json, headers=headers, timeout=timeout)

    out = run_watch([("aspirin", "RXCUI:1191"), ("warfarin", "RXCUI:11289")],
                    Flaky([FDA]), FakeRouter(json.dumps({"material": [0]})),
                    api_key="k", now="t")
    assert out["unchecked"] == ["RXCUI:1191"]
    assert [a["rxcui"] for a in out["alerts"]] == ["RXCUI:11289"]


def test_an_unreadable_triage_marks_the_drug_unchecked():
    out = run_watch([("warfarin", "RXCUI:11289")], FakeTavily([FDA]),
                    FakeRouter("garbage"), api_key="k", now="t")
    assert out["unchecked"] == ["RXCUI:11289"]
    assert out["alerts"] == []
