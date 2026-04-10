from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.core.market_store import init_market_store, truncate_all_tables, truncate_by_source
from app.models.schemas import SyncJob, SyncJobCreate
from app.services import repository
from app.services.demo_engine import process_sync_job
from app.services.sync_service import request_cancel, request_pause, request_resume

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sync", tags=["sync"])

_VALID_SOURCES = {"akshare", "tushare", "baostock"}
_FULL_SYNC_JOB_TYPES = ["symbol_sync", "history_sync", "financial_sync", "news_sync"]


@router.get("/jobs", response_model=list[SyncJob])
def list_sync_jobs() -> list[SyncJob]:
    return [SyncJob.model_validate(item) for item in repository.list_sync_jobs()]


@router.post("/jobs", response_model=SyncJob)
def create_sync_job(payload: SyncJobCreate, background_tasks: BackgroundTasks) -> SyncJob:
    job = repository.create_sync_job(payload.job_type, payload.source, payload.scope, payload.params)
    repository.add_operation_log("sync", "create", "INFO", f"{payload.source} {payload.job_type} 已入队。", job["id"])
    background_tasks.add_task(process_sync_job, job["id"])
    return SyncJob.model_validate(job)


# ---------------------------------------------------------------------------
# Cancel / Pause / Resume
# ---------------------------------------------------------------------------


@router.post("/jobs/{job_id}/cancel")
def cancel_sync_job(job_id: str) -> dict[str, str]:
    job = repository.get_sync_job(job_id)
    if not job:
        raise HTTPException(404, "任务不存在。")
    if job["status"] not in ("queued", "running"):
        raise HTTPException(400, f"任务状态为 {job['status']}，无法取消。")

    if job["status"] == "running":
        if not request_cancel(job_id):
            # Worker might have already finished; just mark cancelled
            pass
    repository.update_sync_job(job_id, "cancelled", result_summary="用户手动取消。")
    repository.add_operation_log("sync", "cancel", "INFO", f"同步任务 {job_id} 已被用户取消。", job_id)
    return {"status": "cancelled"}


@router.post("/jobs/{job_id}/pause")
def pause_sync_job(job_id: str) -> dict[str, str]:
    job = repository.get_sync_job(job_id)
    if not job:
        raise HTTPException(404, "任务不存在。")
    if job["status"] != "running":
        raise HTTPException(400, "只能暂停运行中的任务。")

    request_pause(job_id)
    return {"status": "paused"}


@router.post("/jobs/{job_id}/resume")
def resume_sync_job(job_id: str) -> dict[str, str]:
    job = repository.get_sync_job(job_id)
    if not job:
        raise HTTPException(404, "任务不存在。")
    if job["status"] != "running":
        raise HTTPException(400, "只能恢复运行中的任务。")

    request_resume(job_id)
    return {"status": "resumed"}


# ---------------------------------------------------------------------------
# Full sync — create a chain of sync jobs
# ---------------------------------------------------------------------------


@router.post("/full", response_model=list[SyncJob])
def create_full_sync(
    payload: dict[str, Any],
    background_tasks: BackgroundTasks,
) -> list[SyncJob]:
    """Create a full sync pipeline: symbol_sync → history_sync → financial_sync → news_sync."""
    source = payload.get("source", "")
    if source not in _VALID_SOURCES:
        raise HTTPException(400, f"无效的数据源: {source}")

    sync_mode = payload.get("sync_mode", "standard")
    max_workers = payload.get("max_workers", 3)

    created: list[SyncJob] = []
    for job_type in _FULL_SYNC_JOB_TYPES:
        job = repository.create_sync_job(
            job_type, source, "all",
            {"sync_mode": sync_mode, "max_workers": max_workers},
        )
        repository.add_operation_log(
            "sync", "full_sync", "INFO",
            f"全量同步：创建 {source}/{job_type} 任务（{sync_mode}模式）。",
            job["id"],
        )
        background_tasks.add_task(process_sync_job, job["id"])
        created.append(SyncJob.model_validate(job))

    return created


# ---------------------------------------------------------------------------
# Reset / Clear data
# ---------------------------------------------------------------------------


@router.post("/reset")
def reset_all_data(payload: dict[str, Any]) -> dict[str, Any]:
    """Clear ALL market data. Requires confirmation token."""
    confirm = payload.get("confirm", "")
    if confirm != "CONFIRM":
        raise HTTPException(400, "请输入 CONFIRM 以确认清空所有数据。")

    if not init_market_store():
        raise HTTPException(500, "DuckDB 不可用。")

    deleted = truncate_all_tables()
    jobs_deleted = repository.delete_all_sync_jobs()

    total = sum(deleted.values())
    repository.add_operation_log(
        "sync", "reset", "WARN",
        f"用户已清空所有市场数据，共删除 {total} 条数据记录和 {jobs_deleted} 条同步任务记录。",
    )
    return {"deleted_data": deleted, "deleted_jobs": jobs_deleted, "total_records": total}


@router.post("/reset/{source}")
def reset_source_data(source: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Clear all data for a specific source."""
    if source not in _VALID_SOURCES:
        raise HTTPException(400, f"无效的数据源: {source}")

    confirm = payload.get("confirm", "")
    if confirm != "CONFIRM":
        raise HTTPException(400, "请输入 CONFIRM 以确认清空数据。")

    if not init_market_store():
        raise HTTPException(500, "DuckDB 不可用。")

    deleted = truncate_by_source(source)
    total = sum(deleted.values())
    repository.add_operation_log(
        "sync", "reset_source", "WARN",
        f"用户已清空 {source} 数据源的所有数据，共删除 {total} 条记录。",
    )
    return {"source": source, "deleted": deleted, "total_records": total}


# ---------------------------------------------------------------------------
# SSE progress stream
# ---------------------------------------------------------------------------


@router.get("/progress/stream")
async def sync_progress_stream(
    job_ids: str = Query("", description="Comma-separated job IDs to watch. Empty = all running."),
) -> StreamingResponse:
    """Server-Sent Events stream for sync job progress."""
    target_ids = [jid.strip() for jid in job_ids.split(",") if jid.strip()] if job_ids else []

    async def event_generator():
        try:
            while True:
                jobs = repository.list_sync_jobs(limit=50)
                active = [
                    j for j in jobs
                    if j["status"] in ("queued", "running")
                    and (not target_ids or j["id"] in target_ids)
                ]

                for job in active:
                    event_data = {
                        "id": job["id"],
                        "job_type": job["job_type"],
                        "source": job["source"],
                        "status": job["status"],
                        "total_items": job.get("total_items", 0),
                        "completed_items": job.get("completed_items", 0),
                        "error_items": job.get("error_items", 0),
                        "skipped_items": job.get("skipped_items", 0),
                        "current_item": job.get("current_item"),
                        "result_summary": job.get("result_summary"),
                    }
                    yield f"data: {json.dumps(event_data, ensure_ascii=False)}\n\n"

                if not active and target_ids:
                    # All target jobs are done — send final state and close
                    for job in jobs:
                        if job["id"] in target_ids:
                            event_data = {
                                "id": job["id"],
                                "status": job["status"],
                                "result_summary": job.get("result_summary"),
                                "finished": True,
                            }
                            yield f"data: {json.dumps(event_data, ensure_ascii=False)}\n\n"
                    break

                await asyncio.sleep(1.5)
        except asyncio.CancelledError:
            pass

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
