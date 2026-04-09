"""Unit tests for configuration management (config.py)."""
from __future__ import annotations

from app.core.config import (
    _deep_merge,
    load_settings,
    mask_secrets,
    merge_incoming_settings,
    reload_settings,
    render_settings_toml,
    save_settings,
)


def test_deep_merge_basic():
    base = {"a": 1, "b": {"c": 2, "d": 3}}
    override = {"b": {"c": 99}, "e": 5}
    result = _deep_merge(base, override)
    assert result == {"a": 1, "b": {"c": 99, "d": 3}, "e": 5}


def test_deep_merge_does_not_mutate_base():
    base = {"a": {"x": 1}}
    override = {"a": {"y": 2}}
    _deep_merge(base, override)
    assert base == {"a": {"x": 1}}


def test_load_settings_returns_defaults_on_first_run():
    settings = load_settings()
    assert "data_sources" in settings
    assert "llm_providers" in settings
    assert "prompts" in settings
    assert len(settings["prompts"]) >= 6


def test_save_and_reload_settings():
    settings = load_settings()
    settings["prompts"]["market_analyst"] = "custom marker for test"
    save_settings(settings)
    reloaded = reload_settings()
    assert reloaded["prompts"]["market_analyst"] == "custom marker for test"


def test_mask_secrets_hides_tokens():
    settings = load_settings()
    settings["data_sources"]["tushare"]["token"] = "my_secret_token"
    settings["llm_providers"]["openai"]["api_key"] = "sk-123456"
    masked = mask_secrets(settings)
    assert masked["data_sources"]["tushare"]["token"] == "******"
    assert masked["data_sources"]["tushare"]["configured"] is True
    assert masked["llm_providers"]["openai"]["api_key"] == "******"
    assert masked["llm_providers"]["openai"]["configured"] is True


def test_mask_secrets_empty_token():
    settings = load_settings()
    settings["data_sources"]["akshare"]["token"] = ""
    masked = mask_secrets(settings)
    assert masked["data_sources"]["akshare"]["token"] == ""
    assert masked["data_sources"]["akshare"]["configured"] is False


def test_merge_incoming_preserves_real_secret():
    """When user sends '******', the real secret should be kept."""
    reload_settings()
    # Set a real token
    save_settings({"data_sources": {"tushare": {"token": "real_secret"}}})
    reload_settings()
    # Simulate frontend sending masked value
    merged = merge_incoming_settings({"data_sources": {"tushare": {"token": "******"}}})
    assert merged["data_sources"]["tushare"]["token"] == "real_secret"


def test_render_settings_toml_round_trip():
    settings = load_settings()
    toml_text = render_settings_toml(settings)
    assert "[data_sources.tushare]" in toml_text
    assert "[llm_providers.openai]" in toml_text
    assert "[prompts]" in toml_text
