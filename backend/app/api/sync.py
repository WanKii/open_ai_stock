from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks

from app.models.schemas import SyncJob, SyncJobCreate
from app.services import repository
from app.services.demo_engine import process_sync_job


router = APIRouter(prefix="/api/sync", tags=["sync"])


@router.get("/jobs", response_model=list[SyncJob])
def list_sync_jobs() -> list[SyncJob]:
    return [SyncJob.model_validate(item) for item in repository.list_sync_jobs()]


@router.post("/jobs", response_model=SyncJob)
def create_sync_job(payload: SyncJobCreate, background_tasks: BackgroundTasks) -> SyncJob:
    job = repository.create_sync_job(payload.job_type, payload.source, payload.scope, payload.params)
    repository.add_operation_log("sync", "create", "INFO", f"{payload.source} {payload.job_type} 已入队。", job["id"])
    background_tasks.add_task(process_sync_job, job["id"])
    return SyncJob.model_validate(job)
