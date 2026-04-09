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


def _import_duckdb():
    import duckdb

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
    except ModuleNotFoundError:
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
        rows = connection.execute(
            """
            SELECT news_id, published_at, title, content, url, source
            FROM news_items
            WHERE symbol IN (?, '__MARKET__')
            ORDER BY published_at DESC
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
