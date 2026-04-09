from __future__ import annotations

from fastapi import APIRouter

from app.core.config import load_settings, mask_secrets, merge_incoming_settings, reload_settings, save_settings
from app.models.schemas import SystemSettings, TestConnectionRequest, TestConnectionResponse
from app.services import repository
from app.services.sync_service import describe_source_status


router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("", response_model=SystemSettings)
def get_settings() -> SystemSettings:
    return SystemSettings.model_validate(mask_secrets(load_settings()))


@router.put("", response_model=SystemSettings)
def update_settings(payload: dict) -> SystemSettings:
    merged = merge_incoming_settings(payload)
    saved = save_settings(merged)
    reload_settings()
    repository.add_operation_log("settings", "update", "INFO", "系统配置已更新。")
    return SystemSettings.model_validate(mask_secrets(saved))


@router.post("/test-connection", response_model=TestConnectionResponse)
def test_connection(payload: TestConnectionRequest) -> TestConnectionResponse:
    settings = load_settings()
    section = "data_sources" if payload.category == "data_source" else "llm_providers"
    config = settings.get(section, {}).get(payload.provider)

    if not config:
        return TestConnectionResponse(success=False, message="未找到对应配置。")

    if payload.category == "data_source":
        runtime_status = describe_source_status(payload.provider, config)
        repository.add_operation_log("settings", "test_connection", "INFO", f"执行 {payload.provider} 数据源连接测试。")
        return TestConnectionResponse(success=runtime_status.live_mode, message=runtime_status.note)

    if not config.get("api_key"):
        return TestConnectionResponse(success=False, message=f"{payload.provider} 未配置 API Key。")

    repository.add_operation_log("settings", "test_connection", "INFO", f"执行 {payload.provider} 连接测试。")
    return TestConnectionResponse(
        success=True,
        message=f"{payload.provider} 连接测试通过（当前仍为本地模拟校验）。",
    )
