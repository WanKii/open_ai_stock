"""数据源适配器抽象基类。

所有具体适配器（akshare / tushare / baostock）继承此基类并实现对应方法。
不支持的数据类型应返回空列表。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from typing import Any


class DataSourceAdapter(ABC):
    """统一数据源适配器接口。"""

    name: str = ""

    @abstractmethod
    def test_connection(self) -> tuple[bool, str]:
        """测试连接。返回 (是否成功, 消息)。"""

    @abstractmethod
    def fetch_symbol_list(self) -> list[dict[str, Any]]:
        """获取全量 A 股股票列表。

        返回字段: symbol, exchange, name, listing_date, status, industry, area
        """

    @abstractmethod
    def fetch_daily_quotes(
        self, symbol: str, start_date: date, end_date: date
    ) -> list[dict[str, Any]]:
        """获取日线行情。

        返回字段: symbol, trade_date, open, high, low, close, volume, amount
        """

    @abstractmethod
    def fetch_financials(
        self, symbol: str, periods: int = 4
    ) -> list[dict[str, Any]]:
        """获取财务数据。

        返回字段: symbol, report_date, report_type, revenue, net_profit, roe, gross_margin
        """

    @abstractmethod
    def fetch_news(self, symbol: str, count: int = 20) -> list[dict[str, Any]]:
        """获取新闻/公告。

        返回字段: news_id, symbol, published_at, title, content, url
        """

    # ------------------------------------------------------------------
    # 工具方法
    # ------------------------------------------------------------------

    @staticmethod
    def normalize_symbol(symbol: str) -> str:
        """规范化股票代码为 XXXXXX.SH / XXXXXX.SZ 格式。"""
        s = symbol.strip().upper()
        if s.endswith((".SH", ".SZ")):
            return s
        suffix = ".SH" if s.startswith(("5", "6", "9")) else ".SZ"
        return f"{s}{suffix}"

    @staticmethod
    def strip_suffix(symbol: str) -> str:
        """去掉后缀返回纯数字代码。"""
        return symbol.replace(".SH", "").replace(".SZ", "")
