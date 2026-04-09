from __future__ import annotations

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


@contextmanager
def get_market_connection() -> Iterator[Any]:
    ensure_project_dirs()
    duckdb = _import_duckdb()
    connection = duckdb.connect(str(DUCKDB_PATH))
    try:
        yield connection
    finally:
        connection.close()


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
