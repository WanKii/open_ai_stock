from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import Iterator

from .config import SQLITE_PATH, ensure_project_dirs


def init_db() -> None:
    ensure_project_dirs()
    with sqlite3.connect(SQLITE_PATH) as connection:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS analysis_tasks (
                id TEXT PRIMARY KEY,
                symbol TEXT NOT NULL,
                depth TEXT NOT NULL,
                selected_agents TEXT NOT NULL,
                status TEXT NOT NULL,
                queue_position INTEGER,
                warnings TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL,
                started_at TEXT,
                finished_at TEXT
            );

            CREATE TABLE IF NOT EXISTS analysis_reports (
                task_id TEXT PRIMARY KEY,
                report_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(task_id) REFERENCES analysis_tasks(id)
            );

            CREATE TABLE IF NOT EXISTS prompt_snapshots (
                id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                prompt_key TEXT NOT NULL,
                prompt_body TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(task_id) REFERENCES analysis_tasks(id)
            );

            CREATE TABLE IF NOT EXISTS sync_jobs (
                id TEXT PRIMARY KEY,
                job_type TEXT NOT NULL,
                source TEXT NOT NULL,
                scope TEXT NOT NULL,
                params_json TEXT NOT NULL,
                status TEXT NOT NULL,
                result_summary TEXT,
                total_items INTEGER NOT NULL DEFAULT 0,
                completed_items INTEGER NOT NULL DEFAULT 0,
                error_items INTEGER NOT NULL DEFAULT 0,
                skipped_items INTEGER NOT NULL DEFAULT 0,
                current_item TEXT,
                created_at TEXT NOT NULL,
                started_at TEXT,
                finished_at TEXT
            );

            CREATE TABLE IF NOT EXISTS operation_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                module TEXT NOT NULL,
                action TEXT NOT NULL,
                level TEXT NOT NULL,
                message TEXT NOT NULL,
                task_id TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS system_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                module TEXT NOT NULL,
                level TEXT NOT NULL,
                message TEXT NOT NULL,
                task_id TEXT,
                created_at TEXT NOT NULL
            );
            """
        )
        # Migrate: add progress columns if missing (for existing databases)
        existing = {row[1] for row in connection.execute("PRAGMA table_info(sync_jobs)").fetchall()}
        migrations = [
            ("total_items", "INTEGER NOT NULL DEFAULT 0"),
            ("completed_items", "INTEGER NOT NULL DEFAULT 0"),
            ("error_items", "INTEGER NOT NULL DEFAULT 0"),
            ("skipped_items", "INTEGER NOT NULL DEFAULT 0"),
            ("current_item", "TEXT"),
        ]
        for col_name, col_type in migrations:
            if col_name not in existing:
                connection.execute(f"ALTER TABLE sync_jobs ADD COLUMN {col_name} {col_type}")


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(SQLITE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()
