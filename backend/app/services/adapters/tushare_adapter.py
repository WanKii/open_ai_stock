"""Tushare 数据源适配器。

Tushare Pro 是 A 股常用付费数据接口，需要 Token。
文档: https://tushare.pro/document/2
"""
from __future__ import annotations

import hashlib
import logging
from datetime import date, datetime, timezone
from typing import Any

from .base import DataSourceAdapter

logger = logging.getLogger(__name__)


def _import_tushare():
    """惰性导入 tushare。"""
    import tushare as ts  # type: ignore[import-untyped]
    return ts


class TushareAdapter(DataSourceAdapter):
    name = "tushare"

    def __init__(self, token: str = ""):
        self._token = token
        self._pro = None

    def _get_pro(self):
        if self._pro is None:
            ts = _import_tushare()
            ts.set_token(self._token)
            self._pro = ts.pro_api()
        return self._pro

    def test_connection(self) -> tuple[bool, str]:
        if not self._token:
            return False, "Tushare 未配置 Token。"
        try:
            pro = self._get_pro()
            df = pro.trade_cal(exchange="SSE", is_open="1", limit=1)
            if df is not None and len(df) > 0:
                return True, "Tushare 连接正常。"
            return False, "Tushare 返回空数据。"
        except ImportError:
            return False, "未安装 tushare 包，请执行 pip install tushare。"
        except Exception as exc:
            return False, f"Tushare 连接失败：{exc}"

    def fetch_symbol_list(self) -> list[dict[str, Any]]:
        pro = self._get_pro()

        try:
            df = pro.stock_basic(
                exchange="",
                list_status="L",
                fields="ts_code,symbol,name,area,industry,list_date",
            )
        except Exception as exc:
            logger.warning("Tushare 获取股票列表失败: %s", exc)
            return []

        if df is None or df.empty:
            return []

        rows: list[dict[str, Any]] = []
        for _, row in df.iterrows():
            ts_code = str(row.get("ts_code", ""))
            symbol = self.normalize_symbol(ts_code.replace(".SH", ".SH").replace(".SZ", ".SZ"))
            exchange = "SH" if ts_code.endswith(".SH") else "SZ"
            list_date = str(row.get("list_date", ""))
            listing_date = None
            if list_date and len(list_date) == 8:
                try:
                    listing_date = datetime.strptime(list_date, "%Y%m%d").date().isoformat()
                except ValueError:
                    pass

            rows.append(
                {
                    "symbol": symbol,
                    "exchange": exchange,
                    "name": str(row.get("name", "")),
                    "listing_date": listing_date,
                    "status": "listed",
                    "industry": str(row.get("industry", "")) or None,
                    "area": str(row.get("area", "")) or None,
                }
            )
        return rows

    def fetch_daily_quotes(
        self, symbol: str, start_date: date, end_date: date
    ) -> list[dict[str, Any]]:
        pro = self._get_pro()
        # Tushare 使用 XXXXXX.SH/SZ 格式
        ts_code = symbol

        try:
            df = pro.daily(
                ts_code=ts_code,
                start_date=start_date.strftime("%Y%m%d"),
                end_date=end_date.strftime("%Y%m%d"),
            )
        except Exception as exc:
            logger.warning("Tushare 获取 %s 日线失败: %s", symbol, exc)
            return []

        if df is None or df.empty:
            return []

        rows: list[dict[str, Any]] = []
        for _, row in df.iterrows():
            trade_date_str = str(row.get("trade_date", ""))
            try:
                trade_date = datetime.strptime(trade_date_str, "%Y%m%d").date()
            except (ValueError, TypeError):
                continue

            rows.append(
                {
                    "symbol": symbol,
                    "trade_date": trade_date,
                    "open": float(row.get("open", 0)),
                    "high": float(row.get("high", 0)),
                    "low": float(row.get("low", 0)),
                    "close": float(row.get("close", 0)),
                    "volume": float(row.get("vol", 0)) * 100,  # Tushare vol 单位是手
                    "amount": float(row.get("amount", 0)) * 1000,  # 单位千元→元
                }
            )
        # Tushare 默认降序，反转为升序
        rows.sort(key=lambda r: r["trade_date"])
        return rows

    def fetch_financials(self, symbol: str, periods: int = 4) -> list[dict[str, Any]]:
        pro = self._get_pro()
        ts_code = symbol

        try:
            df_income = pro.income(
                ts_code=ts_code,
                fields="end_date,revenue,n_income",
            )
        except Exception as exc:
            logger.warning("Tushare 获取 %s 利润表失败: %s", symbol, exc)
            df_income = None

        try:
            df_indicator = pro.fina_indicator(
                ts_code=ts_code,
                fields="end_date,roe,grossprofit_margin",
            )
        except Exception as exc:
            logger.warning("Tushare 获取 %s 财务指标失败: %s", symbol, exc)
            df_indicator = None

        rows: list[dict[str, Any]] = []

        if df_income is not None and not df_income.empty:
            for _, row in df_income.head(periods).iterrows():
                end_date_str = str(row.get("end_date", ""))
                try:
                    report_date = datetime.strptime(end_date_str, "%Y%m%d").date()
                except (ValueError, TypeError):
                    continue

                revenue = self._safe_float(row.get("revenue"))
                net_profit = self._safe_float(row.get("n_income"))

                roe = 0.0
                gross_margin = 0.0
                if df_indicator is not None and not df_indicator.empty:
                    matched = df_indicator[
                        df_indicator["end_date"] == end_date_str
                    ]
                    if not matched.empty:
                        roe = self._safe_float(matched.iloc[0].get("roe"))
                        gross_margin = self._safe_float(
                            matched.iloc[0].get("grossprofit_margin")
                        )

                rows.append(
                    {
                        "symbol": symbol,
                        "report_date": report_date,
                        "report_type": "quarterly",
                        "revenue": revenue,
                        "net_profit": net_profit,
                        "roe": roe,
                        "gross_margin": gross_margin,
                    }
                )
        return rows

    def fetch_news(self, symbol: str, count: int = 20) -> list[dict[str, Any]]:
        pro = self._get_pro()

        try:
            df = pro.news(
                src="sina",
                start_date=date.today().strftime("%Y-%m-%d"),
                end_date=date.today().strftime("%Y-%m-%d"),
            )
        except Exception as exc:
            logger.warning("Tushare 获取 %s 新闻失败: %s", symbol, exc)
            return []

        if df is None or df.empty:
            return []

        rows: list[dict[str, Any]] = []
        for _, row in df.head(count).iterrows():
            title = str(row.get("title", ""))
            content = str(row.get("content", ""))
            pub_str = str(row.get("datetime", ""))

            try:
                published_at = datetime.strptime(pub_str[:19], "%Y-%m-%d %H:%M:%S")
                published_at = published_at.replace(tzinfo=timezone.utc)
            except (ValueError, TypeError):
                published_at = datetime.now(timezone.utc)

            news_id = hashlib.sha256(
                f"tushare:{symbol}:{title}:{pub_str}".encode()
            ).hexdigest()[:16]

            rows.append(
                {
                    "news_id": f"tushare:{news_id}",
                    "symbol": symbol,
                    "published_at": published_at,
                    "title": title,
                    "content": content,
                    "url": "",
                }
            )
        return rows

    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        if value is None:
            return default
        try:
            return float(value)
        except (ValueError, TypeError):
            return default
