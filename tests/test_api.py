import io
import json

from fastapi.testclient import TestClient

from tessera.api.app import Deps, create_app
from tessera.api.limits import RateLimiter
from tessera.errors import RateLimitedError, UpstreamError
from tessera.pipeline import Perception
from tessera.schemas import (
    Candidate, ConfirmationRequest, DrugRecord, NormalizedDrug, RankedRisk, SessionResult,
)

JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64


def _risk():
    return RankedRisk(
        subject="RXCUI:11289", object="RXCUI:1191", severity="warning",
        mechanism="Increases bleeding risk.", span_id="s1",
        source_url="https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=x",
        action="Ask a pharmacist.",
    )


class Recorder:
    def __init__(self, result=None, exc=None):
        self.calls = []
        self.result = result
        self.exc = exc

    def __call__(self, arg):
        self.calls.append(arg)
        if self.exc:
            raise self.exc
        return self.result


def make(read=None, assess=None, limiter=None, ceiling=None, alerts_path=None):
    deps = Deps(
        read_fn=read, assess_fn=assess,
        limiter=limiter or RateLimiter(max_calls=100, per_seconds=60),
        ceiling=ceiling, alerts_path=alerts_path,
    )
    return TestClient(create_app(deps))


def test_health_reports_whether_live_mode_is_available():
    assert make().get("/health").json() == {"status": "ok", "live": False}
    live = make(read=Recorder(), assess=Recorder())
    assert live.get("/health").json() == {"status": "ok", "live": True}


# ---- the gate is the schema -------------------------------------------------

def test_assess_refuses_a_body_carrying_names():
    client = make(assess=Recorder(SessionResult(risks=[])), read=Recorder())
    r = client.post("/api/assess", json={"codes": ["RXCUI:1", "RXCUI:2"],
                                         "names": ["warfarin", "aspirin"]})
    assert r.status_code == 422


def test_assess_refuses_a_drug_name_smuggled_in_as_a_code():
    client = make(assess=Recorder(SessionResult(risks=[])), read=Recorder())
    r = client.post("/api/assess", json={"codes": ["RXCUI:1", "warfarin"]})
    assert r.status_code == 422


def test_assess_passes_only_codes_and_returns_codes_only():
    assess = Recorder(SessionResult(risks=[_risk()]))
    client = make(assess=assess, read=Recorder())
    r = client.post("/api/assess", json={"codes": ["RXCUI:1191", "RXCUI:11289"]})
    assert r.status_code == 200
    assert assess.calls[0].codes == ["RXCUI:1191", "RXCUI:11289"]
    body = r.json()
    assert body["risks"][0]["subject"] == "RXCUI:11289"
    assert body["risks"][0]["subject_name"] is None


def test_assess_refuses_an_unbounded_list():
    client = make(assess=Recorder(SessionResult(risks=[])), read=Recorder())
    r = client.post("/api/assess", json={"codes": [f"RXCUI:{i}" for i in range(41)]})
    assert r.status_code == 422


# ---- read --------------------------------------------------------------------

def _files(n, content=JPEG, ctype="image/jpeg"):
    return [("photos", (f"p{i}.jpg", io.BytesIO(content), ctype)) for i in range(n)]


def test_read_returns_names_codes_and_abstentions():
    perception = Perception(
        drugs=[NormalizedDrug(record=DrugRecord(raw_name="WARFARIN 5MG"),
                              rxcui="RXCUI:11289", display_name="warfarin", confidence=1.0)],
        excluded=["PHENPROCOUMON"],
        confirmations=[ConfirmationRequest(raw_name="METF", options=[
            Candidate(rxcui="RXCUI:6809", display_name="metformin", score=1.0)])],
    )
    read = Recorder(perception)
    client = make(read=read, assess=Recorder())
    r = client.post("/api/read", files=_files(2))
    assert r.status_code == 200
    body = r.json()
    assert body["drugs"][0]["rxcui"] == "RXCUI:11289"
    assert body["drugs"][0]["raw_name"] == "WARFARIN 5MG"
    assert body["excluded"] == ["PHENPROCOUMON"]
    assert body["confirmations"][0]["options"][0]["rxcui"] == "RXCUI:6809"
    assert len(read.calls[0]) == 2


def test_read_deletes_the_photographs_afterwards():
    seen = []

    def read(paths):
        seen.extend(paths)
        assert all(p.exists() for p in paths)
        return Perception(unreadable=True)

    make(read=read, assess=Recorder()).post("/api/read", files=_files(1))
    assert seen and not any(p.exists() for p in seen)


def test_read_refuses_too_many_photographs():
    r = make(read=Recorder(Perception()), assess=Recorder()).post(
        "/api/read", files=_files(9))
    assert r.status_code == 422


def test_read_refuses_a_file_that_is_not_an_image():
    r = make(read=Recorder(Perception()), assess=Recorder()).post(
        "/api/read", files=_files(1, content=b"%PDF-1.7", ctype="application/pdf"))
    assert r.status_code == 422


def test_read_refuses_no_photographs():
    r = make(read=Recorder(Perception()), assess=Recorder()).post("/api/read")
    assert r.status_code == 422


# ---- degradation --------------------------------------------------------------

def test_without_credentials_live_routes_point_to_the_demo():
    client = make()
    for r in (client.post("/api/read", files=_files(1)),
              client.post("/api/assess", json={"codes": ["RXCUI:1", "RXCUI:2"]})):
        assert r.status_code == 503
        assert r.json()["fallback"] == "demo"


def test_upstream_failure_is_a_502_with_no_partial_result():
    client = make(read=Recorder(), assess=Recorder(exc=UpstreamError("boom")))
    r = client.post("/api/assess", json={"codes": ["RXCUI:1", "RXCUI:2"]})
    assert r.status_code == 502
    assert "risks" not in r.json()


def test_upstream_rate_limit_is_a_429_pointing_to_the_demo():
    client = make(read=Recorder(), assess=Recorder(exc=RateLimitedError("slow")))
    r = client.post("/api/assess", json={"codes": ["RXCUI:1", "RXCUI:2"]})
    assert r.status_code == 429
    assert r.json()["fallback"] == "demo"


def test_per_caller_limit_is_a_429_pointing_to_the_demo():
    client = make(read=Recorder(), assess=Recorder(SessionResult(risks=[])),
                  limiter=RateLimiter(max_calls=1, per_seconds=600))
    ok = client.post("/api/assess", json={"codes": ["RXCUI:1", "RXCUI:2"]})
    refused = client.post("/api/assess", json={"codes": ["RXCUI:1", "RXCUI:2"]})
    assert ok.status_code == 200
    assert refused.status_code == 429
    assert refused.json()["fallback"] == "demo"


class Exceeded:
    def exceeded(self):
        return True


def test_daily_spend_ceiling_is_a_429_pointing_to_the_demo():
    assess = Recorder(SessionResult(risks=[]))
    client = make(read=Recorder(), assess=assess, ceiling=Exceeded())
    r = client.post("/api/assess", json={"codes": ["RXCUI:1", "RXCUI:2"]})
    assert r.status_code == 429
    assert r.json()["fallback"] == "demo"
    assert assess.calls == []


# ---- alerts -------------------------------------------------------------------

def test_alerts_are_served_whole_so_the_server_never_learns_whose_list_it_is(tmp_path):
    path = tmp_path / "alerts.json"
    path.write_text(json.dumps({"generated_at": "2026-10-03", "alerts": []}))
    r = make(alerts_path=path).get("/api/alerts")
    assert r.status_code == 200
    assert r.json() == {"generated_at": "2026-10-03", "alerts": []}


def test_missing_alerts_file_is_an_empty_list_not_an_error(tmp_path):
    r = make(alerts_path=tmp_path / "nope.json").get("/api/alerts")
    assert r.json() == {"generated_at": None, "alerts": [], "unchecked": []}


def test_alerts_ignore_any_attempt_to_filter_server_side(tmp_path):
    # There is deliberately no /api/alerts?codes=... - filtering is client-side,
    # so a request log never pairs an IP with a medication list.
    path = tmp_path / "alerts.json"
    alerts = [{"rxcui": "RXCUI:1"}, {"rxcui": "RXCUI:2"}]
    path.write_text(json.dumps({"generated_at": "x", "alerts": alerts}))
    r = make(alerts_path=path).get("/api/alerts", params={"codes": "RXCUI:1"})
    assert r.json()["alerts"] == alerts


def test_an_oversized_upload_is_refused_before_it_is_read():
    client = make(read=Recorder(Perception()), assess=Recorder())
    r = client.post("/api/read", content=b"x", headers={
        "content-type": "multipart/form-data; boundary=x",
        "content-length": str(80 * 1024 * 1024)})
    assert r.status_code == 413


# ---- spoken questions -----------------------------------------------------------

M4A = b"\x00\x00\x00\x20ftypM4A " + b"\x00" * 64


def _audio(content=M4A, ctype="audio/mp4"):
    return {"audio": ("q.m4a", io.BytesIO(content), ctype)}


def make_t(transcribe=None, **kw):
    deps = Deps(read_fn=Recorder(), assess_fn=Recorder(), transcribe_fn=transcribe,
                limiter=kw.get("limiter") or RateLimiter(max_calls=100, per_seconds=60),
                ceiling=kw.get("ceiling"), alerts_path=None)
    return TestClient(create_app(deps))


def test_transcribe_returns_only_text_and_deletes_the_clip():
    seen = []

    def fake(path, kind):
        seen.append(path)
        assert path.exists()
        return "is warfarin ok with atorvastatin"

    r = make_t(fake).post("/api/transcribe", files=_audio())
    assert r.status_code == 200
    assert r.json() == {"text": "is warfarin ok with atorvastatin"}
    assert not seen[0].exists()


def test_transcribe_refuses_a_file_that_is_not_audio():
    r = make_t(lambda p, k: "x").post("/api/transcribe", files=_audio(b"%PDF-1.7", "application/pdf"))
    assert r.status_code == 422


def test_transcribe_refuses_a_long_recording():
    r = make_t(lambda p, k: "x").post("/api/transcribe", files=_audio(M4A + b"\x00" * (2 * 1024 * 1024)))
    assert r.status_code == 422


def test_transcribe_without_a_model_says_type_instead():
    r = make_t(None).post("/api/transcribe", files=_audio())
    assert r.status_code == 503
    assert "type" in r.json()["detail"].lower()


def test_transcribe_is_rate_limited_like_every_live_route():
    client = make_t(lambda p, k: "x", limiter=RateLimiter(max_calls=1, per_seconds=600))
    assert client.post("/api/transcribe", files=_audio()).status_code == 200
    assert client.post("/api/transcribe", files=_audio()).status_code == 429


def test_a_platform_client_ip_header_keys_the_limit_when_configured(monkeypatch):
    """On Fly.io the edge sets Fly-Client-IP itself; clients cannot forge it."""
    monkeypatch.setenv("TESSERA_CLIENT_IP_HEADER", "Fly-Client-IP")
    client = make(read=Recorder(), assess=Recorder(SessionResult(risks=[])),
                  limiter=RateLimiter(max_calls=1, per_seconds=600))
    body = {"codes": ["RXCUI:1", "RXCUI:2"]}
    assert client.post("/api/assess", json=body, headers={"Fly-Client-IP": "1.1.1.1"}).status_code == 200
    assert client.post("/api/assess", json=body, headers={"Fly-Client-IP": "2.2.2.2"}).status_code == 200
    assert client.post("/api/assess", json=body, headers={"Fly-Client-IP": "1.1.1.1"}).status_code == 429


def test_without_the_setting_a_client_supplied_header_is_ignored():
    client = make(read=Recorder(), assess=Recorder(SessionResult(risks=[])),
                  limiter=RateLimiter(max_calls=1, per_seconds=600))
    body = {"codes": ["RXCUI:1", "RXCUI:2"]}
    assert client.post("/api/assess", json=body, headers={"Fly-Client-IP": "1.1.1.1"}).status_code == 200
    assert client.post("/api/assess", json=body, headers={"Fly-Client-IP": "9.9.9.9"}).status_code == 429


def test_an_oversized_audio_upload_is_refused_from_its_declared_length():
    r = make_t(lambda p, k: "x").post("/api/transcribe", content=b"x", headers={
        "content-type": "multipart/form-data; boundary=x",
        "content-length": str(10 * 1024 * 1024)})
    assert r.status_code == 413
