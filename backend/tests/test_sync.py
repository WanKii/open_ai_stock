"""Smoke and unit tests for sync jobs API and semantics."""
from __future__ import annotations

import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from app.core import market_store
from app.services import demo_engine, repository
from app.services import sync_service


def _settings() -> dict:
    return {"data_sources": {"akshare": {"enabled": True, "token": "", "base_url": "https://akshare.akfamily.xyz"}}}


def _job(job_type: str, symbol: str = "000001.SH") -> dict:
    return {
        "id": f"job-{job_type}",
        "job_type": job_type,
        "source": "akshare",
        "scope": "single",
        "params": {"symbols": [symbol]},
    }


def test_create_sync_job(client):
    resp = client.post(
        "/api/sync/jobs",
        json={
            "job_type": "health_check",
            "source": "akshare",
            "scope": "all",
            "params": {},
        },
    )
    assert resp.status_code == 200
    job = resp.json()
    assert job["id"]
    assert job["job_type"] == "health_check"
    assert job["source"] == "akshare"
    assert job["status"] == "queued"
    # New progress fields should be present
    assert job["total_items"] == 0
    assert job["completed_items"] == 0


def test_list_sync_jobs(client):
    client.post(
        "/api/sync/jobs",
        json={"job_type": "symbol_sync", "source": "akshare", "scope": "all", "params": {}},
    )
    resp = client.get("/api/sync/jobs")
    assert resp.status_code == 200
    jobs = resp.json()
    assert isinstance(jobs, list)
    assert len(jobs) >= 1


def test_sync_job_end_to_end(client):
    create_resp = client.post(
        "/api/sync/jobs",
        json={"job_type": "health_check", "source": "akshare", "scope": "all", "params": {}},
    )
    job_id = create_resp.json()["id"]

    for _ in range(12):
        time.sleep(0.5)
        jobs_resp = client.get("/api/sync/jobs")
        jobs = jobs_resp.json()
        job = next((j for j in jobs if j["id"] == job_id), None)
        if job and job["status"] in ("completed", "completed_with_warnings", "failed"):
            break

    assert job is not None
    assert job["status"] in ("completed", "completed_with_warnings", "failed")


@pytest.mark.parametrize("job_type", ["symbol_sync", "history_sync", "financial_sync", "news_sync"])
def test_live_mode_disabled_realtime_sync_fails_without_fixture(monkeypatch, job_type):
    symbol = f"6888{len(job_type):02d}.SH"
    monkeypatch.setattr(sync_service, "load_settings", _settings)
    monkeypatch.setattr(sync_service, "init_market_store", lambda: True)
    monkeypatch.setattr(sync_service, "_create_adapter", lambda *_: pytest.fail("adapter should not be created"))
    monkeypatch.setattr(
        sync_service,
        "describe_source_status",
        lambda *_: sync_service.SourceRuntimeStatus(
            configured=False,
            status="dependency_missing",
            note="缺少对应 SDK，当前无法执行实时同步。",
            live_mode=False,
        ),
    )

    result = sync_service.execute_sync_job(_job(job_type, symbol))

    assert result.status == "failed"
    assert "无法执行实时同步" in result.summary


def _make_mock_adapter(*, quotes_empty=False, financials_empty=False, news_empty=False, announcements_empty=False, index_empty=False):
    adapter = MagicMock()
    adapter.news_is_symbol_specific = True
    if quotes_empty:
        adapter.fetch_daily_quotes.side_effect = Exception("timeout")
    else:
        adapter.fetch_daily_quotes.return_value = [
            {"symbol": "000001.SH", "trade_date": "2026-01-01", "open": 10, "high": 11, "low": 9, "close": 10.5, "volume": 1000, "amount": 10500},
        ]
    if financials_empty:
        adapter.fetch_financials.side_effect = Exception("blocked")
    else:
        adapter.fetch_financials.return_value = [
            {"symbol": "000001.SH", "report_date": "2025-12-31", "report_type": "年报", "revenue": 100, "net_profit": 10, "roe": 0.1, "gross_margin": 0.3},
        ]
    if news_empty:
        adapter.fetch_news.side_effect = Exception("blocked")
    else:
        adapter.fetch_news.return_value = [
            {"news_id": "n1", "symbol": "000001.SH", "published_at": "2026-01-01", "title": "Test", "content": "body", "url": "https://example.com"},
        ]
    if announcements_empty:
        adapter.fetch_announcements.side_effect = Exception("blocked")
    else:
        adapter.fetch_announcements.return_value = [
            {"announcement_id": "a1", "symbol": "000001.SH", "published_at": "2026-01-01", "title": "Ann", "content": "body", "url": "https://example.com"},
        ]
    if index_empty:
        adapter.fetch_index_daily.side_effect = Exception("blocked")
    else:
        adapter.fetch_index_daily.return_value = [
            {"index_code": "000300.SH", "trade_date": "2026-01-01", "close": 3800, "change_pct": 0.5},
        ]
    return adapter


def _patch_online(monkeypatch):
    monkeypatch.setattr(sync_service, "load_settings", _settings)
    monkeypatch.setattr(sync_service, "init_market_store", lambda: True)
    monkeypatch.setattr(
        sync_service,
        "describe_source_status",
        lambda *_: sync_service.SourceRuntimeStatus(True, "online", "ok", True),
    )
    # Disable retries in tests to avoid slow sleeps
    monkeypatch.setattr(sync_service, "DEFAULT_MAX_RETRIES", 1)


def test_history_sync_fails_when_primary_quotes_are_empty(monkeypatch):
    _patch_online(monkeypatch)
    adapter = _make_mock_adapter(quotes_empty=True, index_empty=True)
    monkeypatch.setattr(sync_service, "_create_adapter", lambda *_: adapter)
    monkeypatch.setattr(sync_service, "upsert_daily_quotes", lambda rows: 0)
    monkeypatch.setattr(sync_service, "upsert_index_daily", lambda rows: 0)

    result = sync_service.execute_sync_job(_job("history_sync"))

    assert result.status == "failed"
    assert "历史行情同步失败" in result.summary


def test_history_sync_warns_when_indexes_are_missing(monkeypatch):
    _patch_online(monkeypatch)
    adapter = _make_mock_adapter(index_empty=True)
    monkeypatch.setattr(sync_service, "_create_adapter", lambda *_: adapter)
    monkeypatch.setattr(sync_service, "upsert_daily_quotes", lambda rows: len(rows))
    monkeypatch.setattr(sync_service, "upsert_index_daily", lambda rows: 0)

    result = sync_service.execute_sync_job(_job("history_sync"))

    assert result.status == "completed_with_warnings"
    assert any("指数日线缺失" in w for w in result.warnings)


def test_news_sync_warns_when_announcements_are_missing(monkeypatch):
    _patch_online(monkeypatch)
    adapter = _make_mock_adapter(announcements_empty=True)
    monkeypatch.setattr(sync_service, "_create_adapter", lambda *_: adapter)
    monkeypatch.setattr(sync_service, "upsert_news_items", lambda rows: len(rows))
    monkeypatch.setattr(sync_service, "upsert_announcements", lambda rows: 0)

    result = sync_service.execute_sync_job(_job("news_sync"))

    assert result.status == "completed_with_warnings"
    assert any("公告数据缺失" in w for w in result.warnings)


def test_financial_sync_fails_when_reports_are_empty(monkeypatch):
    _patch_online(monkeypatch)
    adapter = _make_mock_adapter(financials_empty=True)
    monkeypatch.setattr(sync_service, "_create_adapter", lambda *_: adapter)
    monkeypatch.setattr(sync_service, "upsert_financial_reports", lambda rows: 0)

    result = sync_service.execute_sync_job(_job("financial_sync"))

    assert result.status == "failed"
    assert "财务数据同步失败" in result.summary


# ---------------------------------------------------------------------------
# New tests for v0.2 features
# ---------------------------------------------------------------------------


def test_dirty_data_filtering():
    from app.services.sync_service import _filter_daily_quotes, _filter_news_items

    dirty_rows = [
        {"trade_date": "2026-01-01", "open": 10, "high": 11, "low": 9, "close": 10, "volume": 100, "amount": 1000},
        {"trade_date": "", "open": 10, "high": 11, "low": 9, "close": 10, "volume": 100, "amount": 1000},  # empty date
        {"trade_date": "2026-01-02", "open": 0, "high": 11, "low": 9, "close": 10, "volume": 100, "amount": 1000},  # zero open
        {"trade_date": "2026-01-03", "open": None, "high": 11, "low": 9, "close": 10, "volume": 100, "amount": 1000},  # null open
        {"trade_date": "2026-01-04", "open": 10, "high": 11, "low": 9, "close": 10, "volume": -5, "amount": 1000},  # negative volume
    ]
    clean, filtered = _filter_daily_quotes(dirty_rows)
    assert len(clean) == 1
    assert filtered == 4

    news_dirty = [
        {"news_id": "n1", "title": "Good", "content": "x", "url": "http://x"},
        {"news_id": "", "title": "Bad", "content": "x", "url": "http://x"},  # no id
        {"news_id": "n3", "title": "", "content": "x", "url": "http://x"},  # empty title
        {"news_id": "n4", "title": None, "content": "x", "url": "http://x"},  # null title
    ]
    clean_news, filtered_news = _filter_news_items(news_dirty)
    assert len(clean_news) == 1
    assert filtered_news == 3


def test_sync_mode_presets():
    assert "standard" in sync_service.SYNC_MODE_PRESETS
    assert "full" in sync_service.SYNC_MODE_PRESETS
    assert "incremental" in sync_service.SYNC_MODE_PRESETS
    assert sync_service.SYNC_MODE_PRESETS["full"]["history_days"] == 3650
    assert sync_service.SYNC_MODE_PRESETS["standard"]["history_days"] == 365


def test_cancel_and_resume_signals():
    cancel, pause = sync_service.register_job_signals("test-job-1")
    assert not cancel.is_set()
    assert pause.is_set()  # not paused

    assert sync_service.request_pause("test-job-1")
    assert not pause.is_set()  # paused

    assert sync_service.request_resume("test-job-1")
    assert pause.is_set()  # resumed

    assert sync_service.request_cancel("test-job-1")
    assert cancel.is_set()

    sync_service.unregister_job_signals("test-job-1")
    assert not sync_service.request_cancel("test-job-1")  # no longer registered


def test_execute_sync_job_returns_cancelled_when_cancel_event_is_set(monkeypatch):
    _patch_online(monkeypatch)
    adapter = _make_mock_adapter()
    monkeypatch.setattr(sync_service, "_create_adapter", lambda *_: adapter)
    monkeypatch.setattr(sync_service, "upsert_daily_quotes", lambda rows: len(rows))
    monkeypatch.setattr(sync_service, "upsert_index_daily", lambda rows: len(rows))
    cancel_event = threading.Event()
    cancel_event.set()

    result = sync_service.execute_sync_job(_job("history_sync"), cancel_event=cancel_event)

    assert result.status == "cancelled"
    assert "取消" in result.summary


def test_process_sync_job_skips_jobs_cancelled_while_queued(monkeypatch):
    job = repository.create_sync_job("health_check", "akshare", "all", {})
    repository.update_sync_job(job["id"], "cancelled", result_summary="用户手动取消。")
    monkeypatch.setattr(demo_engine, "execute_sync_job", lambda *_args, **_kwargs: pytest.fail("cancelled queued job should not execute"))

    demo_engine.process_sync_job(job["id"])

    saved = repository.get_sync_job(job["id"])
    assert saved is not None
    assert saved["status"] == "cancelled"
    assert saved["started_at"] is None


def test_cancel_sync_job_api(client):
    resp = client.post(
        "/api/sync/jobs",
        json={"job_type": "health_check", "source": "akshare", "scope": "all", "params": {}},
    )
    job_id = resp.json()["id"]
    # Health check completes quickly via background task on TestClient
    # Cancelling a completed job should fail with 400
    cancel_resp = client.post(f"/api/sync/jobs/{job_id}/cancel")
    assert cancel_resp.status_code in (200, 400)


def test_full_sync_api(client, monkeypatch):
    # Prevent background tasks from actually running (they would retry with sleeps)
    from app.api import sync as sync_api_module
    monkeypatch.setattr(sync_api_module, "process_sync_job", lambda job_id: None)

    resp = client.post(
        "/api/sync/full",
        json={"source": "akshare", "sync_mode": "standard", "max_workers": 2},
    )
    assert resp.status_code == 200
    jobs = resp.json()
    assert len(jobs) == 4  # symbol_sync + history_sync + financial_sync + news_sync
    types = {j["job_type"] for j in jobs}
    assert types == {"symbol_sync", "history_sync", "financial_sync", "news_sync"}


def test_reset_requires_confirmation(client):
    resp = client.post("/api/sync/reset", json={"confirm": "wrong"})
    assert resp.status_code == 400


def test_truncate_by_source_preserves_shared_symbol_metadata(monkeypatch):
    statements: list[str] = []

    class _FakeCursor:
        def fetchone(self):
            return [0]

    class _FakeConnection:
        def execute(self, sql: str, params=None):
            statements.append(sql)
            return _FakeCursor()

    @contextmanager
    def _fake_market_connection():
        yield _FakeConnection()

    monkeypatch.setattr(market_store, "get_market_connection", _fake_market_connection)

    deleted = market_store.truncate_by_source("akshare")

    assert "symbol_master" not in deleted
    assert "company_profile" not in deleted
    assert not any("symbol_master" in sql for sql in statements)
    assert not any("company_profile" in sql for sql in statements)
