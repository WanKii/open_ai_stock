"""Anthropic LLM 提供者。

使用 httpx 直接调用 Anthropic Messages API，避免引入 anthropic SDK 强依赖。
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

from .base import LLMProvider

logger = logging.getLogger(__name__)


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def __init__(self, config: dict[str, Any]):
        self._api_key = config.get("api_key", "")
        self._base_url = config.get("base_url", "https://api.anthropic.com").rstrip("/")
        self._model = config.get("model", "claude-3-5-sonnet-latest")
        self._timeout = config.get("timeout", 60)
        self._max_tokens = config.get("max_tokens", 4000)

    def _headers(self) -> dict[str, str]:
        return {
            "x-api-key": self._api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }

    async def chat(self, system_prompt: str, user_message: str) -> str:
        url = f"{self._base_url}/v1/messages"
        payload = {
            "model": self._model,
            "max_tokens": self._max_tokens,
            "system": system_prompt,
            "messages": [
                {"role": "user", "content": user_message},
            ],
        }

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(url, headers=self._headers(), json=payload)
            response.raise_for_status()
            data = response.json()

        content_blocks = data.get("content", [])
        if not content_blocks:
            raise ValueError("Anthropic 返回空 content。")
        return content_blocks[0].get("text", "")

    async def test_connection(self) -> tuple[bool, str]:
        if not self._api_key:
            return False, "未配置 API Key。"

        url = f"{self._base_url}/v1/messages"
        payload = {
            "model": self._model,
            "max_tokens": 10,
            "messages": [{"role": "user", "content": "ping"}],
        }
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(url, headers=self._headers(), json=payload)
                if response.status_code == 200:
                    return True, f"Anthropic 连接正常，模型: {self._model}。"
                return False, f"Anthropic 返回状态码 {response.status_code}：{response.text[:200]}"
        except Exception as exc:
            return False, f"Anthropic 连接失败：{exc}"
