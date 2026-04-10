from __future__ import annotations

import importlib.util
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Protocol

from app.core.config import load_settings
from app.core.market_store import (
    init_market_store,
    list_seed_symbols,
    upsert_announcements,
    upsert_company_profiles,
    upsert_daily_quotes,
    upsert_financial_reports,
    upsert_index_daily,
    upsert_news_items,
    upsert_symbol_master,
)

logger = logging.getLogger(__name__)

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

LIVE_SYNC_IMPLEMENTED: set[str] = {"akshare", "tushare", "baostock"}
MARKET_WIDE_NEWS_SYMBOL = "__MARKET__"
DEFAULT_SYMBOL_CANDIDATES = ["000001.SZ", "600519.SH", "300750.SZ"]
DEFAULT_INDEX_CODES = ["000300.SH", "000001.SH"]

# Sync mode presets: (history_days, financial_periods, news_count)
SYNC_MODE_PRESETS: dict[str, dict[str, int]] = {
    "incremental": {"history_days": 30, "financial_periods": 4, "news_count": 20},
    "standard": {"history_days": 365, "financial_periods": 12, "news_count": 50},
    "full": {"history_days": 3650, "financial_periods": 20, "news_count": 100},
}

DEFAULT_MAX_WORKERS = 3
DEFAULT_MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = [2, 4, 8]

# ---------------------------------------------------------------------------
# Cancel / pause registry — keyed by job_id
# ---------------------------------------------------------------------------
_cancel_events: dict[str, threading.Event] = {}
_pause_events: dict[str, threading.Event] = {}  # cleared = paused, set = running


def register_job_signals(job_id: str) -> tuple[threading.Event, threading.Event]:
    """Register cancel and pause events for a job. Returns (cancel_event, pause_event)."""
    cancel_ev = threading.Event()
    pause_ev = threading.Event()
    pause_ev.set()  # not paused by default
    _cancel_events[job_id] = cancel_ev
    _pause_events[job_id] = pause_ev
    return cancel_ev, pause_ev


def unregister_job_signals(job_id: str) -> None:
    _cancel_events.pop(job_id, None)
    _pause_events.pop(job_id, None)


def request_cancel(job_id: str) -> bool:
    ev = _cancel_events.get(job_id)
    if ev is None:
        return False
    ev.set()
    # Also unpause so the thread can exit
    pause_ev = _pause_events.get(job_id)
    if pause_ev:
        pause_ev.set()
    return True


def request_pause(job_id: str) -> bool:
    ev = _pause_events.get(job_id)
    if ev is None:
        return False
    ev.clear()  # clear = paused
    return True


def request_resume(job_id: str) -> bool:
    ev = _pause_events.get(job_id)
    if ev is None:
        return False
    ev.set()  # set = running
    return True


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


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


class ProgressCallback(Protocol):
    def __call__(
        self,
        *,
        total_items: int | None = None,
        completed_items: int | None = None,
        error_items: int | None = None,
        skipped_items: int | None = None,
        current_item: str | None = None,
    ) -> None: ...


def _noop_progress(**_: Any) -> None:
    pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


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
        return SourceRuntimeStatus(False, "disabled", "当前数据源已禁用，不会执行实时同步。", False)
    if live_mode:
        return SourceRuntimeStatus(True, "online", "依赖和配置已就绪，可执行实时同步。", True)
    if runtime_ready:
        return SourceRuntimeStatus(True, "adapter_pending", "运行环境已就绪，但当前数据源尚未接入实时同步实现。", False)
    if not dependency_ready:
        return SourceRuntimeStatus(False, "dependency_missing", "缺少对应 SDK，当前无法执行实时同步。", False)
    return SourceRuntimeStatus(False, "missing_token", "缺少访问凭证，当前无法执行实时同步。", False)


def _resolve_symbols(job: dict[str, Any], *, allow_all: bool = False) -> list[str]:
    """Resolve the list of symbols to sync from job params/scope.

    When *allow_all* is True (full-sync mode) and scope == 'all',
    we return ALL symbols from the symbol_master table instead of a small sample.
    """
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

    # scope == 'all'
    if allow_all:
        stored = list_seed_symbols(limit=100000)  # effectively all
        if stored:
            return stored
    else:
        stored = list_seed_symbols(limit=3)
        if stored:
            return stored

    return DEFAULT_SYMBOL_CANDIDATES[:]


def _create_adapter(source_name: str, source_config: dict[str, Any]):
    if source_name == "akshare":
        from app.services.adapters.akshare_adapter import AKShareAdapter

        return AKShareAdapter()
    if source_name == "tushare":
        from app.services.adapters.tushare_adapter import TushareAdapter

        return TushareAdapter(token=source_config.get("token", ""))
    if source_name == "baostock":
        from app.services.adapters.baostock_adapter import BaoStockAdapter

        return BaoStockAdapter()
    return None


def _dedupe_messages(messages: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for message in messages:
        text = str(message).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _format_details(messages: list[str], fallback: str) -> str:
    unique = _dedupe_messages(messages)
    return "；".join(unique[:3]) if unique else fallback


def _fail_sync(summary: str, warnings: list[str] | None = None) -> SyncExecutionResult:
    return SyncExecutionResult(status="failed", summary=summary, warnings=_dedupe_messages(warnings or []))


def _cancel_sync(summary: str, warnings: list[str] | None = None) -> SyncExecutionResult:
    return SyncExecutionResult(status="cancelled", summary=summary, warnings=_dedupe_messages(warnings or []))


def _complete_sync(summary: str, warnings: list[str] | None = None) -> SyncExecutionResult:
    normalized = _dedupe_messages(warnings or [])
    return SyncExecutionResult(
        status="completed_with_warnings" if normalized else "completed",
        summary=summary,
        warnings=normalized,
    )


# ---------------------------------------------------------------------------
# Retry wrapper
# ---------------------------------------------------------------------------


def _retry_fetch(
    fn: Callable[..., Any],
    args: tuple = (),
    kwargs: dict[str, Any] | None = None,
    max_retries: int = DEFAULT_MAX_RETRIES,
    label: str = "",
) -> Any:
    """Call *fn* with automatic retry on failure (exponential backoff)."""
    kwargs = kwargs or {}
    last_exc: Exception | None = None
    for attempt in range(max_retries):
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            last_exc = exc
            if attempt < max_retries - 1:
                wait = RETRY_BACKOFF_SECONDS[min(attempt, len(RETRY_BACKOFF_SECONDS) - 1)]
                logger.warning(
                    "[%s] 第 %d/%d 次重试失败: %s — %ds 后重试",
                    label, attempt + 1, max_retries, exc, wait,
                )
                time.sleep(wait)
    raise last_exc  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Dirty data filters
# ---------------------------------------------------------------------------


def _is_valid_number(value: Any) -> bool:
    """Check that value is a finite number and not None / NaN."""
    if value is None:
        return False
    try:
        f = float(value)
        return f == f  # NaN check
    except (TypeError, ValueError):
        return False


def _filter_daily_quotes(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    """Filter out dirty quote rows. Returns (clean_rows, filtered_count)."""
    clean: list[dict[str, Any]] = []
    for row in rows:
        trade_date = row.get("trade_date")
        if not trade_date:
            continue
        # All OHLCV must be valid positive numbers
        if not all(_is_valid_number(row.get(f)) for f in ("open", "high", "low", "close")):
            continue
        if any(float(row.get(f, 0)) <= 0 for f in ("open", "high", "low", "close")):
            continue
        if not _is_valid_number(row.get("volume")) or float(row.get("volume", -1)) < 0:
            continue
        clean.append(row)
    return clean, len(rows) - len(clean)


def _filter_financial_reports(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    clean: list[dict[str, Any]] = []
    for row in rows:
        if not row.get("report_date"):
            continue
        # At least one of revenue/net_profit should be a valid number
        if not _is_valid_number(row.get("revenue")) and not _is_valid_number(row.get("net_profit")):
            continue
        clean.append(row)
    return clean, len(rows) - len(clean)


def _filter_news_items(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    clean: list[dict[str, Any]] = []
    for row in rows:
        if not row.get("news_id"):
            continue
        title = row.get("title")
        if not title or not str(title).strip():
            continue
        clean.append(row)
    return clean, len(rows) - len(clean)


def _filter_announcements(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    clean: list[dict[str, Any]] = []
    for row in rows:
        if not row.get("announcement_id"):
            continue
        title = row.get("title")
        if not title or not str(title).strip():
            continue
        clean.append(row)
    return clean, len(rows) - len(clean)


# ---------------------------------------------------------------------------
# Check cancel / pause
# ---------------------------------------------------------------------------


def _check_cancel_pause(
    cancel_event: threading.Event | None,
    pause_event: threading.Event | None,
) -> bool:
    """Return True if job should be cancelled."""
    if cancel_event and cancel_event.is_set():
        return True
    if pause_event:
        # Block until resumed or cancelled
        while not pause_event.is_set():
            if cancel_event and cancel_event.is_set():
                return True
            pause_event.wait(timeout=1.0)
    return False


# ---------------------------------------------------------------------------
# Live sync functions (with retry + filter + cancel/pause + progress)
# ---------------------------------------------------------------------------


def _live_symbol_sync(adapter, source_name: str) -> tuple[int, int]:
    updated_at = _utc_now()
    raw_rows = _retry_fetch(adapter.fetch_symbol_list, label=f"{source_name}/symbols")
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
    return upsert_symbol_master(symbol_rows), upsert_company_profiles(profile_rows)


def _sync_single_history(
    adapter,
    symbol: str,
    source_name: str,
    start_date,
    end_date,
    updated_at: datetime,
) -> tuple[int, int, str | None]:
    """Sync one symbol's daily quotes. Returns (written, filtered, error_msg)."""
    try:
        rows = _retry_fetch(
            adapter.fetch_daily_quotes,
            args=(symbol, start_date, end_date),
            label=f"{source_name}/{symbol}/quotes",
        )
    except Exception as exc:
        return 0, 0, f"{symbol} 日线抓取失败: {exc}"

    for row in rows:
        row["source"] = source_name
        row["updated_at"] = updated_at
    clean, filtered = _filter_daily_quotes(rows)
    written = upsert_daily_quotes(clean)
    return written, filtered, None


def _sync_single_financial(
    adapter,
    symbol: str,
    source_name: str,
    periods: int,
    updated_at: datetime,
) -> tuple[int, int, str | None]:
    try:
        rows = _retry_fetch(
            adapter.fetch_financials,
            args=(symbol, periods),
            label=f"{source_name}/{symbol}/financials",
        )
    except Exception as exc:
        return 0, 0, f"{symbol} 财务数据抓取失败: {exc}"

    for row in rows:
        row["source"] = source_name
        row["updated_at"] = updated_at
    clean, filtered = _filter_financial_reports(rows)
    written = upsert_financial_reports(clean)
    return written, filtered, None


def _sync_single_news(
    adapter,
    symbol: str,
    source_name: str,
    count: int,
    updated_at: datetime,
) -> tuple[int, int, str | None]:
    try:
        rows = _retry_fetch(
            adapter.fetch_news,
            args=(symbol, count),
            label=f"{source_name}/{symbol}/news",
        )
    except Exception as exc:
        return 0, 0, f"{symbol} 新闻抓取失败: {exc}"

    for row in rows:
        row["source"] = source_name
        row["updated_at"] = updated_at
    clean, filtered = _filter_news_items(rows)
    written = upsert_news_items(clean)
    return written, filtered, None


def _sync_single_announcement(
    adapter,
    symbol: str,
    source_name: str,
    count: int,
    updated_at: datetime,
) -> tuple[int, int, str | None]:
    try:
        rows = _retry_fetch(
            adapter.fetch_announcements,
            args=(symbol, count),
            label=f"{source_name}/{symbol}/announcements",
        )
    except Exception as exc:
        return 0, 0, f"{symbol} 公告抓取失败: {exc}"

    for row in rows:
        row["source"] = source_name
        row["updated_at"] = updated_at
    clean, filtered = _filter_announcements(rows)
    written = upsert_announcements(clean)
    return written, filtered, None


def _run_per_symbol(
    fn: Callable,
    symbols: list[str],
    *,
    max_workers: int = DEFAULT_MAX_WORKERS,
    cancel_event: threading.Event | None = None,
    pause_event: threading.Event | None = None,
    progress: ProgressCallback = _noop_progress,
    label: str = "",
) -> tuple[int, int, int, int, list[str]]:
    """Execute *fn(symbol)* for each symbol with concurrency, cancel, pause, progress.

    *fn* must accept a single positional arg (symbol) and return
    ``(written: int, filtered: int, error_msg: str | None)``.

    Returns ``(total_written, total_filtered, ok_count, error_count, errors)``.
    """
    total_written = 0
    total_filtered = 0
    ok_count = 0
    error_count = 0
    errors: list[str] = []
    completed = 0

    progress(total_items=len(symbols), completed_items=0)

    effective_workers = min(max_workers, len(symbols))
    if effective_workers <= 1:
        # Sequential path — simpler and also avoids ThreadPoolExecutor overhead for 1 worker
        for symbol in symbols:
            if _check_cancel_pause(cancel_event, pause_event):
                errors.append("用户取消了同步任务。")
                break
            progress(current_item=symbol)
            written, filtered, err = fn(symbol)
            total_written += written
            total_filtered += filtered
            if err:
                error_count += 1
                errors.append(err)
            else:
                ok_count += 1
            completed += 1
            progress(completed_items=completed, error_items=error_count)
        return total_written, total_filtered, ok_count, error_count, errors

    # Concurrent path
    with ThreadPoolExecutor(max_workers=effective_workers) as pool:
        future_to_symbol: dict[Any, str] = {}
        for symbol in symbols:
            if _check_cancel_pause(cancel_event, pause_event):
                errors.append("用户取消了同步任务。")
                break
            future = pool.submit(fn, symbol)
            future_to_symbol[future] = symbol

        for future in as_completed(future_to_symbol):
            if _check_cancel_pause(cancel_event, pause_event):
                # Cancel remaining futures
                for f in future_to_symbol:
                    f.cancel()
                errors.append("用户取消了同步任务。")
                break

            symbol = future_to_symbol[future]
            progress(current_item=symbol)
            try:
                written, filtered, err = future.result()
                total_written += written
                total_filtered += filtered
                if err:
                    error_count += 1
                    errors.append(err)
                else:
                    ok_count += 1
            except Exception as exc:
                error_count += 1
                errors.append(f"{symbol} 处理异常: {exc}")

            completed += 1
            progress(completed_items=completed, error_items=error_count)

    return total_written, total_filtered, ok_count, error_count, errors


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def execute_sync_job(
    job: dict[str, Any],
    *,
    cancel_event: threading.Event | None = None,
    pause_event: threading.Event | None = None,
    progress: ProgressCallback = _noop_progress,
) -> SyncExecutionResult:
    settings = load_settings()
    source_name = job["source"]
    source_config = settings["data_sources"].get(source_name)
    if not source_config:
        raise ValueError(f"未知数据源：{source_name}")

    runtime_status = describe_source_status(source_name, source_config)
    use_live = runtime_status.live_mode

    params = job.get("params", {})
    sync_mode = str(params.get("sync_mode", "standard"))
    if sync_mode not in SYNC_MODE_PRESETS:
        sync_mode = "standard"
    preset = SYNC_MODE_PRESETS[sync_mode]
    max_workers = int(params.get("max_workers", DEFAULT_MAX_WORKERS))
    allow_all = sync_mode == "full"

    # ---- health_check ----
    if job["job_type"] == "health_check":
        if use_live:
            adapter = _create_adapter(source_name, source_config)
            if adapter is None:
                return SyncExecutionResult(
                    status="completed_with_warnings",
                    summary=f"{source_name} 连接测试未执行：未找到可用适配器。",
                    warnings=["未找到可用适配器。"],
                )

            ok, msg = adapter.test_connection()
            return SyncExecutionResult(
                status="completed" if ok else "completed_with_warnings",
                summary=f"{source_name} 连接测试{'成功' if ok else '失败'}：{msg}",
                warnings=[] if ok else [msg],
            )

        summary = f"{source_name} 当前不可执行实时同步：{runtime_status.note}"
        return SyncExecutionResult(status="completed_with_warnings", summary=summary, warnings=[runtime_status.note])

    if not init_market_store():
        raise RuntimeError("DuckDB 依赖不可用，无法初始化本地数据仓。")

    if not use_live:
        summary = f"{source_name} 实时同步失败：{runtime_status.note}"
        return _fail_sync(summary, [runtime_status.note])

    adapter = _create_adapter(source_name, source_config)
    if adapter is None:
        return _fail_sync(f"{source_name} 实时同步失败：未找到可用适配器。", ["未找到可用适配器。"])

    # ---- symbol_sync ----
    if job["job_type"] == "symbol_sync":
        if _check_cancel_pause(cancel_event, pause_event):
            return _cancel_sync(f"{source_name} 股票基础信息同步被用户取消。")

        progress(total_items=1, current_item="股票列表")
        symbol_count, profile_count = _live_symbol_sync(adapter, source_name)
        progress(completed_items=1)
        if cancel_event and cancel_event.is_set():
            return _cancel_sync(
                f"{source_name} 股票基础信息同步被用户取消。写入 {symbol_count} 条记录。",
                ["用户取消了同步任务。"],
            )
        if symbol_count <= 0:
            return _fail_sync(f"{source_name} 股票基础信息同步失败：未写入任何记录。")

        warnings: list[str] = []
        summary = f"{source_name} 已写入 {symbol_count} 条股票基础信息，更新 {profile_count} 条公司档案。"
        if profile_count <= 0:
            warnings.append("公司档案未写入任何记录。")
        return _complete_sync(summary, warnings)

    # ---- history_sync ----
    if job["job_type"] == "history_sync":
        symbols = _resolve_symbols(job, allow_all=allow_all)
        days = preset["history_days"]
        updated_at = _utc_now()
        end_date = _utc_now().date()
        start_date = end_date - timedelta(days=int(days * 1.5))

        def _do_history(sym: str) -> tuple[int, int, str | None]:
            return _sync_single_history(adapter, sym, source_name, start_date, end_date, updated_at)

        written, filtered, ok, errs, errors = _run_per_symbol(
            _do_history, symbols,
            max_workers=max_workers,
            cancel_event=cancel_event, pause_event=pause_event,
            progress=progress, label="history",
        )

        if cancel_event and cancel_event.is_set():
            return _cancel_sync(f"{source_name} 历史行情同步被用户取消。写入 {written} 条记录。", errors)

        # Also sync index data
        index_count, index_errors = _live_index_sync(adapter, source_name, days)
        all_warnings = list(errors)
        if index_count <= 0:
            all_warnings.append("指数日线缺失。")
        all_warnings.extend(index_errors)
        if filtered > 0:
            all_warnings.append(f"过滤了 {filtered} 条脏数据。")

        if written <= 0:
            detail = _format_details(errors, "未获取到任何个股日线数据。")
            return _fail_sync(f"{source_name} 历史行情同步失败：{detail}", all_warnings)

        summary = (
            f"{source_name} 已同步 {ok}/{len(symbols)} 只股票的历史行情（{sync_mode}模式，{days}天），"
            f"写入 {written} 条个股日线记录"
        )
        if errs > 0:
            summary += f"，{errs} 只失败"
        if filtered > 0:
            summary += f"，过滤 {filtered} 条脏数据"
        if index_count > 0:
            summary += f"，并写入 {index_count} 条指数日线记录。"
        else:
            summary += "。"
        return _complete_sync(summary, all_warnings)

    # ---- financial_sync ----
    if job["job_type"] == "financial_sync":
        symbols = _resolve_symbols(job, allow_all=allow_all)
        periods = preset["financial_periods"]
        updated_at = _utc_now()

        def _do_financial(sym: str) -> tuple[int, int, str | None]:
            return _sync_single_financial(adapter, sym, source_name, periods, updated_at)

        written, filtered, ok, errs, errors = _run_per_symbol(
            _do_financial, symbols,
            max_workers=max_workers,
            cancel_event=cancel_event, pause_event=pause_event,
            progress=progress, label="financial",
        )

        if cancel_event and cancel_event.is_set():
            return _cancel_sync(f"{source_name} 财务数据同步被用户取消。写入 {written} 条记录。", errors)

        all_warnings = list(errors)
        if filtered > 0:
            all_warnings.append(f"过滤了 {filtered} 条脏数据。")

        if written <= 0:
            detail = _format_details(errors, "未获取到任何财务数据。")
            return _fail_sync(f"{source_name} 财务数据同步失败：{detail}", all_warnings)

        summary = (
            f"{source_name} 已同步 {ok}/{len(symbols)} 只股票的财务数据（{sync_mode}模式，{periods}期），"
            f"写入 {written} 条财报记录"
        )
        if errs > 0:
            summary += f"，{errs} 只失败"
        if filtered > 0:
            summary += f"，过滤 {filtered} 条脏数据"
        summary += "。"
        return _complete_sync(summary, all_warnings)

    # ---- news_sync ----
    if job["job_type"] == "news_sync":
        symbols = _resolve_symbols(job, allow_all=allow_all)
        news_count_limit = preset["news_count"]
        updated_at = _utc_now()

        # Market-wide news (non-symbol-specific)
        market_news_written = 0
        market_news_errors: list[str] = []
        if not adapter.news_is_symbol_specific:
            try:
                m_rows = _retry_fetch(
                    adapter.fetch_news,
                    args=(MARKET_WIDE_NEWS_SYMBOL, news_count_limit),
                    label=f"{source_name}/market-news",
                )
                for row in m_rows:
                    row["symbol"] = MARKET_WIDE_NEWS_SYMBOL
                    row["source"] = source_name
                    row["updated_at"] = updated_at
                clean, _ = _filter_news_items(m_rows)
                market_news_written = upsert_news_items(clean)
            except Exception as exc:
                market_news_errors.append(f"全市场新闻抓取失败: {exc}")

        # Per-symbol news
        def _do_news(sym: str) -> tuple[int, int, str | None]:
            if adapter.news_is_symbol_specific:
                return _sync_single_news(adapter, sym, source_name, news_count_limit, updated_at)
            return 0, 0, None  # already handled above

        news_written, news_filtered, news_ok, news_errs, news_errors = _run_per_symbol(
            _do_news, symbols,
            max_workers=max_workers,
            cancel_event=cancel_event, pause_event=pause_event,
            progress=progress, label="news",
        )

        if cancel_event and cancel_event.is_set():
            total = news_written + market_news_written
            return _cancel_sync(f"{source_name} 新闻同步被用户取消。写入 {total} 条记录。", news_errors)

        # Announcements
        ann_updated_at = _utc_now()

        def _do_ann(sym: str) -> tuple[int, int, str | None]:
            return _sync_single_announcement(adapter, sym, source_name, news_count_limit, ann_updated_at)

        ann_written, ann_filtered, ann_ok, ann_errs, ann_errors = _run_per_symbol(
            _do_ann, symbols,
            max_workers=max_workers,
            cancel_event=cancel_event, pause_event=pause_event,
            progress=progress, label="announcements",
        )

        total_news = news_written + market_news_written
        total_filtered = news_filtered + ann_filtered

        all_warnings = market_news_errors + news_errors
        if ann_written <= 0:
            all_warnings.append("公告数据缺失。")
        all_warnings.extend(ann_errors)
        if total_filtered > 0:
            all_warnings.append(f"过滤了 {total_filtered} 条脏数据。")

        if total_news <= 0:
            detail = _format_details(all_warnings, "未获取到任何新闻数据。")
            return _fail_sync(f"{source_name} 新闻同步失败：{detail}", all_warnings)

        summary = (
            f"{source_name} 已同步 {news_ok}/{len(symbols)} 只股票的新闻数据（{sync_mode}模式），"
            f"写入 {total_news} 条新闻记录"
        )
        if ann_written > 0:
            summary += f"，并写入 {ann_written} 条公告记录"
        if news_errs + ann_errs > 0:
            summary += f"，{news_errs + ann_errs} 项失败"
        if total_filtered > 0:
            summary += f"，过滤 {total_filtered} 条脏数据"
        summary += "。"
        return _complete_sync(summary, all_warnings)

    raise ValueError(f"不支持的同步任务类型：{job['job_type']}")


def _live_index_sync(adapter, source_name: str, days: int = 60) -> tuple[int, list[str]]:
    """Sync major index daily data."""
    updated_at = _utc_now()
    end_date = _utc_now().date()
    start_date = end_date - timedelta(days=int(days * 1.5))
    rows_to_write: list[dict[str, Any]] = []
    errors: list[str] = []

    for index_code in DEFAULT_INDEX_CODES:
        try:
            rows = _retry_fetch(
                adapter.fetch_index_daily,
                args=(index_code, start_date, end_date),
                label=f"{source_name}/{index_code}/index",
            )
        except Exception as exc:
            logger.warning("同步指数 %s 日线失败: %s", index_code, exc)
            errors.append(f"{index_code} 指数抓取失败: {exc}")
            continue

        for row in rows:
            row["source"] = source_name
            row["updated_at"] = updated_at
        rows_to_write.extend(rows)

    return upsert_index_daily(rows_to_write), errors
