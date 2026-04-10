"""Smoke tests for health check and settings API."""
from __future__ import annotations


def test_health_check(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"


def test_get_settings(client):
    resp = client.get("/api/settings")
    assert resp.status_code == 200
    data = resp.json()
    assert "data_sources" in data
    assert "llm_providers" in data
    assert "prompts" in data
    assert "source_priority_by_dataset" in data
    # Secrets should be masked
    for _name, source in data["data_sources"].items():
        if source.get("configured"):
            assert source["token"] == "******"
    for _name, llm in data["llm_providers"].items():
        if llm.get("configured"):
            assert llm["api_key"] == "******"


def test_update_settings_round_trip(client):
    """PUT /api/settings then GET should reflect the change."""
    resp = client.put(
        "/api/settings",
        json={"prompts": {"market_analyst": "test prompt override"}},
    )
    assert resp.status_code == 200

    resp2 = client.get("/api/settings")
    data = resp2.json()
    assert data["prompts"]["market_analyst"] == "test prompt override"


def test_update_settings_preserves_masked_secret(client):
    """Sending '******' should not overwrite the real secret."""
    # First write a real token
    client.put(
        "/api/settings",
        json={"data_sources": {"tushare": {"token": "real_token_123"}}},
    )
    # Now send masked value back
    client.put(
        "/api/settings",
        json={"data_sources": {"tushare": {"token": "******"}}},
    )
    # Reload raw settings to verify
    from app.core.config import reload_settings
    raw = reload_settings()
    assert raw["data_sources"]["tushare"]["token"] == "real_token_123"


def test_update_settings_does_not_write_env_secret_to_file(client, monkeypatch):
    from app.core.config import SETTINGS_PATH, reload_settings

    monkeypatch.setenv("OPENAI_API_KEY", "env-openai-key")
    reload_settings()

    resp = client.put(
        "/api/settings",
        json={"prompts": {"market_analyst": "env-backed prompt"}},
    )

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["llm_providers"]["openai"]["configured"] is True
    assert payload["llm_providers"]["openai"]["api_key"] == "******"
    assert "env-openai-key" not in SETTINGS_PATH.read_text(encoding="utf-8")
