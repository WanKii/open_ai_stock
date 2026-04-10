from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter

from app.core.config import load_settings
from app.core.market_store import get_data_quality_overview
from app.models.schemas import DataQualityOverview, DataSourceStatus, TableQualityStat
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


@router.get("/quality", response_model=DataQualityOverview)
def get_data_quality() -> DataQualityOverview:
    overview = get_data_quality_overview()
    return DataQualityOverview(
        total_symbols=overview["total_symbols"],
        tables=[TableQualityStat(**t) for t in overview["tables"]],
        updated_at=datetime.now(timezone.utc),
    )
