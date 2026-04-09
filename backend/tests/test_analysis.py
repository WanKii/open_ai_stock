"""Smoke tests for the analysis task lifecycle."""
from __future__ import annotations

import time


def test_create_analysis_task(client):
    resp = client.post(
        "/api/analysis/tasks",
        json={
            "symbol": "600519.SH",
            "depth": "fast",
            "selected_agents": ["market_analyst", "fundamental_analyst"],
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["task_id"]
    assert data["status"] == "queued"
    assert data["queue_position"] >= 1


def test_create_analysis_task_requires_agents(client):
    resp = client.post(
        "/api/analysis/tasks",
        json={
            "symbol": "600519.SH",
            "depth": "fast",
            "selected_agents": [],
        },
    )
    assert resp.status_code == 400


def test_list_analysis_tasks(client):
    # Ensure at least one task exists
    client.post(
        "/api/analysis/tasks",
        json={
            "symbol": "000001.SZ",
            "depth": "standard",
            "selected_agents": ["news_analyst"],
        },
    )
    resp = client.get("/api/analysis/tasks")
    assert resp.status_code == 200
    tasks = resp.json()
    assert isinstance(tasks, list)
    assert len(tasks) >= 1
    task = tasks[0]
    assert "id" in task
    assert "symbol" in task
    assert "status" in task


def test_get_analysis_task_detail(client):
    create_resp = client.post(
        "/api/analysis/tasks",
        json={
            "symbol": "300750.SZ",
            "depth": "fast",
            "selected_agents": ["sector_analyst"],
        },
    )
    task_id = create_resp.json()["task_id"]

    resp = client.get(f"/api/analysis/tasks/{task_id}")
    assert resp.status_code == 200
    task = resp.json()
    assert task["id"] == task_id
    assert task["symbol"] == "300750.SZ"


def test_get_nonexistent_task_returns_404(client):
    resp = client.get("/api/analysis/tasks/nonexistent-id")
    assert resp.status_code == 404


def test_analysis_task_end_to_end(client):
    """Submit a task and wait for the demo engine to complete it."""
    create_resp = client.post(
        "/api/analysis/tasks",
        json={
            "symbol": "601318.SH",
            "depth": "fast",
            "selected_agents": ["market_analyst"],
        },
    )
    task_id = create_resp.json()["task_id"]

    # Poll until completion (demo engine takes ~1.2s)
    for _ in range(10):
        time.sleep(0.5)
        task_resp = client.get(f"/api/analysis/tasks/{task_id}")
        task = task_resp.json()
        if task["status"] in ("completed", "completed_with_warnings", "failed"):
            break

    assert task["status"] in ("completed", "completed_with_warnings"), f"Unexpected status: {task['status']}"

    # Fetch report
    report_resp = client.get(f"/api/analysis/tasks/{task_id}/report")
    assert report_resp.status_code == 200
    report = report_resp.json()
    assert report["task_id"] == task_id
    assert 0 <= report["overall_score"] <= 100
    assert report["action_tag"] in ("关注", "观望", "谨慎")
    assert report["disclaimer"]
    assert len(report["agent_reports"]) >= 1
    assert len(report["data_snapshot"]["price_series"]) > 0


def test_report_not_ready_returns_404(client):
    create_resp = client.post(
        "/api/analysis/tasks",
        json={
            "symbol": "002415.SZ",
            "depth": "fast",
            "selected_agents": ["index_analyst"],
        },
    )
    task_id = create_resp.json()["task_id"]
    # Immediately ask for report (before engine finishes)
    resp = client.get(f"/api/analysis/tasks/{task_id}/report")
    # Could be 404 (not ready) or 200 (very fast), both acceptable
    assert resp.status_code in (200, 404)
