"""Smoke tests for stocks data management API."""
from __future__ import annotations

from datetime import datetime, timezone

from app.core.market_store import (
    get_market_connection,
    upsert_daily_quotes,
    upsert_financial_reports,
    upsert_news_items,
    upsert_symbol_master,
    upsert_company_profiles,
)


_NOW = datetime.now(timezone.utc)
_SYMBOL = "000001.SZ"


def _seed_data():
    """Insert a handful of fixture rows for testing."""
    upsert_symbol_master([
        {"symbol": "000001.SZ", "exchange": "SZ", "name": "平安银行",
         "listing_date": "1991-04-03", "status": "L", "source": "akshare", "updated_at": _NOW},
        {"symbol": "600519.SH", "exchange": "SH", "name": "贵州茅台",
         "listing_date": "2001-08-27", "status": "L", "source": "akshare", "updated_at": _NOW},
    ])
    upsert_company_profiles([
        {"symbol": "000001.SZ", "name": "平安银行", "industry": "银行", "area": "深圳",
         "listing_date": "1991-04-03", "source": "akshare", "updated_at": _NOW},
    ])
    upsert_daily_quotes([
        {"symbol": _SYMBOL, "trade_date": "2026-04-01", "open": 10.0, "high": 11.0,
         "low": 9.5, "close": 10.5, "volume": 100000, "amount": 1050000,
         "source": "akshare", "updated_at": _NOW},
        {"symbol": _SYMBOL, "trade_date": "2026-04-02", "open": 10.5, "high": 11.5,
         "low": 10.0, "close": 11.0, "volume": 120000, "amount": 1320000,
         "source": "akshare", "updated_at": _NOW},
    ])
    upsert_financial_reports([
        {"symbol": _SYMBOL, "report_date": "2025-12-31", "report_type": "annual",
         "revenue": 1e9, "net_profit": 2e8, "roe": 0.12, "gross_margin": 0.35,
         "source": "tushare", "updated_at": _NOW},
    ])
    upsert_news_items([
        {"news_id": "n001", "symbol": _SYMBOL, "published_at": _NOW,
         "title": "测试新闻", "content": "新闻内容", "url": "https://example.com",
         "source": "akshare", "updated_at": _NOW},
    ])


# ---- List stocks ----

def test_list_stocks_empty(client):
    resp = client.get("/api/stocks")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data


def test_list_stocks_with_data(client):
    _seed_data()
    resp = client.get("/api/stocks?page=1&page_size=10")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 2
    symbols = [item["symbol"] for item in data["items"]]
    assert "000001.SZ" in symbols


def test_list_stocks_search(client):
    _seed_data()
    resp = client.get("/api/stocks?search=平安")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert data["items"][0]["name"] == "平安银行"


# ---- Data summary ----

def test_stock_data_summary(client):
    _seed_data()
    resp = client.get(f"/api/stocks/{_SYMBOL}/data-summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["symbol"] == _SYMBOL
    assert isinstance(data["summaries"], list)
    # Should have at least daily_quotes from akshare
    dq = [s for s in data["summaries"] if s["data_type"] == "daily_quotes" and s["source"] == "akshare"]
    assert len(dq) == 1
    assert dq[0]["record_count"] == 2


# ---- Data page view ----

def test_stock_data_page(client):
    _seed_data()
    resp = client.get(f"/api/stocks/{_SYMBOL}/data?source=akshare&data_type=daily_quotes&page=1&page_size=10")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert len(data["rows"]) == 2
    assert "columns" in data


def test_stock_data_page_invalid_type(client):
    resp = client.get(f"/api/stocks/{_SYMBOL}/data?source=akshare&data_type=invalid&page=1")
    assert resp.status_code == 400


# ---- CSV download ----

def test_stock_data_download(client):
    _seed_data()
    resp = client.get(f"/api/stocks/{_SYMBOL}/data/download?source=akshare&data_type=daily_quotes")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    content = resp.text
    assert "trade_date" in content  # header row
    assert "2026-04-01" in content


def test_stock_data_download_invalid_type(client):
    resp = client.get(f"/api/stocks/{_SYMBOL}/data/download?source=akshare&data_type=bad")
    assert resp.status_code == 400


# ---- Delete ----

def test_delete_stock_data(client):
    _seed_data()
    # Delete daily_quotes for akshare
    resp = client.delete(f"/api/stocks/{_SYMBOL}/data?source=akshare&data_type=daily_quotes")
    assert resp.status_code == 200
    data = resp.json()
    assert data["deleted_count"] >= 2

    # Verify deletion
    resp2 = client.get(f"/api/stocks/{_SYMBOL}/data?source=akshare&data_type=daily_quotes&page=1")
    assert resp2.json()["total"] == 0


# ---- Sync by source ----

def test_sync_stock_by_source(client):
    _seed_data()
    resp = client.post(f"/api/stocks/{_SYMBOL}/sync", json={"source": "akshare"})
    assert resp.status_code == 200
    jobs = resp.json()
    assert isinstance(jobs, list)
    assert len(jobs) == 3  # history_sync, financial_sync, news_sync
    job_types = {j["job_type"] for j in jobs}
    assert job_types == {"history_sync", "financial_sync", "news_sync"}


def test_sync_stock_invalid_source(client):
    resp = client.post(f"/api/stocks/{_SYMBOL}/sync", json={"source": "invalid"})
    assert resp.status_code == 400
