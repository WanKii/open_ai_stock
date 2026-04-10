from __future__ import annotations

import threading
from contextlib import contextmanager
from typing import Any, Iterator

from .config import DUCKDB_PATH, ensure_project_dirs


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS symbol_master (
    symbol TEXT PRIMARY KEY,
    exchange TEXT NOT NULL,
    name TEXT NOT NULL,
    listing_date DATE,
    status TEXT NOT NULL,
    source TEXT NOT NULL,
    updated_at TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS company_profile (
    symbol TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    industry TEXT,
    area TEXT,
    listing_date DATE,
    source TEXT NOT NULL,
    updated_at TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS daily_quotes (
    symbol TEXT NOT NULL,
    trade_date DATE NOT NULL,
    open DOUBLE NOT NULL,
    high DOUBLE NOT NULL,
    low DOUBLE NOT NULL,
    close DOUBLE NOT NULL,
    volume DOUBLE NOT NULL,
    amount DOUBLE NOT NULL,
    source TEXT NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    PRIMARY KEY (symbol, trade_date, source)
);

CREATE TABLE IF NOT EXISTS realtime_quote_cache (
    symbol TEXT PRIMARY KEY,
    quote_time TIMESTAMP NOT NULL,
    price DOUBLE NOT NULL,
    change_pct DOUBLE NOT NULL,
    source TEXT NOT NULL,
    updated_at TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS financial_reports (
    symbol TEXT NOT NULL,
    report_date DATE NOT NULL,
    report_type TEXT NOT NULL,
    revenue DOUBLE NOT NULL,
    net_profit DOUBLE NOT NULL,
    roe DOUBLE NOT NULL,
    gross_margin DOUBLE NOT NULL,
    source TEXT NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    PRIMARY KEY (symbol, report_date, report_type, source)
);

CREATE TABLE IF NOT EXISTS news_items (
    news_id TEXT PRIMARY KEY,
    symbol TEXT NOT NULL,
    published_at TIMESTAMP NOT NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    url TEXT NOT NULL,
    source TEXT NOT NULL,
    updated_at TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS announcements (
    announcement_id TEXT PRIMARY KEY,
    symbol TEXT NOT NULL,
    published_at TIMESTAMP NOT NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    url TEXT NOT NULL,
    source TEXT NOT NULL,
    updated_at TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS index_daily (
    index_code TEXT NOT NULL,
    trade_date DATE NOT NULL,
    close DOUBLE NOT NULL,
    change_pct DOUBLE NOT NULL,
    source TEXT NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    PRIMARY KEY (index_code, trade_date, source)
);

CREATE TABLE IF NOT EXISTS sector_daily (
    sector_code TEXT NOT NULL,
    trade_date DATE NOT NULL,
    close DOUBLE NOT NULL,
    change_pct DOUBLE NOT NULL,
    source TEXT NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    PRIMARY KEY (sector_code, trade_date, source)
);
"""


DUCKDB_UNAVAILABLE_MESSAGE = (
    "DuckDB 依赖未安装，市场数据功能不可用。"
    "请使用项目虚拟环境启动，或先执行 `pip install -r backend/requirements.txt`。"
)


class MarketStoreUnavailableError(RuntimeError):
    """Raised when the local DuckDB-backed market store cannot be used."""


def _import_duckdb():
    try:
        import duckdb
    except ModuleNotFoundError as exc:
        raise MarketStoreUnavailableError(DUCKDB_UNAVAILABLE_MESSAGE) from exc

    return duckdb


_connection_lock = threading.Lock()
_shared_connection = None


def _get_shared_connection():
    global _shared_connection
    if _shared_connection is None:
        ensure_project_dirs()
        duckdb = _import_duckdb()
        _shared_connection = duckdb.connect(str(DUCKDB_PATH))
    return _shared_connection


@contextmanager
def get_market_connection() -> Iterator[Any]:
    with _connection_lock:
        yield _get_shared_connection()


def close_market_connection() -> None:
    global _shared_connection
    with _connection_lock:
        if _shared_connection is not None:
            _shared_connection.close()
            _shared_connection = None


def init_market_store() -> bool:
    try:
        with get_market_connection() as connection:
            connection.execute(SCHEMA_SQL)
        return True
    except MarketStoreUnavailableError:
        return False


def upsert_symbol_master(rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0

    payload = [
        (
            row["symbol"],
            row["exchange"],
            row["name"],
            row["listing_date"],
            row["status"],
            row["source"],
            row["updated_at"],
        )
        for row in rows
    ]

    with get_market_connection() as connection:
        connection.executemany(
            """
            INSERT OR REPLACE INTO symbol_master (
                symbol, exchange, name, listing_date, status, source, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            payload,
        )

    return len(payload)


def upsert_company_profiles(rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0

    payload = [
        (
            row["symbol"],
            row["name"],
            row.get("industry"),
            row.get("area"),
            row.get("listing_date"),
            row["source"],
            row["updated_at"],
        )
        for row in rows
    ]

    with get_market_connection() as connection:
        connection.executemany(
            """
            INSERT OR REPLACE INTO company_profile (
                symbol, name, industry, area, listing_date, source, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            payload,
        )

    return len(payload)


def upsert_daily_quotes(rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0

    payload = [
        (
            row["symbol"],
            row["trade_date"],
            row["open"],
            row["high"],
            row["low"],
            row["close"],
            row["volume"],
            row["amount"],
            row["source"],
            row["updated_at"],
        )
        for row in rows
    ]

    with get_market_connection() as connection:
        connection.executemany(
            """
            INSERT OR REPLACE INTO daily_quotes (
                symbol, trade_date, open, high, low, close, volume, amount, source, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            payload,
        )

    return len(payload)


def upsert_financial_reports(rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0

    payload = [
        (
            row["symbol"],
            row["report_date"],
            row["report_type"],
            row["revenue"],
            row["net_profit"],
            row["roe"],
            row["gross_margin"],
            row["source"],
            row["updated_at"],
        )
        for row in rows
    ]

    with get_market_connection() as connection:
        connection.executemany(
            """
            INSERT OR REPLACE INTO financial_reports (
                symbol, report_date, report_type, revenue, net_profit, roe, gross_margin, source, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            payload,
        )

    return len(payload)


def upsert_news_items(rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0

    payload = [
        (
            row["news_id"],
            row["symbol"],
            row["published_at"],
            row["title"],
            row["content"],
            row["url"],
            row["source"],
            row["updated_at"],
        )
        for row in rows
    ]

    with get_market_connection() as connection:
        connection.executemany(
            """
            INSERT OR REPLACE INTO news_items (
                news_id, symbol, published_at, title, content, url, source, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            payload,
        )

    return len(payload)


def upsert_index_daily(rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0

    payload = [
        (
            row["index_code"],
            row["trade_date"],
            row["close"],
            row["change_pct"],
            row["source"],
            row["updated_at"],
        )
        for row in rows
    ]

    with get_market_connection() as connection:
        connection.executemany(
            """
            INSERT OR REPLACE INTO index_daily (
                index_code, trade_date, close, change_pct, source, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            payload,
        )

    return len(payload)


def upsert_announcements(rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0

    payload = [
        (
            row["announcement_id"],
            row["symbol"],
            row["published_at"],
            row["title"],
            row["content"],
            row["url"],
            row["source"],
            row["updated_at"],
        )
        for row in rows
    ]

    with get_market_connection() as connection:
        connection.executemany(
            """
            INSERT OR REPLACE INTO announcements (
                announcement_id, symbol, published_at, title, content, url, source, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            payload,
        )

    return len(payload)


def list_seed_symbols(limit: int = 3) -> list[str]:
    with get_market_connection() as connection:
        rows = connection.execute(
            """
            SELECT symbol
            FROM symbol_master
            ORDER BY updated_at DESC, symbol ASC
            LIMIT ?
            """,
            [limit],
        ).fetchall()

    return [row[0] for row in rows]


# ---------------------------------------------------------------------------
# 查询函数 — 面向分析引擎的读取层
# ---------------------------------------------------------------------------


def get_symbol_info(symbol: str) -> dict[str, Any] | None:
    with get_market_connection() as connection:
        row = connection.execute(
            """
            SELECT sm.symbol, sm.exchange, sm.name, sm.listing_date, sm.status,
                   cp.industry, cp.area
            FROM symbol_master sm
            LEFT JOIN company_profile cp ON sm.symbol = cp.symbol
            WHERE sm.symbol = ?
            """,
            [symbol],
        ).fetchone()

    if not row:
        return None
    cols = ["symbol", "exchange", "name", "listing_date", "status", "industry", "area"]
    return dict(zip(cols, row))


def get_daily_quotes(symbol: str, days: int = 60) -> list[dict[str, Any]]:
    with get_market_connection() as connection:
        rows = connection.execute(
            """
            SELECT trade_date, open, high, low, close, volume, amount, source
            FROM daily_quotes
            WHERE symbol = ?
            ORDER BY trade_date DESC
            LIMIT ?
            """,
            [symbol, days],
        ).fetchall()

    cols = ["trade_date", "open", "high", "low", "close", "volume", "amount", "source"]
    return [dict(zip(cols, row)) for row in reversed(rows)]


def get_financials(symbol: str, quarters: int = 4) -> list[dict[str, Any]]:
    with get_market_connection() as connection:
        rows = connection.execute(
            """
            SELECT report_date, report_type, revenue, net_profit, roe, gross_margin, source
            FROM financial_reports
            WHERE symbol = ?
            ORDER BY report_date DESC
            LIMIT ?
            """,
            [symbol, quarters],
        ).fetchall()

    cols = ["report_date", "report_type", "revenue", "net_profit", "roe", "gross_margin", "source"]
    return [dict(zip(cols, row)) for row in reversed(rows)]


def get_news(symbol: str, count: int = 20) -> list[dict[str, Any]]:
    with get_market_connection() as connection:
        # 优先取个股新闻，再补全市场新闻，合计不超过 count 条
        rows = connection.execute(
            """
            SELECT news_id, published_at, title, content, url, source
            FROM (
                SELECT *, 0 AS priority FROM news_items WHERE symbol = ?
                UNION ALL
                SELECT *, 1 AS priority FROM news_items WHERE symbol = '__MARKET__'
            ) sub
            ORDER BY priority ASC, published_at DESC
            LIMIT ?
            """,
            [symbol, count],
        ).fetchall()

    cols = ["news_id", "published_at", "title", "content", "url", "source"]
    return [dict(zip(cols, row)) for row in rows]


def get_announcements(symbol: str, count: int = 20) -> list[dict[str, Any]]:
    with get_market_connection() as connection:
        rows = connection.execute(
            """
            SELECT announcement_id, published_at, title, content, url, source
            FROM announcements
            WHERE symbol = ?
            ORDER BY published_at DESC
            LIMIT ?
            """,
            [symbol, count],
        ).fetchall()

    cols = ["announcement_id", "published_at", "title", "content", "url", "source"]
    return [dict(zip(cols, row)) for row in rows]


def get_index_daily(index_code: str, days: int = 60) -> list[dict[str, Any]]:
    with get_market_connection() as connection:
        rows = connection.execute(
            """
            SELECT trade_date, close, change_pct, source
            FROM index_daily
            WHERE index_code = ?
            ORDER BY trade_date DESC
            LIMIT ?
            """,
            [index_code, days],
        ).fetchall()

    cols = ["trade_date", "close", "change_pct", "source"]
    return [dict(zip(cols, row)) for row in reversed(rows)]


def get_sector_daily(sector_code: str, days: int = 60) -> list[dict[str, Any]]:
    with get_market_connection() as connection:
        rows = connection.execute(
            """
            SELECT trade_date, close, change_pct, source
            FROM sector_daily
            WHERE sector_code = ?
            ORDER BY trade_date DESC
            LIMIT ?
            """,
            [sector_code, days],
        ).fetchall()

    cols = ["trade_date", "close", "change_pct", "source"]
    return [dict(zip(cols, row)) for row in reversed(rows)]


# ---------------------------------------------------------------------------
# 股票数据管理 — 列表 / 汇总 / 分页查看 / 导出 / 删除
# ---------------------------------------------------------------------------

_DATA_TYPE_TABLE: dict[str, str] = {
    "daily_quotes": "daily_quotes",
    "financial_reports": "financial_reports",
    "news_items": "news_items",
    "announcements": "announcements",
}


def list_stocks(
    page: int = 1,
    page_size: int = 50,
    search: str | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """分页查询已同步的股票列表，支持按代码/名称模糊搜索。返回 (rows, total)。"""
    where = ""
    params: list[Any] = []
    if search:
        where = "WHERE sm.symbol ILIKE ? OR sm.name ILIKE ?"
        params = [f"%{search}%", f"%{search}%"]

    with get_market_connection() as connection:
        total_row = connection.execute(
            f"SELECT COUNT(*) FROM symbol_master sm {where}", params
        ).fetchone()
        total = total_row[0] if total_row else 0

        offset = (page - 1) * page_size
        rows = connection.execute(
            f"""
            SELECT sm.symbol, sm.exchange, sm.name, sm.listing_date, sm.status,
                   cp.industry, cp.area
            FROM symbol_master sm
            LEFT JOIN company_profile cp ON sm.symbol = cp.symbol
            {where}
            ORDER BY sm.symbol ASC
            LIMIT ? OFFSET ?
            """,
            [*params, page_size, offset],
        ).fetchall()

    cols = ["symbol", "exchange", "name", "listing_date", "status", "industry", "area"]
    return [dict(zip(cols, row)) for row in rows], total


def get_stock_data_summary(symbol: str) -> list[dict[str, Any]]:
    """返回某支股票在各数据源 × 各数据类型下的记录数和最新日期。"""
    sql = """
    SELECT 'daily_quotes' AS data_type, source,
           COUNT(*) AS record_count, MAX(trade_date)::TEXT AS latest_date
    FROM daily_quotes WHERE symbol = ? GROUP BY source
    UNION ALL
    SELECT 'financial_reports', source,
           COUNT(*), MAX(report_date)::TEXT
    FROM financial_reports WHERE symbol = ? GROUP BY source
    UNION ALL
    SELECT 'news_items', source,
           COUNT(*), MAX(published_at)::TEXT
    FROM news_items WHERE symbol = ? GROUP BY source
    UNION ALL
    SELECT 'announcements', source,
           COUNT(*), MAX(published_at)::TEXT
    FROM announcements WHERE symbol = ? GROUP BY source
    """
    with get_market_connection() as connection:
        rows = connection.execute(sql, [symbol, symbol, symbol, symbol]).fetchall()

    cols = ["data_type", "source", "record_count", "latest_date"]
    return [dict(zip(cols, row)) for row in rows]


def _data_type_columns(data_type: str) -> tuple[str, list[str]]:
    """返回 (sql_select_columns_str, col_names_list)。"""
    if data_type == "daily_quotes":
        cols = ["trade_date", "open", "high", "low", "close", "volume", "amount", "source"]
        order = "trade_date DESC"
    elif data_type == "financial_reports":
        cols = ["report_date", "report_type", "revenue", "net_profit", "roe", "gross_margin", "source"]
        order = "report_date DESC"
    elif data_type == "news_items":
        cols = ["news_id", "published_at", "title", "content", "url", "source"]
        order = "published_at DESC"
    elif data_type == "announcements":
        cols = ["announcement_id", "published_at", "title", "content", "url", "source"]
        order = "published_at DESC"
    else:
        raise ValueError(f"Unknown data_type: {data_type}")
    return ", ".join(cols), cols, order  # type: ignore[return-value]


def get_stock_data_page(
    symbol: str,
    source: str,
    data_type: str,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[dict[str, Any]], int, list[str]]:
    """分页查看数据。返回 (rows, total, columns)。"""
    table = _DATA_TYPE_TABLE.get(data_type)
    if not table:
        raise ValueError(f"Unknown data_type: {data_type}")

    select_str, cols, order = _data_type_columns(data_type)  # type: ignore[misc]

    with get_market_connection() as connection:
        total_row = connection.execute(
            f"SELECT COUNT(*) FROM {table} WHERE symbol = ? AND source = ?",
            [symbol, source],
        ).fetchone()
        total = total_row[0] if total_row else 0

        offset = (page - 1) * page_size
        rows = connection.execute(
            f"""
            SELECT {select_str} FROM {table}
            WHERE symbol = ? AND source = ?
            ORDER BY {order}
            LIMIT ? OFFSET ?
            """,
            [symbol, source, page_size, offset],
        ).fetchall()

    return [dict(zip(cols, row)) for row in rows], total, cols


def get_stock_data_all(
    symbol: str,
    source: str,
    data_type: str,
) -> tuple[list[dict[str, Any]], list[str]]:
    """全量查询，用于 CSV 导出。返回 (rows, columns)。"""
    table = _DATA_TYPE_TABLE.get(data_type)
    if not table:
        raise ValueError(f"Unknown data_type: {data_type}")

    select_str, cols, order = _data_type_columns(data_type)  # type: ignore[misc]

    with get_market_connection() as connection:
        rows = connection.execute(
            f"""
            SELECT {select_str} FROM {table}
            WHERE symbol = ? AND source = ?
            ORDER BY {order}
            """,
            [symbol, source],
        ).fetchall()

    return [dict(zip(cols, row)) for row in rows], cols


def delete_stock_data(symbol: str, source: str, data_type: str) -> int:
    """删除指定 (symbol, source, data_type) 的数据，返回删除行数。"""
    table = _DATA_TYPE_TABLE.get(data_type)
    if not table:
        raise ValueError(f"Unknown data_type: {data_type}")

    with get_market_connection() as connection:
        before = connection.execute(
            f"SELECT COUNT(*) FROM {table} WHERE symbol = ? AND source = ?",
            [symbol, source],
        ).fetchone()
        count_before = before[0] if before else 0

        connection.execute(
            f"DELETE FROM {table} WHERE symbol = ? AND source = ?",
            [symbol, source],
        )

    return count_before


_ALL_TABLES = [
    "daily_quotes", "financial_reports", "news_items", "announcements",
    "index_daily", "sector_daily", "symbol_master", "company_profile",
    "realtime_quote_cache",
]


def truncate_all_tables() -> dict[str, int]:
    """Delete ALL data from all market tables. Returns {table: deleted_count}."""
    result: dict[str, int] = {}
    with get_market_connection() as connection:
        for table in _ALL_TABLES:
            count = connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            connection.execute(f"DELETE FROM {table}")
            result[table] = count
    return result


def truncate_by_source(source: str) -> dict[str, int]:
    """Delete all data for a given source. Returns {table: deleted_count}."""
    # Keep symbol metadata intact: symbol_master/company_profile are shared by the app
    # and keyed only by symbol, so deleting them by source can hide data that still exists
    # in other source-partitioned tables.
    source_tables = [
        "daily_quotes", "financial_reports", "news_items", "announcements",
        "index_daily", "sector_daily", "realtime_quote_cache",
    ]
    result: dict[str, int] = {}
    with get_market_connection() as connection:
        for table in source_tables:
            count = connection.execute(
                f"SELECT COUNT(*) FROM {table} WHERE source = ?", [source]
            ).fetchone()[0]
            connection.execute(f"DELETE FROM {table} WHERE source = ?", [source])
            result[table] = count
    return result


# ---------------------------------------------------------------------------
# FR-110 数据质量仪表板
# ---------------------------------------------------------------------------

_QUALITY_QUERIES: list[tuple[str, str]] = [
    (
        "symbol_master",
        """
        SELECT COUNT(*) AS row_count,
               COUNT(DISTINCT symbol) AS distinct_symbols,
               MAX(updated_at)::TEXT AS latest_date,
               MIN(updated_at)::TEXT AS oldest_date,
               LIST(DISTINCT source) AS sources
        FROM symbol_master
        """,
    ),
    (
        "company_profile",
        """
        SELECT COUNT(*) AS row_count,
               COUNT(DISTINCT symbol) AS distinct_symbols,
               MAX(updated_at)::TEXT AS latest_date,
               MIN(updated_at)::TEXT AS oldest_date,
               LIST(DISTINCT source) AS sources
        FROM company_profile
        """,
    ),
    (
        "daily_quotes",
        """
        SELECT COUNT(*) AS row_count,
               COUNT(DISTINCT symbol) AS distinct_symbols,
               MAX(trade_date)::TEXT AS latest_date,
               MIN(trade_date)::TEXT AS oldest_date,
               LIST(DISTINCT source) AS sources
        FROM daily_quotes
        """,
    ),
    (
        "financial_reports",
        """
        SELECT COUNT(*) AS row_count,
               COUNT(DISTINCT symbol) AS distinct_symbols,
               MAX(report_date)::TEXT AS latest_date,
               MIN(report_date)::TEXT AS oldest_date,
               LIST(DISTINCT source) AS sources
        FROM financial_reports
        """,
    ),
    (
        "news_items",
        """
        SELECT COUNT(*) AS row_count,
               COUNT(DISTINCT symbol) AS distinct_symbols,
               MAX(published_at)::TEXT AS latest_date,
               MIN(published_at)::TEXT AS oldest_date,
               LIST(DISTINCT source) AS sources
        FROM news_items
        """,
    ),
    (
        "announcements",
        """
        SELECT COUNT(*) AS row_count,
               COUNT(DISTINCT symbol) AS distinct_symbols,
               MAX(published_at)::TEXT AS latest_date,
               MIN(published_at)::TEXT AS oldest_date,
               LIST(DISTINCT source) AS sources
        FROM announcements
        """,
    ),
    (
        "index_daily",
        """
        SELECT COUNT(*) AS row_count,
               COUNT(DISTINCT index_code) AS distinct_symbols,
               MAX(trade_date)::TEXT AS latest_date,
               MIN(trade_date)::TEXT AS oldest_date,
               LIST(DISTINCT source) AS sources
        FROM index_daily
        """,
    ),
    (
        "sector_daily",
        """
        SELECT COUNT(*) AS row_count,
               COUNT(DISTINCT sector_code) AS distinct_symbols,
               MAX(trade_date)::TEXT AS latest_date,
               MIN(trade_date)::TEXT AS oldest_date,
               LIST(DISTINCT source) AS sources
        FROM sector_daily
        """,
    ),
]


def get_data_quality_overview() -> dict[str, Any]:
    """返回所有 DuckDB 市场数据表的质量概览。"""
    tables: list[dict[str, Any]] = []
    total_symbols = 0

    with get_market_connection() as connection:
        # 总股票数
        total_row = connection.execute("SELECT COUNT(*) FROM symbol_master").fetchone()
        total_symbols = total_row[0] if total_row else 0

        for table_name, sql in _QUALITY_QUERIES:
            row = connection.execute(sql).fetchone()
            if row:
                sources_raw = row[4] if row[4] else []
                tables.append({
                    "table_name": table_name,
                    "row_count": row[0] or 0,
                    "distinct_symbols": row[1] or 0,
                    "latest_date": row[2],
                    "oldest_date": row[3],
                    "sources": list(sources_raw) if sources_raw else [],
                })
            else:
                tables.append({
                    "table_name": table_name,
                    "row_count": 0,
                    "distinct_symbols": 0,
                    "latest_date": None,
                    "oldest_date": None,
                    "sources": [],
                })

    return {
        "total_symbols": total_symbols,
        "tables": tables,
    }
