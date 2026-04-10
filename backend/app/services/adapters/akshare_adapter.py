"""AKShare datasource adapter."""
from __future__ import annotations

import hashlib
import logging
from contextlib import ExitStack
from datetime import date, datetime, timedelta, timezone
from typing import Any
from unittest.mock import patch

from .base import DataFetchError, DataSourceAdapter

logger = logging.getLogger(__name__)


def _import_akshare():
    """Import akshare lazily so startup does not require the dependency."""
    import akshare as ak  # type: ignore[import-untyped]

    return ak


class AKShareAdapter(DataSourceAdapter):
    name = "akshare"

    _INDEX_SYMBOL_MAP: dict[str, str] = {
        "000300.SH": "sh000300",
        "000001.SH": "sh000001",
        "399001.SZ": "sz399001",
        "399006.SZ": "sz399006",
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
            code = str(_pick(row, "代码", "code")).strip()
            if not code:
                continue

            symbol = self.normalize_symbol(code)
            exchange = "SH" if symbol.endswith(".SH") else "SZ"
            rows.append(
                {
                    "symbol": symbol,
                    "exchange": exchange,
                    "name": str(_pick(row, "名称", "name")).strip(),
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
        errors: list[str] = []

        try:
            df = ak.stock_zh_a_hist(
                symbol=code,
                period="daily",
                start_date=start_date.strftime("%Y%m%d"),
                end_date=end_date.strftime("%Y%m%d"),
                adjust="qfq",
            )
            rows = self._parse_daily_quotes_frame(df, symbol)
            if rows:
                return rows
        except Exception as exc:
            errors.append(f"eastmoney: {exc}")
            logger.warning("AKShare 获取 %s 日线失败，准备回退新浪源: %s", symbol, exc)

        try:
            df = ak.stock_zh_a_daily(
                symbol=self._to_market_symbol(symbol),
                start_date=start_date.strftime("%Y%m%d"),
                end_date=end_date.strftime("%Y%m%d"),
                adjust="qfq",
            )
            rows = self._parse_daily_quotes_frame(df, symbol)
            if rows:
                return rows
        except Exception as exc:
            errors.append(f"sina: {exc}")
            logger.warning("AKShare 回退新浪获取 %s 日线失败: %s", symbol, exc)

        detail = "；".join(errors) if errors else "empty result"
        raise DataFetchError(f"{symbol} 日线抓取失败: {detail}")

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
            report_date = _coerce_date(_pick(row, "报告期", "report_date"))
            if not report_date:
                continue

            revenue = self._safe_float(_pick(row, "营业总收入", "revenue"))
            net_profit = self._safe_float(_pick(row, "净利润", "net_profit"))

            roe = 0.0
            gross_margin = 0.0
            if df_indicator is not None and not df_indicator.empty:
                indicator_date_series = df_indicator.get("报告期", df_indicator.iloc[:, 0])
                matched = df_indicator[
                    indicator_date_series.astype(str).str[:10] == report_date.isoformat()
                ]
                if not matched.empty:
                    roe = self._safe_float(_pick(matched.iloc[0], "净资产收益率", "roe"))
                    gross_margin = self._safe_float(_pick(matched.iloc[0], "销售毛利率", "gross_margin"))

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
            title = str(_pick(row, "新闻标题", "title")).strip()
            content = str(_pick(row, "新闻内容", "content")).strip()
            url = str(_pick(row, "新闻链接", "url")).strip()
            published_at = _coerce_datetime(_pick(row, "发布时间", "published_at"))
            if published_at is None:
                published_at = datetime.now(timezone.utc)

            news_id = hashlib.sha256(
                f"akshare:{symbol}:{title}:{published_at.isoformat()}".encode()
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
        code = index_code.replace(".", "")[:6]
        market_symbol = self._INDEX_SYMBOL_MAP.get(index_code, self._to_market_symbol(index_code))
        errors: list[str] = []

        try:
            df = ak.index_zh_a_hist(
                symbol=code,
                period="daily",
                start_date=start_date.strftime("%Y%m%d"),
                end_date=end_date.strftime("%Y%m%d"),
            )
            rows = self._parse_index_rows(index_code, df, start_date, end_date)
            if rows:
                return rows
        except Exception as exc:
            errors.append(f"eastmoney: {exc}")
            logger.warning("AKShare 获取指数 %s 日线失败，准备回退其他源: %s", index_code, exc)

        try:
            df = ak.stock_zh_index_daily(symbol=market_symbol)
            rows = self._parse_index_rows(index_code, df, start_date, end_date)
            if rows:
                return rows
        except Exception as exc:
            errors.append(f"sina: {exc}")
            logger.warning("AKShare 回退新浪获取指数 %s 日线失败: %s", index_code, exc)

        try:
            with _mute_akshare_tqdm("akshare.index.index_stock_zh.get_tqdm"):
                df = ak.stock_zh_index_daily_tx(symbol=market_symbol)
            rows = self._parse_index_rows(index_code, df, start_date, end_date)
            if rows:
                return rows
        except Exception as exc:
            errors.append(f"tencent: {exc}")
            logger.warning("AKShare 回退腾讯获取指数 %s 日线失败: %s", index_code, exc)

        detail = "；".join(errors) if errors else "empty result"
        raise DataFetchError(f"{index_code} 指数日线抓取失败: {detail}")

    def fetch_announcements(self, symbol: str, count: int = 20) -> list[dict[str, Any]]:
        ak = _import_akshare()
        code = self.strip_suffix(symbol)
        begin_date = (date.today() - timedelta(days=365)).strftime("%Y%m%d")
        end_date = date.today().strftime("%Y%m%d")
        errors: list[str] = []

        try:
            with _mute_akshare_tqdm("akshare.stock_fundamental.stock_notice.get_tqdm"):
                df = ak.stock_individual_notice_report(
                    security=code,
                    begin_date=begin_date,
                    end_date=end_date,
                )
            rows = self._parse_announcements_frame(df, symbol, count)
            if rows:
                return rows
        except Exception as exc:
            errors.append(f"individual: {exc}")
            logger.warning("AKShare 获取 %s 个股公告失败，准备回退全市场接口: %s", symbol, exc)

        try:
            with _mute_akshare_tqdm("akshare.stock_fundamental.stock_notice.get_tqdm"):
                df = ak.stock_notice_report(date=date.today().strftime("%Y%m%d"))
            rows = self._parse_announcements_frame(df, symbol, count)
            if rows:
                return rows
        except Exception as exc:
            errors.append(f"market: {exc}")
            logger.warning("AKShare 回退全市场公告接口获取 %s 失败: %s", symbol, exc)

        detail = "；".join(errors) if errors else "empty result"
        raise DataFetchError(f"{symbol} 公告抓取失败: {detail}")

    def _parse_daily_quotes_frame(self, df: Any, symbol: str) -> list[dict[str, Any]]:
        if df is None or getattr(df, "empty", True):
            return []

        rows: list[dict[str, Any]] = []
        for _, row in df.iterrows():
            trade_date = _coerce_date(_pick(row, "日期", "date"))
            if not trade_date:
                continue

            rows.append(
                {
                    "symbol": symbol,
                    "trade_date": trade_date,
                    "open": self._safe_float(_pick(row, "开盘", "open")),
                    "high": self._safe_float(_pick(row, "最高", "high")),
                    "low": self._safe_float(_pick(row, "最低", "low")),
                    "close": self._safe_float(_pick(row, "收盘", "close")),
                    "volume": self._safe_float(_pick(row, "成交量", "volume")),
                    "amount": self._safe_float(_pick(row, "成交额", "amount")),
                }
            )
        return rows

    def _parse_index_rows(
        self,
        index_code: str,
        df: Any,
        start_date: date,
        end_date: date,
    ) -> list[dict[str, Any]]:
        if df is None or getattr(df, "empty", True):
            return []

        parsed: list[tuple[date, float]] = []
        for _, row in df.iterrows():
            trade_date = _coerce_date(_pick(row, "日期", "date"))
            close = self._safe_float(_pick(row, "收盘", "close"))
            if not trade_date or close <= 0:
                continue
            parsed.append((trade_date, close))

        parsed.sort(key=lambda item: item[0])
        rows: list[dict[str, Any]] = []
        previous_close: float | None = None
        for trade_date, close in parsed:
            if trade_date < start_date or trade_date > end_date:
                previous_close = close
                continue

            change_pct = 0.0
            if previous_close and previous_close > 0:
                change_pct = (close - previous_close) / previous_close * 100

            rows.append(
                {
                    "index_code": index_code,
                    "trade_date": trade_date,
                    "close": close,
                    "change_pct": round(change_pct, 4),
                }
            )
            previous_close = close
        return rows

    def _parse_announcements_frame(
        self,
        df: Any,
        symbol: str,
        count: int,
    ) -> list[dict[str, Any]]:
        if df is None or getattr(df, "empty", True):
            return []

        code = self.strip_suffix(symbol)
        rows: list[dict[str, Any]] = []
        seen_ids: set[str] = set()

        for _, row in df.iterrows():
            row_code = _normalize_notice_code(_pick(row, "代码", "stock_code", "code"))
            if row_code and row_code != code:
                continue

            title = str(_pick(row, "公告标题", "title")).strip()
            if not title:
                continue

            url = str(_pick(row, "网址", "公告链接", "url")).strip()
            published_at = _coerce_datetime(_pick(row, "公告日期", "date", "公告时间", "published_at"))
            if published_at is None:
                published_at = datetime.now(timezone.utc)

            identity = url or f"{code}:{title}:{published_at.isoformat()}"
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

        rows.sort(key=lambda item: item["published_at"], reverse=True)
        return rows[:count]

    @staticmethod
    def _to_market_symbol(symbol: str) -> str:
        normalized = DataSourceAdapter.normalize_symbol(symbol)
        market = normalized[-2:].lower()
        code = normalized[:6]
        return f"{market}{code}"

    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        if value is None:
            return default
        try:
            return float(str(value).replace(",", "").replace("--", "0"))
        except (ValueError, TypeError):
            return default


def _pick(row: Any, *keys: str) -> Any:
    for key in keys:
        try:
            value = row.get(key)
        except AttributeError:
            value = None
        if value is not None:
            return value
    return None


def _mute_akshare_tqdm(*targets: str):
    stack = ExitStack()
    quiet_tqdm = lambda: (lambda iterable, *args, **kwargs: iterable)
    for target in targets:
        stack.enter_context(patch(target, quiet_tqdm))
    return stack


def _normalize_notice_code(value: Any) -> str:
    text = str(value or "").strip()
    if text.endswith(".0"):
        text = text[:-2]
    return text.zfill(6) if text.isdigit() else text


def _coerce_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value

    text = str(value or "").strip()
    if not text:
        return None

    for fmt, width in (("%Y-%m-%d", 10), ("%Y/%m/%d", 10), ("%Y%m%d", 8)):
        try:
            return datetime.strptime(text[:width], fmt).date()
        except ValueError:
            continue
    return None


def _coerce_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time(), tzinfo=timezone.utc)

    text = str(value or "").strip()
    if not text:
        return None

    for fmt, width in (
        ("%Y-%m-%d %H:%M:%S", 19),
        ("%Y-%m-%d %H:%M", 16),
        ("%Y-%m-%d", 10),
        ("%Y/%m/%d", 10),
        ("%Y%m%d", 8),
    ):
        try:
            parsed = datetime.strptime(text[:width], fmt)
            return parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None
