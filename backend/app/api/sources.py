from __future__ import annotations

from fastapi import APIRouter

from app.core.config import load_settings
from app.models.schemas import DataSourceStatus


router = APIRouter(prefix="/api/data-sources", tags=["data-sources"])


@router.get("/status", response_model=list[DataSourceStatus])
def get_source_status() -> list[DataSourceStatus]:
    settings = load_settings()
    statuses: list[DataSourceStatus] = []

    for source_name, config in settings["data_sources"].items():
        configured = bool(config.get("token")) or source_name == "akshare"
        enabled = bool(config.get("enabled"))

        if enabled and configured:
            status = "online"
            note = "配置完整，可进入手动同步。"
        elif enabled and not configured:
            status = "missing_token"
            note = "已启用，但缺少访问凭证。"
        else:
            status = "disabled"
            note = "当前未启用。"

        statuses.append(
            DataSourceStatus(
                source=source_name,
                enabled=enabled,
                configured=configured,
                priority=config["priority"],
                supports=config["supports"],
                status=status,
                note=note,
            )
        )

    return statuses
