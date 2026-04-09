from __future__ import annotations

from fastapi import APIRouter

from app.core.config import load_settings
from app.models.schemas import DataSourceStatus
from app.services.sync_service import describe_source_status


router = APIRouter(prefix="/api/data-sources", tags=["data-sources"])


@router.get("/status", response_model=list[DataSourceStatus])
def get_source_status() -> list[DataSourceStatus]:
    settings = load_settings()
    statuses: list[DataSourceStatus] = []

    for source_name, config in settings["data_sources"].items():
        runtime_status = describe_source_status(source_name, config)
        statuses.append(
            DataSourceStatus(
                source=source_name,
                enabled=bool(config.get("enabled")),
                configured=runtime_status.configured,
                priority=config["priority"],
                supports=config["supports"],
                status=runtime_status.status,
                note=runtime_status.note,
            )
        )

    return statuses
