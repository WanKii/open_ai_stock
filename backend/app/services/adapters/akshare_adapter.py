"""AKShare 数据源适配器。

AKShare 是开源免费的 A 股数据接口，不需要 Token。
文档: https://akshare.akfamily.xyz/
"""
from __future__ import annotations

import hashlib
import logging
from datetime import date, datetime, timezone
from typing import Any

from .base import DataSourceAdapter

logger = logging.getLogger(__name__)


def _import_akshare():
    """惰性导入 akshare，避免未安装时启动报错。"""
    import akshare as ak  # type: ignore[import-untyped]
    return ak


class AKShareAdapter(DataSourceAdapter):
    name = "akshare"

    def test_connection(self) -> tuple[bool, str]:
        try:
            ak = _import_akshare()
            # 用一次轻量调用验证连接
            df = ak.stock_zh_a_spot_em()
            if df is not None and len(df) > 0:
                return True, f"AKShare 连接正常，获取到 {len(df)} 只个股实时行情。"
            return False, "AKShare 返回空数据。"
        except ImportError:
            return False, "未安装 akshare 包，请执行 pip install akshare。"
        except Exception as exc:
            return False, f"AKShare 连接失败：{exc}"

    def fetch_symbol_list(self) -> list[dict[str, Any]]:
        ak = _import_akshare()
        df = ak.stock_zh_a_spot_em()
        if df is None or df.empty:
            return []

        rows: list[dict[str, Any]] = []
        for _, row in df.iterrows():
            code = str(row.get("代码", "")).strip()
            if not code:
                continue
            symbol = self.normalize_symbol(code)
            exchange = "SH" if symbol.endswith(".SH") else "SZ"
            rows.append(
                {
                    "symbol": symbol,
                    "exchange": exchange,
                    "name": str(row.get("名称", "")),
                    "listing_date": None,
                    "status": "listed",
                    "industry": None,
                    "area": None,
                }
            )
        return rows

    def fetch_daily_quotes(
        self, symbol: str, start_date: date, end_date: date
    ) -> list[dict[str, Any]]:
        ak = _import_akshare()
        code = self.strip_suffix(symbol)

        try:
            df = ak.stock_zh_a_hist(
                symbol=code,
                period="daily",
                start_date=start_date.strftime("%Y%m%d"),
                end_date=end_date.strftime("%Y%m%d"),
                adjust="qfq",
            )
        except Exception as exc:
            logger.warning("AKShare 获取 %s 日线失败: %s", symbol, exc)
            return []

        if df is None or df.empty:
            return []

        rows: list[dict[str, Any]] = []
        for _, row in df.iterrows():
            try:
                trade_date_str = str(row.get("日期", ""))
                trade_date = (
                    datetime.strptime(trade_date_str[:10], "%Y-%m-%d").date()
                    if trade_date_str
                    else None
                )
                if not trade_date:
                    continue

                rows.append(
                    {
                        "symbol": symbol,
                        "trade_date": trade_date,
                        "open": float(row.get("开盘", 0)),
                        "high": float(row.get("最高", 0)),
                        "low": float(row.get("最低", 0)),
                        "close": float(row.get("收盘", 0)),
                        "volume": float(row.get("成交量", 0)),
                        "amount": float(row.get("成交额", 0)),
                    }
                )
            except (ValueError, TypeError) as exc:
                logger.debug("AKShare 行解析跳过: %s", exc)
                continue
        return rows

    def fetch_financials(self, symbol: str, periods: int = 4) -> list[dict[str, Any]]:
        ak = _import_akshare()
        code = self.strip_suffix(symbol)

        try:
            # 利润表
            df_profit = ak.stock_financial_benefit_ths(symbol=code, indicator="按报告期")
        except Exception as exc:
            logger.warning("AKShare 获取 %s 利润表失败: %s", symbol, exc)
            df_profit = None

        try:
            # 资产负债表 — 获取 ROE 等
            df_balance = ak.stock_financial_analysis_indicator(symbol=code, start_year="2020")
        except Exception as exc:
            logger.warning("AKShare 获取 %s 财务指标失败: %s", symbol, exc)
            df_balance = None

        rows: list[dict[str, Any]] = []

        if df_profit is not None and not df_profit.empty:
            for _, row in df_profit.head(periods).iterrows():
                report_date_raw = str(row.get("报告期", ""))
                try:
                    report_date = datetime.strptime(report_date_raw[:10], "%Y-%m-%d").date()
                except (ValueError, TypeError):
                    continue

                revenue = self._safe_float(row.get("营业总收入"))
                net_profit = self._safe_float(row.get("净利润"))

                # 尝试从指标表匹配 ROE 和毛利率
                roe = 0.0
                gross_margin = 0.0
                if df_balance is not None and not df_balance.empty:
                    matched = df_balance[
                        df_balance.get("报告期", df_balance.iloc[:, 0]).astype(str).str[:10]
                        == report_date_raw[:10]
                    ]
                    if not matched.empty:
                        roe = self._safe_float(matched.iloc[0].get("净资产收益率"))
                        gross_margin = self._safe_float(matched.iloc[0].get("销售毛利率"))

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
        ak = _import_akshare()
        code = self.strip_suffix(symbol)

        try:
            df = ak.stock_news_em(symbol=code)
        except Exception as exc:
            logger.warning("AKShare 获取 %s 新闻失败: %s", symbol, exc)
            return []

        if df is None or df.empty:
            return []

        rows: list[dict[str, Any]] = []
        for _, row in df.head(count).iterrows():
            title = str(row.get("新闻标题", ""))
            content = str(row.get("新闻内容", ""))
            url = str(row.get("新闻链接", ""))
            pub_str = str(row.get("发布时间", ""))

            try:
                published_at = datetime.strptime(pub_str[:19], "%Y-%m-%d %H:%M:%S")
                published_at = published_at.replace(tzinfo=timezone.utc)
            except (ValueError, TypeError):
                published_at = datetime.now(timezone.utc)

            news_id = hashlib.sha256(
                f"akshare:{symbol}:{title}:{pub_str}".encode()
            ).hexdigest()[:16]

            rows.append(
                {
                    "news_id": f"akshare:{news_id}",
                    "symbol": symbol,
                    "published_at": published_at,
                    "title": title,
                    "content": content,
                    "url": url,
                }
            )
        return rows

    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        if value is None:
            return default
        try:
            v = float(str(value).replace(",", "").replace("--", "0"))
            return v
        except (ValueError, TypeError):
            return default
