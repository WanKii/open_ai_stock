"""LLM 提供者抽象基类。"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class LLMProvider(ABC):
    """统一 LLM 调用接口。"""

    name: str = ""

    @abstractmethod
    async def chat(self, system_prompt: str, user_message: str) -> str:
        """发送聊天请求，返回模型文本回复。"""

    @abstractmethod
    async def test_connection(self) -> tuple[bool, str]:
        """测试 API 连接。返回 (是否成功, 消息)。"""
