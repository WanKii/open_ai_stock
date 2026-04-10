"""Unit tests for repository layer (SQLite operations)."""
from __future__ import annotations

from app.services import repository


def test_create_and_get_task():
    task = repository.create_task("600519.SH", "fast", ["market_analyst"])
    assert task["symbol"] == "600519.SH"
    assert task["depth"] == "fast"
    assert task["status"] == "queued"
    assert task["queue_position"] is not None
    assert task["progress"]["total_agents"] == 1
    assert task["progress"]["completed_agents"] == 0
    assert task["progress"]["current_step"] == "等待执行"
    assert task["progress"]["agent_states"][0]["agent_type"] == "market_analyst"
    assert task["progress"]["agent_states"][0]["status"] == "pending"

    fetched = repository.get_task(task["id"])
    assert fetched is not None
    assert fetched["id"] == task["id"]
    assert fetched["progress"]["agent_states"][0]["status"] == "pending"


def test_update_task_status():
    task = repository.create_task("000001.SZ", "standard", ["news_analyst"])
    repository.update_task_status(task["id"], "running")
    updated = repository.get_task(task["id"])
    assert updated["status"] == "running"
    assert updated["started_at"] is not None
    assert updated["queue_position"] is None

    repository.update_task_status(task["id"], "completed")
    completed = repository.get_task(task["id"])
    assert completed["status"] == "completed"
    assert completed["finished_at"] is not None


def test_update_task_progress():
    task = repository.create_task(
        "300750.SZ",
        "standard",
        ["market_analyst", "news_analyst"],
    )

    repository.update_task_progress(
        task["id"],
        current_step="市场分析师执行中",
        current_agent_types=["market_analyst"],
        agent_updates={
            "market_analyst": {
                "status": "running",
                "started_at": repository.utc_now(),
            }
        },
    )

    updated = repository.get_task(task["id"])
    assert updated["progress"]["current_step"] == "市场分析师执行中"
    assert updated["progress"]["current_agent_types"] == ["market_analyst"]
    assert updated["progress"]["agent_states"][0]["status"] == "running"
    assert updated["progress"]["agent_states"][0]["started_at"] is not None


def test_save_and_get_report():
    task = repository.create_task("300750.SZ", "deep", ["sector_analyst"])
    report = {"task_id": task["id"], "overall_score": 75, "action_tag": "关注"}
    repository.save_report(task["id"], report)
    fetched = repository.get_report(task["id"])
    assert fetched is not None
    assert fetched["overall_score"] == 75


def test_get_report_nonexistent():
    result = repository.get_report("nonexistent-id")
    assert result is None


def test_list_tasks():
    tasks = repository.list_tasks()
    assert isinstance(tasks, list)


def test_prompt_snapshots():
    task = repository.create_task("601318.SH", "fast", ["market_analyst"])
    prompts = {"market_analyst": "test prompt", "final_summarizer": "summary prompt"}
    repository.save_prompt_snapshots(task["id"], prompts)
    snapshots = repository.list_prompt_snapshots(task["id"])
    assert len(snapshots) == 2
    keys = {s["prompt_key"] for s in snapshots}
    assert keys == {"market_analyst", "final_summarizer"}


def test_operation_log():
    repository.add_operation_log("test", "create", "INFO", "Test log entry")
    logs = repository.list_logs(kind="operation")
    assert any(log["message"] == "Test log entry" for log in logs)


def test_system_log():
    repository.add_system_log("test", "ERROR", "System test error")
    logs = repository.list_logs(kind="system")
    assert any(log["message"] == "System test error" for log in logs)


def test_sync_job_lifecycle():
    job = repository.create_sync_job("health_check", "akshare", "all", {})
    assert job["status"] == "queued"

    repository.update_sync_job(job["id"], "running")
    running = repository.get_sync_job(job["id"])
    assert running["status"] == "running"

    repository.update_sync_job(job["id"], "completed", result_summary="OK")
    done = repository.get_sync_job(job["id"])
    assert done["status"] == "completed"
    assert done["result_summary"] == "OK"


def test_list_sync_jobs():
    jobs = repository.list_sync_jobs()
    assert isinstance(jobs, list)
