from __future__ import annotations

import asyncio
import json
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse

from app.core.config import load_settings
from app.models.schemas import AnalysisReport, AnalysisTask, AnalysisTaskCreate, TaskCreatedResponse
from app.services import repository
from app.services.analysis_engine import process_analysis_task


router = APIRouter(prefix="/api/analysis", tags=["analysis"])
_TERMINAL_STATUSES = {"completed", "completed_with_warnings", "failed", "cancelled"}


def _json_default(value: object) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"Unsupported value: {type(value)!r}")


@router.get("/tasks", response_model=list[AnalysisTask])
def list_analysis_tasks() -> list[AnalysisTask]:
    return [AnalysisTask.model_validate(item) for item in repository.list_tasks()]


@router.post("/tasks", response_model=TaskCreatedResponse)
def create_analysis_task(payload: AnalysisTaskCreate, background_tasks: BackgroundTasks) -> TaskCreatedResponse:
    if not payload.selected_agents:
        raise HTTPException(status_code=400, detail="至少选择一个分析角色。")

    task = repository.create_task(payload.symbol.strip().upper(), payload.depth, payload.selected_agents)
    repository.save_prompt_snapshots(task["id"], load_settings()["prompts"])
    repository.add_operation_log("analysis", "create", "INFO", f"{task['symbol']} 分析任务已入队。", task["id"])
    background_tasks.add_task(process_analysis_task, task["id"])
    return TaskCreatedResponse(task_id=task["id"], status=task["status"], queue_position=task["queue_position"] or 1)


@router.get("/tasks/{task_id}", response_model=AnalysisTask)
def get_analysis_task(task_id: str) -> AnalysisTask:
    task = repository.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在。")
    return AnalysisTask.model_validate(task)


@router.get("/tasks/{task_id}/stream")
async def stream_analysis_task(task_id: str) -> StreamingResponse:
    task = repository.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在。")

    async def event_generator():
        last_payload = ""
        try:
            while True:
                current = repository.get_task(task_id)
                if not current:
                    break

                payload = {
                    **current,
                    "finished": current["status"] in _TERMINAL_STATUSES,
                }
                serialized = json.dumps(payload, ensure_ascii=False, default=_json_default)
                if serialized != last_payload:
                    last_payload = serialized
                    yield f"data: {serialized}\n\n"

                if payload["finished"]:
                    break

                await asyncio.sleep(1)
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


@router.get("/tasks/{task_id}/report", response_model=AnalysisReport)
def get_analysis_report(task_id: str) -> AnalysisReport:
    report = repository.get_report(task_id)
    if not report:
        raise HTTPException(status_code=404, detail="报告尚未生成。")
    return AnalysisReport.model_validate(report)
