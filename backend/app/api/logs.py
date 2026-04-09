from __future__ import annotations

from fastapi import APIRouter, Query

from app.models.schemas import LogEntry
from app.services import repository


router = APIRouter(prefix="/api/logs", tags=["logs"])


@router.get("", response_model=list[LogEntry])
def list_logs(
    kind: str = Query(default="all", pattern="^(all|operation|system)$"),
    task_id: str | None = None,
    level: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[LogEntry]:
    return [LogEntry.model_validate(item) for item in repository.list_logs(kind=kind, task_id=task_id, level=level, limit=limit)]
