"""AKShare datasource adapter."""
from __future__ import annotations

import hashlib
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any

from .base import DataFetchError, DataSourceAdapter

logger = logging.getLogger(__name__)


def _import_akshare():
    """Import akshare lazily so startup does not require the dependency."""
    import akshare as ak  # type: ignore[import-untyped]

    return ak


class AKShareAdapter(DataSourceAdapter):
    name = "akshare"

    _INDEX_CODE_MAP: dict[str, str] = {
        "000300.SH": "000300",
        "000001.SH": "000001",
        "399001.SZ": "399001",
        "399006.SZ": "399006",
    }

    def test_connection(self) -> tuple[bool, str]:
        try:
            ak = _import_akshare()
            df = ak.tool_trade_date_hist_sina()
            if df is not None and len(df) > 0:
                return True, f"AKShare 连接正常，获取到 {len(df)} 条交易日历数据。"
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
            raise DataFetchError(f"{symbol} 日线抓取失败: {exc}") from exc

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
            df_profit = ak.stock_financial_benefit_ths(symbol=code, indicator="按报告期")
        except Exception as exc:
            logger.warning("AKShare 获取 %s 利润表失败: %s", symbol, exc)
            df_profit = None

        try:
            df_indicator = ak.stock_financial_analysis_indicator(symbol=code, start_year="2020")
        except Exception as exc:
            logger.warning("AKShare 获取 %s 财务指标失败: %s", symbol, exc)
            df_indicator = None

        rows: list[dict[str, Any]] = []
        if df_profit is None or df_profit.empty:
            return rows

        for _, row in df_profit.head(periods).iterrows():
            report_date_raw = str(row.get("报告期", ""))
            try:
                report_date = datetime.strptime(report_date_raw[:10], "%Y-%m-%d").date()
            except (ValueError, TypeError):
                continue

            revenue = self._safe_float(row.get("营业总收入"))
            net_profit = self._safe_float(row.get("净利润"))

            roe = 0.0
            gross_margin = 0.0
            if df_indicator is not None and not df_indicator.empty:
                indicator_date_series = df_indicator.get("报告期", df_indicator.iloc[:, 0])
                matched = df_indicator[indicator_date_series.astype(str).str[:10] == report_date_raw[:10]]
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

    def fetch_index_daily(
        self, index_code: str, start_date: date, end_date: date
    ) -> list[dict[str, Any]]:
        ak = _import_akshare()
        ak_code = self._INDEX_CODE_MAP.get(index_code, self.strip_suffix(index_code))

        try:
            df = ak.index_zh_a_hist(
                symbol=ak_code,
                period="daily",
                start_date=start_date.strftime("%Y%m%d"),
                end_date=end_date.strftime("%Y%m%d"),
            )
        except Exception as exc:
            logger.warning("AKShare 获取指数 %s 日线失败: %s", index_code, exc)
            raise DataFetchError(f"{index_code} 指数日线抓取失败: {exc}") from exc

        if df is None or df.empty:
            return []

        rows: list[dict[str, Any]] = []
        for _, row in df.iterrows():
            trade_date_str = str(row.get("日期", ""))
            try:
                trade_date = datetime.strptime(trade_date_str[:10], "%Y-%m-%d").date()
            except (ValueError, TypeError):
                continue

            rows.append(
                {
                    "index_code": index_code,
                    "trade_date": trade_date,
                    "close": self._safe_float(row.get("收盘")),
                    "change_pct": self._safe_float(row.get("涨跌幅")),
                }
            )
        return rows

    def fetch_announcements(self, symbol: str, count: int = 20) -> list[dict[str, Any]]:
        ak = _import_akshare()
        code = self.strip_suffix(symbol)
        rows: list[dict[str, Any]] = []
        seen_ids: set[str] = set()

        for day_offset in range(7):
            query_date = (date.today() - timedelta(days=day_offset)).strftime("%Y%m%d")
            try:
                df = ak.stock_notice_report(symbol="全部", date=query_date)
            except Exception as exc:
                logger.warning("AKShare 获取 %s 公告失败: %s", symbol, exc)
                raise DataFetchError(f"{symbol} 公告抓取失败: {exc}") from exc

            if df is None or df.empty:
                continue

            for _, row in df.iterrows():
                row_code = _normalize_notice_code(row.get("代码", row.get("stock_code", "")))
                if row_code != code:
                    continue

                title = str(row.get("公告标题", row.get("title", ""))).strip()
                url = str(row.get("网址", row.get("公告链接", row.get("url", "")))).strip()
                published_at = _coerce_datetime(
                    row.get("公告日期", row.get("date", row.get("公告时间", "")))
                ) or datetime.now(timezone.utc)
                identity = url or f"{row_code}:{title}:{published_at.isoformat()}"
                ann_id = hashlib.sha256(identity.encode()).hexdigest()[:16]
                if ann_id in seen_ids:
                    continue

                seen_ids.add(ann_id)
                rows.append(
                    {
                        "announcement_id": f"akshare:{ann_id}",
                        "symbol": symbol,
                        "published_at": published_at,
                        "title": title,
                        "content": title,
                        "url": url,
                    }
                )
                if len(rows) >= count:
                    return rows

        return rows

    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        if value is None:
            return default
        try:
            return float(str(value).replace(",", "").replace("--", "0"))
        except (ValueError, TypeError):
            return default


def _normalize_notice_code(value: Any) -> str:
    text = str(value or "").strip()
    if text.endswith(".0"):
        text = text[:-2]
    return text.zfill(6) if text.isdigit() else text


def _coerce_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time(), tzinfo=timezone.utc)

    text = str(value or "").strip()
    if not text:
        return None

    for fmt, width in (("%Y-%m-%d %H:%M:%S", 19), ("%Y-%m-%d", 10)):
        try:
            parsed = datetime.strptime(text[:width], fmt)
            return parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None
