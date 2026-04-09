"""BaoStock 数据源适配器。

BaoStock 是免费开源的 A 股数据接口，无需 Token。
文档: http://baostock.com/baostock/index.php
"""
from __future__ import annotations

import hashlib
import logging
from datetime import date, datetime, timezone
from typing import Any

from .base import DataSourceAdapter

logger = logging.getLogger(__name__)


def _import_baostock():
    """惰性导入 baostock。"""
    import baostock as bs  # type: ignore[import-untyped]
    return bs


class BaoStockAdapter(DataSourceAdapter):
    name = "baostock"

    def __init__(self):
        self._logged_in = False

    def _ensure_login(self):
        if not self._logged_in:
            bs = _import_baostock()
            lg = bs.login()
            if lg.error_code != "0":
                raise RuntimeError(f"BaoStock 登录失败：{lg.error_msg}")
            self._logged_in = True

    def _to_baostock_code(self, symbol: str) -> str:
        """转换为 BaoStock 格式：sh.600519 / sz.000001"""
        s = self.strip_suffix(symbol)
        prefix = "sh" if symbol.endswith(".SH") else "sz"
        return f"{prefix}.{s}"

    def test_connection(self) -> tuple[bool, str]:
        try:
            bs = _import_baostock()
            lg = bs.login()
            if lg.error_code == "0":
                bs.logout()
                return True, "BaoStock 连接正常。"
            return False, f"BaoStock 登录失败：{lg.error_msg}"
        except ImportError:
            return False, "未安装 baostock 包，请执行 pip install baostock。"
        except Exception as exc:
            return False, f"BaoStock 连接失败：{exc}"

    def fetch_symbol_list(self) -> list[dict[str, Any]]:
        bs = _import_baostock()
        self._ensure_login()

        try:
            rs = bs.query_stock_basic()
        except Exception as exc:
            logger.warning("BaoStock 获取股票列表失败: %s", exc)
            return []

        rows: list[dict[str, Any]] = []
        while rs.error_code == "0" and rs.next():
            row = rs.get_row_data()
            # row: [code, code_name, ipoDate, outDate, type, status]
            if len(row) < 6:
                continue
            bao_code = row[0]
            if not bao_code.startswith(("sh.", "sz.")):
                continue

            code_num = bao_code.split(".")[1]
            suffix = ".SH" if bao_code.startswith("sh.") else ".SZ"
            symbol = f"{code_num}{suffix}"
            exchange = "SH" if suffix == ".SH" else "SZ"

            listing_date = row[2] if row[2] else None
            status = "listed" if row[5] == "1" else "delisted"

            rows.append(
                {
                    "symbol": symbol,
                    "exchange": exchange,
                    "name": row[1],
                    "listing_date": listing_date,
                    "status": status,
                    "industry": None,
                    "area": None,
                }
            )
        return rows

    def fetch_daily_quotes(
        self, symbol: str, start_date: date, end_date: date
    ) -> list[dict[str, Any]]:
        bs = _import_baostock()
        self._ensure_login()
        bao_code = self._to_baostock_code(symbol)

        try:
            rs = bs.query_history_k_data_plus(
                bao_code,
                "date,open,high,low,close,volume,amount",
                start_date=start_date.strftime("%Y-%m-%d"),
                end_date=end_date.strftime("%Y-%m-%d"),
                frequency="d",
                adjustflag="2",  # 前复权
            )
        except Exception as exc:
            logger.warning("BaoStock 获取 %s 日线失败: %s", symbol, exc)
            return []

        rows: list[dict[str, Any]] = []
        while rs.error_code == "0" and rs.next():
            data = rs.get_row_data()
            if len(data) < 7:
                continue
            try:
                trade_date = datetime.strptime(data[0], "%Y-%m-%d").date()
                rows.append(
                    {
                        "symbol": symbol,
                        "trade_date": trade_date,
                        "open": float(data[1]) if data[1] else 0.0,
                        "high": float(data[2]) if data[2] else 0.0,
                        "low": float(data[3]) if data[3] else 0.0,
                        "close": float(data[4]) if data[4] else 0.0,
                        "volume": float(data[5]) if data[5] else 0.0,
                        "amount": float(data[6]) if data[6] else 0.0,
                    }
                )
            except (ValueError, TypeError) as exc:
                logger.debug("BaoStock 行解析跳过: %s", exc)
                continue
        return rows

    def fetch_financials(self, symbol: str, periods: int = 4) -> list[dict[str, Any]]:
        bs = _import_baostock()
        self._ensure_login()
        bao_code = self._to_baostock_code(symbol)

        rows: list[dict[str, Any]] = []

        # 获取最近几年的季度数据
        current_year = date.today().year
        for year in range(current_year, current_year - 3, -1):
            for quarter in range(4, 0, -1):
                if len(rows) >= periods:
                    break
                try:
                    rs = bs.query_profit_data(
                        code=bao_code, year=year, quarter=quarter
                    )
                except Exception as exc:
                    logger.debug("BaoStock 获取 %s %d-Q%d 利润失败: %s", symbol, year, quarter, exc)
                    continue

                while rs.error_code == "0" and rs.next():
                    data = rs.get_row_data()
                    if len(data) < 5:
                        continue
                    # data: [code, pubDate, statDate, roeAvg, npMargin, gpMargin, ...]
                    stat_date_str = data[2] if len(data) > 2 else ""
                    try:
                        report_date = datetime.strptime(stat_date_str, "%Y-%m-%d").date()
                    except (ValueError, TypeError):
                        continue

                    roe = self._safe_float(data[3]) if len(data) > 3 else 0.0
                    gross_margin = self._safe_float(data[5]) if len(data) > 5 else 0.0

                    rows.append(
                        {
                            "symbol": symbol,
                            "report_date": report_date,
                            "report_type": "quarterly",
                            "revenue": 0.0,  # BaoStock profit API 不直接给 revenue
                            "net_profit": 0.0,
                            "roe": roe * 100 if abs(roe) < 1 else roe,  # 归一化为百分比
                            "gross_margin": gross_margin * 100 if abs(gross_margin) < 1 else gross_margin,
                        }
                    )
        return rows[:periods]

    def fetch_news(self, symbol: str, count: int = 20) -> list[dict[str, Any]]:
        # BaoStock 不提供新闻接口
        return []

    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        if value is None or value == "":
            return default
        try:
            return float(value)
        except (ValueError, TypeError):
            return default
