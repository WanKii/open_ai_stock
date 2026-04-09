"""OpenAI 兼容 LLM 提供者。

支持 OpenAI 官方 API 以及所有 OpenAI 兼容接口（如 DeepSeek、智谱等）。
使用 httpx 直接调用，避免引入 openai SDK 强依赖。
"""
from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from .base import LLMProvider

logger = logging.getLogger(__name__)


class OpenAIProvider(LLMProvider):
    name = "openai"

    def __init__(self, config: dict[str, Any]):
        self._api_key = config.get("api_key", "")
        self._base_url = config.get("base_url", "https://api.openai.com/v1").rstrip("/")
        self._model = config.get("model", "gpt-4.1-mini")
        self._timeout = config.get("timeout", 60)
        self._max_tokens = config.get("max_tokens", 4000)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    async def chat(self, system_prompt: str, user_message: str) -> str:
        url = f"{self._base_url}/chat/completions"
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "max_tokens": self._max_tokens,
            "temperature": 0.7,
        }

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(url, headers=self._headers(), json=payload)
            response.raise_for_status()
            data = response.json()

        choices = data.get("choices", [])
        if not choices:
            raise ValueError("OpenAI 返回空 choices。")
        return choices[0]["message"]["content"]

    async def test_connection(self) -> tuple[bool, str]:
        if not self._api_key:
            return False, "未配置 API Key。"

        url = f"{self._base_url}/models"
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(url, headers=self._headers())
                if response.status_code == 200:
                    return True, f"OpenAI 连接正常，模型: {self._model}。"
                return False, f"OpenAI 返回状态码 {response.status_code}。"
        except Exception as exc:
            return False, f"OpenAI 连接失败：{exc}"
