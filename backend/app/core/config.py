from __future__ import annotations

import copy
import json
import os
import tomllib
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[3]
CONFIG_DIR = PROJECT_ROOT / "config"
DATA_DIR = PROJECT_ROOT / "data"
SETTINGS_PATH = CONFIG_DIR / "local_settings.toml"
SQLITE_PATH = DATA_DIR / "app.db"
DUCKDB_PATH = DATA_DIR / "market.duckdb"


DEFAULT_SETTINGS: dict[str, Any] = {
    "data_sources": {
        "tushare": {
            "enabled": False,
            "priority": 1,
            "token": "",
            "base_url": "https://api.tushare.pro",
            "supports": ["symbols", "quotes", "financials", "news"],
        },
        "akshare": {
            "enabled": True,
            "priority": 2,
            "token": "",
            "base_url": "https://akshare.akfamily.xyz",
            "supports": ["symbols", "quotes", "financials"],
        },
        "baostock": {
            "enabled": False,
            "priority": 3,
            "token": "",
            "base_url": "http://www.baostock.com",
            "supports": ["symbols", "quotes", "financials"],
        },
    },
    "llm_providers": {
        "openai": {
            "enabled": False,
            "base_url": "https://api.openai.com/v1",
            "model": "gpt-4.1-mini",
            "api_key": "",
            "timeout": 60,
            "max_tokens": 4000,
        },
        "anthropic": {
            "enabled": False,
            "base_url": "https://api.anthropic.com",
            "model": "claude-3-5-sonnet-latest",
            "api_key": "",
            "timeout": 60,
            "max_tokens": 4000,
        },
    },
    "source_priority_by_dataset": {
        "quotes": ["tushare", "akshare", "baostock"],
        "financials": ["tushare", "akshare", "baostock"],
        "news": ["tushare", "akshare"],
        "symbols": ["tushare", "akshare", "baostock"],
    },
    "prompts": {
        "market_analyst": "你是一名A股市场分析师。请从宏观环境、市场风格、资金偏好、行业景气度角度评估该股票当前所处环境。",
        "fundamental_analyst": "你是一名A股基本面分析师。请从财务质量、业务模式、竞争优势、估值合理性角度评估该股票。",
        "news_analyst": "你是一名A股新闻分析师。请从最近新闻、公告、舆情事件和潜在催化剂角度评估该股票。",
        "index_analyst": "你是一名A股大盘分析师。请结合主要指数和市场风险偏好判断系统性风险。",
        "sector_analyst": "你是一名A股板块分析师。请从板块轮动、行业趋势、同业对比角度评估该股票。",
        "final_summarizer": "你是一名投资研究总监。请汇总多个分析师的结论，输出辅助决策型总结，不构成投资建议。",
    },
}


def ensure_project_dirs() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)


_settings_cache: dict[str, Any] | None = None


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _render_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        return "[" + ", ".join(_render_value(item) for item in value) + "]"
    return json.dumps(value, ensure_ascii=False)


def render_settings_toml(settings: dict[str, Any]) -> str:
    lines: list[str] = []

    for source_name, source in settings["data_sources"].items():
        lines.append(f"[data_sources.{source_name}]")
        for key, value in source.items():
            lines.append(f"{key} = {_render_value(value)}")
        lines.append("")

    for provider_name, provider in settings["llm_providers"].items():
        lines.append(f"[llm_providers.{provider_name}]")
        for key, value in provider.items():
            lines.append(f"{key} = {_render_value(value)}")
        lines.append("")

    lines.append("[source_priority_by_dataset]")
    for key, value in settings["source_priority_by_dataset"].items():
        lines.append(f"{key} = {_render_value(value)}")
    lines.append("")

    lines.append("[prompts]")
    for key, value in settings["prompts"].items():
        lines.append(f"{key} = {_render_value(value)}")

    return "\n".join(lines).strip() + "\n"


def save_settings(settings: dict[str, Any]) -> dict[str, Any]:
    global _settings_cache
    ensure_project_dirs()
    merged = _deep_merge(DEFAULT_SETTINGS, settings)
    SETTINGS_PATH.write_text(render_settings_toml(merged), encoding="utf-8")
    _settings_cache = merged
    return copy.deepcopy(merged)


def _load_persisted_settings() -> dict[str, Any]:
    """加载磁盘配置并缓存，不包含运行时环境变量覆盖。"""
    global _settings_cache
    if _settings_cache is not None:
        return copy.deepcopy(_settings_cache)

    ensure_project_dirs()
    if not SETTINGS_PATH.exists():
        save_settings(DEFAULT_SETTINGS)
        return copy.deepcopy(_settings_cache or DEFAULT_SETTINGS)

    with SETTINGS_PATH.open("rb") as handle:
        loaded = tomllib.load(handle)

    _settings_cache = _deep_merge(DEFAULT_SETTINGS, loaded)
    return copy.deepcopy(_settings_cache)


def load_settings() -> dict[str, Any]:
    runtime_settings = _load_persisted_settings()
    _apply_env_overrides(runtime_settings)
    return runtime_settings


def reload_settings() -> dict[str, Any]:
    global _settings_cache
    _settings_cache = None
    return load_settings()


# ---------------------------------------------------------------------------
# 环境变量覆盖 — 支持通过 ENV 覆盖 TOML 中的敏感字段
# ---------------------------------------------------------------------------

_ENV_OVERRIDES: list[tuple[str, list[str]]] = [
    ("TUSHARE_TOKEN", ["data_sources", "tushare", "token"]),
    ("AKSHARE_TOKEN", ["data_sources", "akshare", "token"]),
    ("BAOSTOCK_TOKEN", ["data_sources", "baostock", "token"]),
    ("OPENAI_API_KEY", ["llm_providers", "openai", "api_key"]),
    ("OPENAI_BASE_URL", ["llm_providers", "openai", "base_url"]),
    ("OPENAI_MODEL", ["llm_providers", "openai", "model"]),
    ("ANTHROPIC_API_KEY", ["llm_providers", "anthropic", "api_key"]),
    ("ANTHROPIC_BASE_URL", ["llm_providers", "anthropic", "base_url"]),
    ("ANTHROPIC_MODEL", ["llm_providers", "anthropic", "model"]),
]


def _apply_env_overrides(settings: dict[str, Any]) -> dict[str, Any]:
    """将环境变量覆盖到 settings 中（仅当环境变量非空时生效）。"""
    for env_key, path in _ENV_OVERRIDES:
        value = os.environ.get(env_key, "").strip()
        if not value:
            continue
        node = settings
        for part in path[:-1]:
            node = node.setdefault(part, {})
        node[path[-1]] = value
    return settings


def mask_secrets(settings: dict[str, Any]) -> dict[str, Any]:
    masked = copy.deepcopy(settings)

    for _, config in masked.get("data_sources", {}).items():
        token = config.get("token", "")
        config["configured"] = bool(token)
        config["token"] = "******" if token else ""

    for _, config in masked.get("llm_providers", {}).items():
        api_key = config.get("api_key", "")
        config["configured"] = bool(api_key)
        config["api_key"] = "******" if api_key else ""

    masked["local_config_path"] = str(SETTINGS_PATH)
    return masked


def merge_incoming_settings(payload: dict[str, Any]) -> dict[str, Any]:
    current = _load_persisted_settings()

    for group_name in ("data_sources", "llm_providers"):
        for item_key, item_value in payload.get(group_name, {}).items():
            sanitized_value = copy.deepcopy(item_value)
            for secret_field in ("token", "api_key"):
                if sanitized_value.get(secret_field) == "******":
                    sanitized_value.pop(secret_field)
            current[group_name][item_key] = _deep_merge(current[group_name].get(item_key, {}), sanitized_value)

    if "source_priority_by_dataset" in payload:
        current["source_priority_by_dataset"] = _deep_merge(
            current["source_priority_by_dataset"], payload["source_priority_by_dataset"]
        )

    if "prompts" in payload:
        current["prompts"] = _deep_merge(current["prompts"], payload["prompts"])

    return current
