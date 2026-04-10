"""Smoke tests for logs and data-sources API."""
from __future__ import annotations


def test_list_logs_default(client):
    resp = client.get("/api/logs")
    assert resp.status_code == 200
    logs = resp.json()
    assert isinstance(logs, list)


def test_list_logs_by_kind(client):
    for kind in ("all", "operation", "system"):
        resp = client.get(f"/api/logs?kind={kind}")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


def test_list_logs_invalid_kind(client):
    resp = client.get("/api/logs?kind=invalid")
    assert resp.status_code == 422


def test_list_logs_by_level(client):
    resp = client.get("/api/logs?level=INFO")
    assert resp.status_code == 200


def test_get_data_sources_status(client):
    resp = client.get("/api/data-sources/status")
    assert resp.status_code == 200
    sources = resp.json()
    assert isinstance(sources, list)
    assert len(sources) == 3  # tushare, akshare, baostock

    source_names = {s["source"] for s in sources}
    assert source_names == {"tushare", "akshare", "baostock"}

    for source in sources:
        assert "enabled" in source
        assert "configured" in source
        assert "status" in source
        assert "priority" in source
        assert "supports" in source


def test_test_connection_unknown_provider(client):
    resp = client.post(
        "/api/settings/test-connection",
        json={"category": "data_source", "provider": "unknown_source"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is False


# ---------------------------------------------------------------------------
# FR-110 数据质量仪表板
# ---------------------------------------------------------------------------


def test_get_data_quality_overview(client):
    resp = client.get("/api/data-sources/quality")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_symbols" in data
    assert isinstance(data["total_symbols"], int)
    assert "tables" in data
    assert isinstance(data["tables"], list)
    assert len(data["tables"]) == 8  # 8 market tables
    assert "updated_at" in data

    for table in data["tables"]:
        assert "table_name" in table
        assert "row_count" in table
        assert "distinct_symbols" in table
        assert "sources" in table
        assert isinstance(table["sources"], list)
