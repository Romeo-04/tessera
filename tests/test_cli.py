import pytest
from typer.testing import CliRunner

from tessera import cli
from tessera.errors import RateLimitedError, UpstreamError
from tessera.schemas import RankedRisk, SessionResult

runner = CliRunner()


@pytest.fixture
def wired(monkeypatch, tmp_path):
    """Stub out everything that needs credentials or built data files."""
    monkeypatch.setattr(cli, "_load_corpus", lambda s: (object(), object(), set(), set()))

    class FakeRouter:
        def calls(self):
            return []

    monkeypatch.setattr(cli, "Router", FakeRouter)
    img = tmp_path / "a.jpg"
    img.write_bytes(b"x")

    class S:
        data_dir = tmp_path

    monkeypatch.setattr(cli, "get_settings", lambda: S())
    return img


def _risk(**kw):
    base = dict(
        subject="RXCUI:11289", object="RXCUI:1191",
        subject_name="warfarin", object_name="aspirin",
        severity="warning", mechanism="Additive bleeding risk.",
        span_id="s1",
        source_url="https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=x",
        action="Ask a pharmacist.",
    )
    base.update(kw)
    return RankedRisk(**base)


def test_risks_render_with_drug_names(monkeypatch, wired):
    monkeypatch.setattr(
        cli, "run_session",
        lambda *a, **k: SessionResult(risks=[_risk()], status="ok"),
    )
    result = runner.invoke(cli.app, [str(wired)])
    assert result.exit_code == 0
    assert "warfarin" in result.stdout
    assert "aspirin" in result.stdout


def test_a_code_without_a_local_name_falls_back_to_the_code(monkeypatch, wired):
    monkeypatch.setattr(
        cli, "run_session",
        lambda *a, **k: SessionResult(
            risks=[_risk(object_name=None)], status="ok"
        ),
    )
    result = runner.invoke(cli.app, [str(wired)])
    assert "RXCUI:1191" in result.stdout


def test_a_rate_limit_is_a_clean_message_not_a_traceback(monkeypatch, wired):
    def boom(*a, **k):
        raise RateLimitedError("429 from nvidia/Nemotron-3-Ultra-550b-a55b")

    monkeypatch.setattr(cli, "run_session", boom)
    result = runner.invoke(cli.app, [str(wired)])
    assert result.exit_code != 0
    assert "Traceback" not in result.stdout
    assert "rate" in result.stdout.lower() or "busy" in result.stdout.lower()


def test_an_upstream_failure_does_not_print_a_risk_list(monkeypatch, wired):
    """The user must never see a short list that looks complete."""
    def boom(*a, **k):
        raise UpstreamError("gateway exploded")

    monkeypatch.setattr(cli, "run_session", boom)
    result = runner.invoke(cli.app, [str(wired)])
    assert result.exit_code != 0
    assert "No documented interactions" not in result.stdout


def test_missing_corpus_files_explain_how_to_build_them(monkeypatch, wired):
    def boom(_s):
        raise FileNotFoundError("data/index/vectors.npy")

    monkeypatch.setattr(cli, "_load_corpus", boom)
    result = runner.invoke(cli.app, [str(wired)])
    assert result.exit_code != 0
    assert "scripts/" in result.stdout
