from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timezone
from typing import Any

from app.core.database import get_connection

AGENT_RUNNING_STATES = {"running"}
AGENT_FINISHED_STATES = {"completed", "failed"}

_ANALYSIS_TASK_LOCK = threading.Lock()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_json(value: str | None, fallback: Any) -> Any:
    if not value:
        return fallback
    return json.loads(value)


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


def _build_initial_task_progress(selected_agents: list[str]) -> dict[str, Any]:
    now = utc_now()
    return {
        "phase": "queued",
        "current_step": "等待执行",
        "total_agents": len(selected_agents),
        "completed_agents": 0,
        "current_agent_types": [],
        "agent_states": [
            {
                "agent_type": agent_type,
                "status": "pending",
                "summary": None,
                "started_at": None,
                "finished_at": None,
                "updated_at": now,
            }
            for agent_type in selected_agents
        ],
        "updated_at": now,
    }


def _normalize_task_progress(progress: dict[str, Any], selected_agents: list[str]) -> dict[str, Any]:
    if not progress:
        progress = _build_initial_task_progress(selected_agents)

    updated_at = _parse_datetime(progress.get("updated_at")) or datetime.now(timezone.utc)
    states_by_type: dict[str, dict[str, Any]] = {}
    for raw_state in progress.get("agent_states", []):
        agent_type = raw_state.get("agent_type")
        if not agent_type:
            continue
        states_by_type[agent_type] = {
            "agent_type": agent_type,
            "status": raw_state.get("status", "pending"),
            "summary": raw_state.get("summary"),
            "started_at": _parse_datetime(raw_state.get("started_at")),
            "finished_at": _parse_datetime(raw_state.get("finished_at")),
            "updated_at": _parse_datetime(raw_state.get("updated_at")) or updated_at,
        }

    agent_states = []
    for agent_type in selected_agents:
        agent_states.append(
            states_by_type.get(
                agent_type,
                {
                    "agent_type": agent_type,
                    "status": "pending",
                    "summary": None,
                    "started_at": None,
                    "finished_at": None,
                    "updated_at": updated_at,
                },
            )
        )

    completed_agents = sum(1 for state in agent_states if state["status"] in AGENT_FINISHED_STATES)
    valid_agent_types = {state["agent_type"] for state in agent_states}

    return {
        "phase": progress.get("phase", "queued"),
        "current_step": progress.get("current_step", "等待执行"),
        "total_agents": len(agent_states),
        "completed_agents": completed_agents,
        "current_agent_types": [
            agent_type for agent_type in progress.get("current_agent_types", []) if agent_type in valid_agent_types
        ],
        "agent_states": agent_states,
        "updated_at": updated_at,
    }


def _serialize_task_progress(progress: dict[str, Any]) -> str:
    return json.dumps(
        progress,
        ensure_ascii=False,
        default=lambda value: value.isoformat() if isinstance(value, datetime) else value,
    )


def _task_from_row(row: Any) -> dict[str, Any]:
    selected_agents = _parse_json(row["selected_agents"], [])
    return {
        "id": row["id"],
        "symbol": row["symbol"],
        "depth": row["depth"],
        "selected_agents": selected_agents,
        "status": row["status"],
        "progress": _normalize_task_progress(_parse_json(row["progress_json"] if "progress_json" in row.keys() else None, {}), selected_agents),
        "queue_position": row["queue_position"],
        "warnings": _parse_json(row["warnings"], []),
        "created_at": _parse_datetime(row["created_at"]),
        "started_at": _parse_datetime(row["started_at"]),
        "finished_at": _parse_datetime(row["finished_at"]),
    }


def _sync_job_from_row(row: Any) -> dict[str, Any]:
    return {
        "id": row["id"],
        "job_type": row["job_type"],
        "source": row["source"],
        "scope": row["scope"],
        "params": _parse_json(row["params_json"], {}),
        "status": row["status"],
        "result_summary": row["result_summary"],
        "total_items": row["total_items"] if "total_items" in row.keys() else 0,
        "completed_items": row["completed_items"] if "completed_items" in row.keys() else 0,
        "error_items": row["error_items"] if "error_items" in row.keys() else 0,
        "skipped_items": row["skipped_items"] if "skipped_items" in row.keys() else 0,
        "current_item": row["current_item"] if "current_item" in row.keys() else None,
        "created_at": _parse_datetime(row["created_at"]),
        "started_at": _parse_datetime(row["started_at"]),
        "finished_at": _parse_datetime(row["finished_at"]),
    }


def refresh_queue_positions() -> None:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id
            FROM analysis_tasks
            WHERE status = 'queued'
            ORDER BY created_at ASC
            """
        ).fetchall()

        for index, row in enumerate(rows, start=1):
            connection.execute(
                "UPDATE analysis_tasks SET queue_position = ? WHERE id = ?",
                (index, row["id"]),
            )


def list_tasks(limit: int = 50) -> list[dict[str, Any]]:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT *
            FROM analysis_tasks
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    return [_task_from_row(row) for row in rows]


def get_task(task_id: str) -> dict[str, Any] | None:
    with get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM analysis_tasks WHERE id = ?",
            (task_id,),
        ).fetchone()

    return _task_from_row(row) if row else None


def create_task(symbol: str, depth: str, selected_agents: list[str]) -> dict[str, Any]:
    task_id = str(uuid.uuid4())
    created_at = utc_now()
    progress = _build_initial_task_progress(selected_agents)

    with get_connection() as connection:
        connection.execute("BEGIN IMMEDIATE")
        queue_position = (
            connection.execute(
                """
                SELECT COUNT(*)
                FROM analysis_tasks
                WHERE status IN ('queued', 'running')
                """
            ).fetchone()[0]
            + 1
        )
        connection.execute(
            """
            INSERT INTO analysis_tasks (
                id, symbol, depth, selected_agents, status, progress_json, queue_position, warnings, created_at
            )
            VALUES (?, ?, ?, ?, 'queued', ?, ?, '[]', ?)
            """,
            (
                task_id,
                symbol,
                depth,
                json.dumps(selected_agents, ensure_ascii=False),
                _serialize_task_progress(progress),
                queue_position,
                created_at,
            ),
        )
        connection.execute("COMMIT")

    refresh_queue_positions()
    return get_task(task_id)


def update_task_status(task_id: str, status: str, warnings: list[str] | None = None) -> None:
    started_at = utc_now() if status == "running" else None
    finished_at = utc_now() if status in {"completed", "completed_with_warnings", "failed", "cancelled"} else None

    with _ANALYSIS_TASK_LOCK:
        task = get_task(task_id)
        if task is None:
            return

        progress = task["progress"]
        progress["updated_at"] = datetime.now(timezone.utc)

        if status == "running":
            progress["phase"] = "running"
            if progress["current_step"] == "等待执行":
                progress["current_step"] = "任务执行中"
        elif status == "completed":
            progress["phase"] = "completed"
            progress["current_step"] = "分析完成"
            progress["current_agent_types"] = []
        elif status == "completed_with_warnings":
            progress["phase"] = "completed"
            progress["current_step"] = "分析完成（有警告）"
            progress["current_agent_types"] = []
        elif status == "failed":
            progress["phase"] = "failed"
            progress["current_step"] = "分析失败"
            progress["current_agent_types"] = []
        elif status == "cancelled":
            progress["phase"] = "cancelled"
            progress["current_step"] = "任务已取消"
            progress["current_agent_types"] = []

        with get_connection() as connection:
            if status == "running":
                connection.execute(
                    """
                    UPDATE analysis_tasks
                    SET status = ?, started_at = ?, progress_json = ?, queue_position = NULL
                    WHERE id = ?
                    """,
                    (status, started_at, _serialize_task_progress(progress), task_id),
                )
            elif finished_at:
                connection.execute(
                    """
                    UPDATE analysis_tasks
                    SET status = ?, finished_at = ?, warnings = ?, progress_json = ?, queue_position = NULL
                    WHERE id = ?
                    """,
                    (
                        status,
                        finished_at,
                        json.dumps(warnings or [], ensure_ascii=False),
                        _serialize_task_progress(progress),
                        task_id,
                    ),
                )
            else:
                connection.execute(
                    """
                    UPDATE analysis_tasks
                    SET status = ?, warnings = ?, progress_json = ?
                    WHERE id = ?
                    """,
                    (
                        status,
                        json.dumps(warnings or [], ensure_ascii=False),
                        _serialize_task_progress(progress),
                        task_id,
                    ),
                )

    refresh_queue_positions()


def update_task_progress(
    task_id: str,
    *,
    phase: str | None = None,
    current_step: str | None = None,
    current_agent_types: list[str] | None = None,
    agent_updates: dict[str, dict[str, Any]] | None = None,
) -> None:
    with _ANALYSIS_TASK_LOCK:
        task = get_task(task_id)
        if task is None:
            return

        progress = task["progress"]
        states_by_type = {state["agent_type"]: state for state in progress["agent_states"]}

        if phase is not None:
            progress["phase"] = phase
        if current_step is not None:
            progress["current_step"] = current_step
        if current_agent_types is not None:
            progress["current_agent_types"] = current_agent_types

        now = datetime.now(timezone.utc)
        if agent_updates:
            for agent_type, updates in agent_updates.items():
                state = states_by_type.get(agent_type)
                if state is None:
                    state = {
                        "agent_type": agent_type,
                        "status": "pending",
                        "summary": None,
                        "started_at": None,
                        "finished_at": None,
                        "updated_at": now,
                    }
                    progress["agent_states"].append(state)
                    states_by_type[agent_type] = state
                for key, value in updates.items():
                    state[key] = value
                state["updated_at"] = now

        progress["completed_agents"] = sum(
            1 for state in progress["agent_states"] if state["status"] in AGENT_FINISHED_STATES
        )
        progress["updated_at"] = now

        with get_connection() as connection:
            connection.execute(
                "UPDATE analysis_tasks SET progress_json = ? WHERE id = ?",
                (_serialize_task_progress(progress), task_id),
            )


def mark_task_agents_running(task_id: str, agent_types: list[str]) -> None:
    if not agent_types:
        return

    with _ANALYSIS_TASK_LOCK:
        task = get_task(task_id)
        if task is None:
            return

        progress = task["progress"]
        states_by_type = {state["agent_type"]: state for state in progress["agent_states"]}
        now = datetime.now(timezone.utc)

        for agent_type in agent_types:
            state = states_by_type.get(agent_type)
            if state is None:
                state = {
                    "agent_type": agent_type,
                    "status": "pending",
                    "summary": None,
                    "started_at": None,
                    "finished_at": None,
                    "updated_at": now,
                }
                progress["agent_states"].append(state)
                states_by_type[agent_type] = state
            state["status"] = "running"
            state["started_at"] = state.get("started_at") or now
            state["updated_at"] = now

        progress["phase"] = "running_agents"
        progress["current_step"] = "正在执行 Agent 分析"
        progress["current_agent_types"] = [
            state["agent_type"] for state in progress["agent_states"] if state["status"] in AGENT_RUNNING_STATES
        ]
        progress["completed_agents"] = sum(
            1 for state in progress["agent_states"] if state["status"] in AGENT_FINISHED_STATES
        )
        progress["updated_at"] = now

        with get_connection() as connection:
            connection.execute(
                "UPDATE analysis_tasks SET progress_json = ? WHERE id = ?",
                (_serialize_task_progress(progress), task_id),
            )


def mark_task_agent_finished(task_id: str, agent_type: str, status: str, summary: str | None = None) -> None:
    with _ANALYSIS_TASK_LOCK:
        task = get_task(task_id)
        if task is None:
            return

        progress = task["progress"]
        now = datetime.now(timezone.utc)
        states_by_type = {state["agent_type"]: state for state in progress["agent_states"]}
        state = states_by_type.get(agent_type)
        if state is None:
            state = {
                "agent_type": agent_type,
                "status": status,
                "summary": summary,
                "started_at": None,
                "finished_at": now,
                "updated_at": now,
            }
            progress["agent_states"].append(state)
        else:
            state["status"] = status
            state["summary"] = summary
            state["finished_at"] = now
            state["updated_at"] = now

        progress["current_agent_types"] = [
            item["agent_type"]
            for item in progress["agent_states"]
            if item["status"] in AGENT_RUNNING_STATES
        ]
        progress["completed_agents"] = sum(
            1 for item in progress["agent_states"] if item["status"] in AGENT_FINISHED_STATES
        )
        progress["phase"] = "summarizing" if not progress["current_agent_types"] else "running_agents"
        progress["current_step"] = "正在汇总结论" if progress["phase"] == "summarizing" else "正在执行 Agent 分析"
        progress["updated_at"] = now

        with get_connection() as connection:
            connection.execute(
                "UPDATE analysis_tasks SET progress_json = ? WHERE id = ?",
                (_serialize_task_progress(progress), task_id),
            )


def save_report(task_id: str, report: dict[str, Any]) -> None:
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO analysis_reports (task_id, report_json, created_at)
            VALUES (?, ?, ?)
            ON CONFLICT(task_id) DO UPDATE SET report_json = excluded.report_json, created_at = excluded.created_at
            """,
            (task_id, json.dumps(report, ensure_ascii=False), utc_now()),
        )


def get_report(task_id: str) -> dict[str, Any] | None:
    with get_connection() as connection:
        row = connection.execute(
            "SELECT report_json FROM analysis_reports WHERE task_id = ?",
            (task_id,),
        ).fetchone()

    return json.loads(row["report_json"]) if row else None


def save_prompt_snapshots(task_id: str, prompts: dict[str, str]) -> None:
    created_at = utc_now()
    with get_connection() as connection:
        for prompt_key, prompt_body in prompts.items():
            connection.execute(
                """
                INSERT INTO prompt_snapshots (id, task_id, prompt_key, prompt_body, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (str(uuid.uuid4()), task_id, prompt_key, prompt_body, created_at),
            )


def list_prompt_snapshots(task_id: str) -> list[dict[str, Any]]:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, prompt_key, prompt_body, created_at
            FROM prompt_snapshots
            WHERE task_id = ?
            ORDER BY created_at ASC
            """,
            (task_id,),
        ).fetchall()

    return [
        {
            "id": row["id"],
            "prompt_key": row["prompt_key"],
            "prompt_body": row["prompt_body"],
            "created_at": _parse_datetime(row["created_at"]),
        }
        for row in rows
    ]


def add_operation_log(module: str, action: str, level: str, message: str, task_id: str | None = None) -> None:
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO operation_logs (module, action, level, message, task_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (module, action, level, message, task_id, utc_now()),
        )


def add_system_log(module: str, level: str, message: str, task_id: str | None = None) -> None:
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO system_logs (module, level, message, task_id, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (module, level, message, task_id, utc_now()),
        )


def list_logs(kind: str = "all", task_id: str | None = None, level: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    if kind not in ("all", "operation", "system"):
        raise ValueError(f"无效的日志类型：{kind}")

    clauses: list[str] = []
    params: list[Any] = []

    if task_id:
        clauses.append("task_id = ?")
        params.append(task_id)
    if level:
        clauses.append("level = ?")
        params.append(level)

    where_clause = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    with get_connection() as connection:
        if kind == "all":
            operation_rows = connection.execute(
                f"""
                SELECT id, module, action, level, message, task_id, created_at
                FROM operation_logs
                {where_clause}
                ORDER BY created_at DESC
                LIMIT ?
                """,
                [*params, limit],
            ).fetchall()
            system_rows = connection.execute(
                f"""
                SELECT id, module, NULL AS action, level, message, task_id, created_at
                FROM system_logs
                {where_clause}
                ORDER BY created_at DESC
                LIMIT ?
                """,
                [*params, limit],
            ).fetchall()
            rows = sorted(
                [*operation_rows, *system_rows],
                key=lambda row: row["created_at"],
                reverse=True,
            )[:limit]
        else:
            table_name = "operation_logs" if kind == "operation" else "system_logs"
            action_column = "action" if kind == "operation" else "NULL AS action"
            rows = connection.execute(
                f"""
                SELECT id, module, {action_column}, level, message, task_id, created_at
                FROM {table_name}
                {where_clause}
                ORDER BY created_at DESC
                LIMIT ?
                """,
                [*params, limit],
            ).fetchall()

    return [
        {
            "id": row["id"],
            "module": row["module"],
            "action": row["action"],
            "level": row["level"],
            "message": row["message"],
            "task_id": row["task_id"],
            "created_at": _parse_datetime(row["created_at"]),
        }
        for row in rows
    ]


def create_sync_job(job_type: str, source: str, scope: str, params: dict[str, Any]) -> dict[str, Any]:
    job_id = str(uuid.uuid4())
    created_at = utc_now()

    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO sync_jobs (id, job_type, source, scope, params_json, status, created_at)
            VALUES (?, ?, ?, ?, ?, 'queued', ?)
            """,
            (job_id, job_type, source, scope, json.dumps(params, ensure_ascii=False), created_at),
        )

    return get_sync_job(job_id)


def get_sync_job(job_id: str) -> dict[str, Any] | None:
    with get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM sync_jobs WHERE id = ?",
            (job_id,),
        ).fetchone()

    return _sync_job_from_row(row) if row else None


def list_sync_jobs(limit: int = 50) -> list[dict[str, Any]]:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT *
            FROM sync_jobs
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    return [_sync_job_from_row(row) for row in rows]


def update_sync_job(job_id: str, status: str, result_summary: str | None = None) -> None:
    started_at = utc_now() if status == "running" else None
    finished_at = utc_now() if status in {"completed", "completed_with_warnings", "failed", "cancelled"} else None

    with get_connection() as connection:
        if status == "running":
            connection.execute(
                """
                UPDATE sync_jobs
                SET status = ?, started_at = ?
                WHERE id = ?
                """,
                (status, started_at, job_id),
            )
        else:
            connection.execute(
                """
                UPDATE sync_jobs
                SET status = ?, finished_at = ?, result_summary = ?
                WHERE id = ?
                """,
                (status, finished_at, result_summary, job_id),
            )


def update_sync_job_progress(
    job_id: str,
    *,
    total_items: int | None = None,
    completed_items: int | None = None,
    error_items: int | None = None,
    skipped_items: int | None = None,
    current_item: str | None = None,
) -> None:
    """Update progress fields on a running sync job."""
    sets: list[str] = []
    params: list[Any] = []
    if total_items is not None:
        sets.append("total_items = ?")
        params.append(total_items)
    if completed_items is not None:
        sets.append("completed_items = ?")
        params.append(completed_items)
    if error_items is not None:
        sets.append("error_items = ?")
        params.append(error_items)
    if skipped_items is not None:
        sets.append("skipped_items = ?")
        params.append(skipped_items)
    if current_item is not None:
        sets.append("current_item = ?")
        params.append(current_item)
    if not sets:
        return
    params.append(job_id)
    sql = f"UPDATE sync_jobs SET {', '.join(sets)} WHERE id = ?"
    with get_connection() as connection:
        connection.execute(sql, params)


def delete_all_sync_jobs() -> int:
    """Delete all sync job records. Returns deleted count."""
    with get_connection() as connection:
        count = connection.execute("SELECT COUNT(*) FROM sync_jobs").fetchone()[0]
        connection.execute("DELETE FROM sync_jobs")
    return count
