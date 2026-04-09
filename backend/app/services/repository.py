from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from app.core.database import get_connection


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


def _task_from_row(row: Any) -> dict[str, Any]:
    return {
        "id": row["id"],
        "symbol": row["symbol"],
        "depth": row["depth"],
        "selected_agents": _parse_json(row["selected_agents"], []),
        "status": row["status"],
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

    with get_connection() as connection:
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
                id, symbol, depth, selected_agents, status, queue_position, warnings, created_at
            )
            VALUES (?, ?, ?, ?, 'queued', ?, '[]', ?)
            """,
            (task_id, symbol, depth, json.dumps(selected_agents, ensure_ascii=False), queue_position, created_at),
        )

    refresh_queue_positions()
    return get_task(task_id)


def update_task_status(task_id: str, status: str, warnings: list[str] | None = None) -> None:
    started_at = utc_now() if status == "running" else None
    finished_at = utc_now() if status in {"completed", "completed_with_warnings", "failed", "cancelled"} else None

    with get_connection() as connection:
        if status == "running":
            connection.execute(
                """
                UPDATE analysis_tasks
                SET status = ?, started_at = ?, queue_position = NULL
                WHERE id = ?
                """,
                (status, started_at, task_id),
            )
        elif finished_at:
            connection.execute(
                """
                UPDATE analysis_tasks
                SET status = ?, finished_at = ?, warnings = ?, queue_position = NULL
                WHERE id = ?
                """,
                (status, finished_at, json.dumps(warnings or [], ensure_ascii=False), task_id),
            )
        else:
            connection.execute(
                """
                UPDATE analysis_tasks
                SET status = ?, warnings = ?
                WHERE id = ?
                """,
                (status, json.dumps(warnings or [], ensure_ascii=False), task_id),
            )

    refresh_queue_positions()


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
