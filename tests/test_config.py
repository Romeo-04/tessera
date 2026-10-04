import pytest

from tessera.config import Settings


def test_settings_read_from_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("NEBIUS_API_KEY", "sk-test-123")
    monkeypatch.setenv("TESSERA_DATA_DIR", str(tmp_path))
    s = Settings()
    assert s.nebius_api_key == "sk-test-123"
    assert s.nebius_base_url == "https://api.tokenfactory.nebius.com/v1"
    assert s.data_dir == tmp_path


def test_settings_reject_missing_api_key(monkeypatch):
    monkeypatch.delenv("NEBIUS_API_KEY", raising=False)
    # _env_file=None: a developer's real .env must not satisfy this test.
    with pytest.raises(Exception):
        Settings(_env_file=None)
