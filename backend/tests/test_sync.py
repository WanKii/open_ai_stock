"""Smoke tests for sync jobs API."""
from __future__ import annotations

import time


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


def test_list_sync_jobs(client):
    # Ensure at least one job exists
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
    """Create a health_check sync job and wait for completion."""
    create_resp = client.post(
        "/api/sync/jobs",
        json={"job_type": "health_check", "source": "akshare", "scope": "all", "params": {}},
    )
    job_id = create_resp.json()["id"]

    # Poll sync job status via the list endpoint
    for _ in range(12):
        time.sleep(0.5)
        jobs_resp = client.get("/api/sync/jobs")
        jobs = jobs_resp.json()
        job = next((j for j in jobs if j["id"] == job_id), None)
        if job and job["status"] in ("completed", "completed_with_warnings", "failed"):
            break

    assert job is not None
    assert job["status"] in ("completed", "completed_with_warnings", "failed")
