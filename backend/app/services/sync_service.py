from __future__ import annotations

import hashlib
import importlib.util
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any

from app.core.config import load_settings
from app.core.market_store import (
    init_market_store,
    list_seed_symbols,
    upsert_company_profiles,
    upsert_daily_quotes,
    upsert_financial_reports,
    upsert_news_items,
    upsert_symbol_master,
)

logger = logging.getLogger(__name__)


DEFAULT_SYMBOL_FIXTURES = [
    {"symbol": "000001.SZ", "name": "平安银行", "exchange": "SZ", "industry": "银行", "area": "深圳", "listing_date": "1991-04-03"},
    {"symbol": "600519.SH", "name": "贵州茅台", "exchange": "SH", "industry": "白酒", "area": "贵州", "listing_date": "2001-08-27"},
    {"symbol": "300750.SZ", "name": "宁德时代", "exchange": "SZ", "industry": "电池", "area": "福建", "listing_date": "2018-06-11"},
    {"symbol": "601318.SH", "name": "中国平安", "exchange": "SH", "industry": "保险", "area": "上海", "listing_date": "2007-03-01"},
    {"symbol": "002415.SZ", "name": "海康威视", "exchange": "SZ", "industry": "安防", "area": "杭州", "listing_date": "2010-05-28"},
]

SOURCE_MODULES = {
    "akshare": "akshare",
    "tushare": "tushare",
    "baostock": "baostock",
}

SOURCE_TOKEN_FIELDS = {
    "akshare": None,
    "tushare": "token",
    "baostock": None,
}

# 标记哪些数据源已实现真实适配器
LIVE_SYNC_IMPLEMENTED: set[str] = {"akshare", "tushare", "baostock"}


@dataclass
class SourceRuntimeStatus:
    configured: bool
    status: str
    note: str
    live_mode: bool


@dataclass
class SyncExecutionResult:
    status: str
    summary: str
    warnings: list[str] = field(default_factory=list)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _stable_int(seed: str, minimum: int, maximum: int) -> int:
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    value = int(digest[:10], 16)
    return minimum + (value % (maximum - minimum + 1))


def _stable_float(seed: str, minimum: float, maximum: float, digits: int = 2) -> float:
    scale = 10**digits
    raw = _stable_int(seed, int(minimum * scale), int(maximum * scale))
    return round(raw / scale, digits)


def normalize_symbol(symbol: str) -> str:
    normalized = symbol.strip().upper()
    if not normalized:
        raise ValueError("股票代码不能为空。")
    if normalized.endswith((".SH", ".SZ")):
        return normalized
    suffix = ".SH" if normalized.startswith(("5", "6", "9")) else ".SZ"
    return f"{normalized}{suffix}"


def describe_source_status(source_name: str, config: dict[str, Any]) -> SourceRuntimeStatus:
    enabled = bool(config.get("enabled"))
    token_field = SOURCE_TOKEN_FIELDS[source_name]
    secret_ready = True if token_field is None else bool(config.get(token_field))
    dependency_ready = importlib.util.find_spec(SOURCE_MODULES[source_name]) is not None
    runtime_ready = enabled and secret_ready and dependency_ready
    live_mode = runtime_ready and source_name in LIVE_SYNC_IMPLEMENTED

    if not enabled:
        return SourceRuntimeStatus(
            configured=False,
            status="disabled",
            note="当前数据源已禁用，不会作为实时同步主源。",
            live_mode=False,
        )

    if live_mode:
        return SourceRuntimeStatus(
            configured=True,
            status="online",
            note="依赖和配置已就绪，可执行真实同步。",
            live_mode=True,
        )

    if runtime_ready:
        return SourceRuntimeStatus(
            configured=True,
            status="adapter_pending",
            note="运行环境已就绪，但真实抓取适配尚未接入；当前同步仍回退到内置示例数据。",
            live_mode=False,
        )

    if not dependency_ready:
        return SourceRuntimeStatus(
            configured=False,
            status="dependency_missing",
            note="未安装对应 SDK；当前同步会回退到内置示例数据。",
            live_mode=False,
        )

    return SourceRuntimeStatus(
        configured=False,
        status="missing_token",
        note="缺少访问凭证；当前同步会回退到内置示例数据。",
        live_mode=False,
    )


def _resolve_symbols(job: dict[str, Any], limit: int = 3) -> list[str]:
    params = job.get("params", {})
    raw_symbols = params.get("symbols")
    if isinstance(raw_symbols, list) and raw_symbols:
        return [normalize_symbol(item) for item in raw_symbols]

    raw_symbol = params.get("symbol")
    if isinstance(raw_symbol, str) and raw_symbol.strip():
        return [normalize_symbol(raw_symbol)]

    scope = str(job.get("scope", "all")).strip()
    if scope and scope.lower() != "all":
        return [normalize_symbol(item) for item in scope.split(",") if item.strip()]

    stored_symbols = list_seed_symbols(limit=limit)
    if stored_symbols:
        return stored_symbols

    return [item["symbol"] for item in DEFAULT_SYMBOL_FIXTURES[:limit]]


def _business_days(count: int) -> list[date]:
    cursor = _utc_now().date()
    days: list[date] = []
    while len(days) < count:
        if cursor.weekday() < 5:
            days.append(cursor)
        cursor -= timedelta(days=1)
    return list(reversed(days))


def _quarter_end_dates(count: int) -> list[date]:
    today = _utc_now().date()
    quarter_month = ((today.month - 1) // 3 + 1) * 3
    cursor = date(today.year, quarter_month, 1)
    dates: list[date] = []
    while len(dates) < count:
        next_month = date(cursor.year + (1 if cursor.month == 12 else 0), 1 if cursor.month == 12 else cursor.month + 1, 1)
        dates.append(next_month - timedelta(days=1))
        prev_month = cursor.month - 3
        prev_year = cursor.year
        while prev_month <= 0:
            prev_month += 12
            prev_year -= 1
        cursor = date(prev_year, prev_month, 1)
    return dates


def _build_symbol_rows(source: str) -> list[dict[str, Any]]:
    updated_at = _utc_now()
    return [
        {
            "symbol": item["symbol"],
            "exchange": item["exchange"],
            "name": item["name"],
            "industry": item["industry"],
            "area": item["area"],
            "listing_date": item["listing_date"],
            "status": "listed",
            "source": source,
            "updated_at": updated_at,
        }
        for item in DEFAULT_SYMBOL_FIXTURES
    ]


def _build_quote_rows(symbol: str, source: str, count: int = 60) -> list[dict[str, Any]]:
    base_price = _stable_float(f"{symbol}:{source}:base", 12, 380)
    rows: list[dict[str, Any]] = []
    updated_at = _utc_now()

    for index, trade_date in enumerate(_business_days(count)):
        drift = _stable_float(f"{symbol}:{source}:drift:{index}", -4.5, 4.5)
        open_price = round(base_price + drift, 2)
        close_price = round(open_price + _stable_float(f"{symbol}:{source}:close:{index}", -2.2, 2.2), 2)
        high_price = round(max(open_price, close_price) + _stable_float(f"{symbol}:{source}:high:{index}", 0.2, 2.8), 2)
        low_price = round(min(open_price, close_price) - _stable_float(f"{symbol}:{source}:low:{index}", 0.2, 2.4), 2)
        volume = float(_stable_int(f"{symbol}:{source}:volume:{index}", 1_500_000, 25_000_000))

        rows.append(
            {
                "symbol": symbol,
                "trade_date": trade_date,
                "open": max(open_price, 0.01),
                "high": max(high_price, 0.01),
                "low": max(low_price, 0.01),
                "close": max(close_price, 0.01),
                "volume": volume,
                "amount": round(volume * max(close_price, 0.01), 2),
                "source": source,
                "updated_at": updated_at,
            }
        )

    return rows


def _build_financial_rows(symbol: str, source: str, count: int = 6) -> list[dict[str, Any]]:
    updated_at = _utc_now()
    rows: list[dict[str, Any]] = []

    for index, report_date in enumerate(_quarter_end_dates(count)):
        rows.append(
            {
                "symbol": symbol,
                "report_date": report_date,
                "report_type": "quarterly",
                "revenue": _stable_float(f"{symbol}:{source}:revenue:{index}", 18, 420) * 100000000.0,
                "net_profit": _stable_float(f"{symbol}:{source}:profit:{index}", 2, 88) * 100000000.0,
                "roe": _stable_float(f"{symbol}:{source}:roe:{index}", 4.5, 28.0),
                "gross_margin": _stable_float(f"{symbol}:{source}:margin:{index}", 12.0, 67.0),
                "source": source,
                "updated_at": updated_at,
            }
        )

    return rows


def _build_news_rows(symbol: str, source: str, count: int = 8) -> list[dict[str, Any]]:
    updated_at = _utc_now()
    rows: list[dict[str, Any]] = []

    for index in range(count):
        published_at = updated_at - timedelta(hours=index * 6)
        rows.append(
            {
                "news_id": f"{source}:{symbol}:{published_at:%Y%m%d%H%M}:{index}",
                "symbol": symbol,
                "published_at": published_at,
                "title": f"{symbol} 经营进展跟踪 #{index + 1}",
                "content": f"{symbol} 最近披露的经营进展、行业动态与市场反馈已纳入本地新闻样本，用于后续分析链路验证。",
                "url": f"https://example.local/{source}/{symbol}/{index + 1}",
                "source": source,
                "updated_at": updated_at,
            }
        )

    return rows


def _create_adapter(source_name: str, source_config: dict[str, Any]):
    """根据数据源名称创建对应的适配器实例。"""
    from app.services.adapters.base import DataSourceAdapter

    if source_name == "akshare":
        from app.services.adapters.akshare_adapter import AKShareAdapter
        return AKShareAdapter()
    elif source_name == "tushare":
        from app.services.adapters.tushare_adapter import TushareAdapter
        return TushareAdapter(token=source_config.get("token", ""))
    elif source_name == "baostock":
        from app.services.adapters.baostock_adapter import BaoStockAdapter
        return BaoStockAdapter()
    return None


def _live_symbol_sync(adapter, source_name: str) -> tuple[int, int]:
    """使用真实适配器同步股票列表。"""
    updated_at = _utc_now()
    raw_rows = adapter.fetch_symbol_list()
    if not raw_rows:
        return 0, 0

    symbol_rows = [
        {
            "symbol": row["symbol"],
            "exchange": row["exchange"],
            "name": row["name"],
            "listing_date": row.get("listing_date"),
            "status": row.get("status", "listed"),
            "source": source_name,
            "updated_at": updated_at,
        }
        for row in raw_rows
    ]
    profile_rows = [
        {
            "symbol": row["symbol"],
            "name": row["name"],
            "industry": row.get("industry"),
            "area": row.get("area"),
            "listing_date": row.get("listing_date"),
            "source": source_name,
            "updated_at": updated_at,
        }
        for row in raw_rows
    ]
    symbol_count = upsert_symbol_master(symbol_rows)
    profile_count = upsert_company_profiles(profile_rows)
    return symbol_count, profile_count


def _live_history_sync(adapter, symbols: list[str], source_name: str, days: int = 60) -> int:
    """使用真实适配器同步历史行情。"""
    updated_at = _utc_now()
    end_date = _utc_now().date()
    start_date = end_date - timedelta(days=int(days * 1.5))  # 多拉一些日历日覆盖交易日

    all_rows: list[dict[str, Any]] = []
    for symbol in symbols:
        try:
            rows = adapter.fetch_daily_quotes(symbol, start_date, end_date)
            for row in rows:
                row["source"] = source_name
                row["updated_at"] = updated_at
            all_rows.extend(rows)
        except Exception as exc:
            logger.warning("同步 %s 历史行情失败: %s", symbol, exc)
    return upsert_daily_quotes(all_rows)


def _live_financial_sync(adapter, symbols: list[str], source_name: str, periods: int = 6) -> int:
    """使用真实适配器同步财务数据。"""
    updated_at = _utc_now()
    all_rows: list[dict[str, Any]] = []
    for symbol in symbols:
        try:
            rows = adapter.fetch_financials(symbol, periods)
            for row in rows:
                row["source"] = source_name
                row["updated_at"] = updated_at
            all_rows.extend(rows)
        except Exception as exc:
            logger.warning("同步 %s 财务数据失败: %s", symbol, exc)
    return upsert_financial_reports(all_rows)


def _live_news_sync(adapter, symbols: list[str], source_name: str, count: int = 20) -> int:
    """使用真实适配器同步新闻。"""
    updated_at = _utc_now()
    all_rows: list[dict[str, Any]] = []
    for symbol in symbols:
        try:
            rows = adapter.fetch_news(symbol, count)
            for row in rows:
                row["source"] = source_name
                row["updated_at"] = updated_at
            all_rows.extend(rows)
        except Exception as exc:
            logger.warning("同步 %s 新闻失败: %s", symbol, exc)
    return upsert_news_items(all_rows)


def execute_sync_job(job: dict[str, Any]) -> SyncExecutionResult:
    settings = load_settings()
    source_name = job["source"]
    source_config = settings["data_sources"].get(source_name)
    if not source_config:
        raise ValueError(f"未知数据源：{source_name}")

    runtime_status = describe_source_status(source_name, source_config)
    warnings: list[str] = []
    use_live = runtime_status.live_mode

    if not use_live:
        warnings.append(runtime_status.note)

    # --- 健康检查 ---
    if job["job_type"] == "health_check":
        if use_live:
            adapter = _create_adapter(source_name, source_config)
            if adapter:
                ok, msg = adapter.test_connection()
                summary = f"{source_name} 连接测试{'成功' if ok else '失败'}：{msg}"
                return SyncExecutionResult(
                    status="completed" if ok else "completed_with_warnings",
                    summary=summary,
                    warnings=[] if ok else [msg],
                )
        summary = f"{source_name} 状态：{runtime_status.status}。{runtime_status.note}"
        return SyncExecutionResult(
            status="completed_with_warnings" if warnings else "completed",
            summary=summary,
            warnings=warnings,
        )

    if not init_market_store():
        raise RuntimeError("DuckDB 依赖不可用，无法初始化本地数据仓。")

    adapter = _create_adapter(source_name, source_config) if use_live else None

    # --- 股票基本信息同步 ---
    if job["job_type"] == "symbol_sync":
        if adapter and use_live:
            try:
                symbol_count, profile_count = _live_symbol_sync(adapter, source_name)
                summary = f"{source_name} 已从真实接口写入 {symbol_count} 条股票基础信息，更新 {profile_count} 条公司档案。"
                return SyncExecutionResult(status="completed", summary=summary, warnings=[])
            except Exception as exc:
                logger.warning("真实同步失败，回退到 fixture: %s", exc)
                warnings.append(f"真实同步失败（{exc}），已回退到内置示例数据。")

        symbol_rows = _build_symbol_rows(source_name)
        symbol_count = upsert_symbol_master(symbol_rows)
        profile_count = upsert_company_profiles(symbol_rows)
        summary = f"{source_name} 已写入 {symbol_count} 条股票基础信息，更新 {profile_count} 条公司档案。"

    # --- 历史行情同步 ---
    elif job["job_type"] == "history_sync":
        symbols = _resolve_symbols(job)
        if adapter and use_live:
            try:
                quote_count = _live_history_sync(adapter, symbols, source_name)
                summary = f"{source_name} 已从真实接口同步 {len(symbols)} 只股票的历史行情，共写入 {quote_count} 条日线记录。"
                return SyncExecutionResult(status="completed", summary=summary, warnings=[])
            except Exception as exc:
                logger.warning("真实同步失败，回退到 fixture: %s", exc)
                warnings.append(f"真实同步失败（{exc}），已回退到内置示例数据。")

        quote_rows = [row for symbol in symbols for row in _build_quote_rows(symbol, source_name)]
        quote_count = upsert_daily_quotes(quote_rows)
        summary = f"{source_name} 已同步 {len(symbols)} 只股票的历史行情，共写入 {quote_count} 条日线记录。"

    # --- 财务数据同步 ---
    elif job["job_type"] == "financial_sync":
        symbols = _resolve_symbols(job)
        if adapter and use_live:
            try:
                report_count = _live_financial_sync(adapter, symbols, source_name)
                summary = f"{source_name} 已从真实接口同步 {len(symbols)} 只股票的财务摘要，共写入 {report_count} 条财报记录。"
                return SyncExecutionResult(status="completed", summary=summary, warnings=[])
            except Exception as exc:
                logger.warning("真实同步失败，回退到 fixture: %s", exc)
                warnings.append(f"真实同步失败（{exc}），已回退到内置示例数据。")

        financial_rows = [row for symbol in symbols for row in _build_financial_rows(symbol, source_name)]
        report_count = upsert_financial_reports(financial_rows)
        summary = f"{source_name} 已同步 {len(symbols)} 只股票的财务摘要，共写入 {report_count} 条财报记录。"

    # --- 新闻数据同步 ---
    elif job["job_type"] == "news_sync":
        symbols = _resolve_symbols(job)
        if adapter and use_live:
            try:
                news_count = _live_news_sync(adapter, symbols, source_name)
                summary = f"{source_name} 已从真实接口同步 {len(symbols)} 只股票的新闻，共写入 {news_count} 条新闻记录。"
                return SyncExecutionResult(status="completed", summary=summary, warnings=[])
            except Exception as exc:
                logger.warning("真实同步失败，回退到 fixture: %s", exc)
                warnings.append(f"真实同步失败（{exc}），已回退到内置示例数据。")

        news_rows = [row for symbol in symbols for row in _build_news_rows(symbol, source_name)]
        news_count = upsert_news_items(news_rows)
        summary = f"{source_name} 已同步 {len(symbols)} 只股票的新闻样本，共写入 {news_count} 条新闻记录。"
    else:
        raise ValueError(f"不支持的同步任务类型：{job['job_type']}")

    if warnings:
        summary = f"{summary} 当前使用内置示例数据完成落库。"

    return SyncExecutionResult(
        status="completed_with_warnings" if warnings else "completed",
        summary=summary,
        warnings=warnings,
    )
