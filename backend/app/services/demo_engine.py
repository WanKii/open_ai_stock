from __future__ import annotations

import hashlib
import logging
import threading
import time
from datetime import datetime, timezone

from app.core.config import load_settings
from app.services import repository
from app.services.sync_service import (
    execute_sync_job,
    register_job_signals,
    unregister_job_signals,
)

logger = logging.getLogger(__name__)

TASK_TIMEOUT_SECONDS = 300


AGENT_LABELS = {
    "market_analyst": "市场分析师",
    "fundamental_analyst": "基本面分析师",
    "news_analyst": "新闻分析师",
    "index_analyst": "大盘分析师",
    "sector_analyst": "板块分析师",
}


def _stable_int(seed: str, min_value: int, max_value: int) -> int:
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    value = int(digest[:8], 16)
    return min_value + (value % (max_value - min_value + 1))


def _pick_provider(settings: dict) -> tuple[str, str]:
    for name, provider in settings["llm_providers"].items():
        if provider.get("enabled"):
            return name, provider.get("model", "custom-model")
    return "openai", settings["llm_providers"]["openai"]["model"]


def _build_price_series(symbol: str, depth: str) -> list[dict[str, float | str]]:
    size = {"fast": 12, "standard": 20, "deep": 30}[depth]
    base = _stable_int(f"{symbol}:base", 18, 72)
    points: list[dict[str, float | str]] = []

    for index in range(size):
        drift = _stable_int(f"{symbol}:{depth}:{index}", -5, 6)
        value = round(base + index * 0.45 + drift * 0.35, 2)
        points.append({"label": f"T-{size - index - 1}", "value": value})

    return points


def _build_agent_report(task_id: str, symbol: str, depth: str, agent_type: str, provider: str, model: str) -> dict:
    score_delta = _stable_int(f"{task_id}:{agent_type}:score", -8, 9)
    confidence = _stable_int(f"{task_id}:{agent_type}:confidence", 62, 92)
    label = AGENT_LABELS[agent_type]
    prompt_snapshots = repository.list_prompt_snapshots(task_id)
    prompt_id = next(
        (item["id"] for item in prompt_snapshots if item["prompt_key"] == agent_type),
        prompt_snapshots[0]["id"] if prompt_snapshots else "",
    )

    direction = "偏积极" if score_delta >= 0 else "偏谨慎"
    return {
        "agent_type": agent_type,
        "status": "completed",
        "summary": f"{label}认为 {symbol} 在 {depth} 档分析下呈现 {direction} 结构，建议结合仓位纪律继续确认。",
        "positives": [
            f"{label}识别到近期存在 1 到 2 个正向催化点。",
            f"{label}认为当前价格区间仍具备继续跟踪价值。",
        ],
        "risks": [
            f"{label}提示该股对市场风格切换较为敏感。",
            f"{label}提醒高波动阶段可能放大回撤。",
        ],
        "confidence": confidence,
        "score_delta": score_delta,
        "evidence": [
            f"{depth} 档数据包已覆盖关键字段。",
            f"{label}已完成结构化结论抽取。",
        ],
        "missing_data": [],
        "provider": provider,
        "model": model,
        "prompt_snapshot_id": prompt_id,
    }


def build_report(task: dict, settings: dict) -> dict:
    provider, model = _pick_provider(settings)
    agent_reports = [
        _build_agent_report(task["id"], task["symbol"], task["depth"], agent, provider, model)
        for agent in task["selected_agents"]
    ]

    base_score = _stable_int(f"{task['symbol']}:{task['depth']}:overall", 52, 86)
    overall_score = max(35, min(92, base_score + sum(item["score_delta"] for item in agent_reports) // max(len(agent_reports), 1)))
    confidence = _stable_int(f"{task['id']}:confidence", 60, 93)

    if overall_score >= 75:
        action_tag = "关注"
    elif overall_score >= 60:
        action_tag = "观望"
    else:
        action_tag = "谨慎"

    return {
        "task_id": task["id"],
        "overall_score": overall_score,
        "action_tag": action_tag,
        "confidence": confidence,
        "thesis": f"{task['symbol']} 当前更适合作为{('重点观察标的' if overall_score >= 75 else '等待确认标的' if overall_score >= 60 else '风险控制优先标的')}，需要结合量价与后续公告继续验证。",
        "bull_points": [
            "多角色分析结果整体偏正向，未出现明显相互冲突。",
            "结构化报告认为当前观察价值高于短期放弃价值。",
            "模拟行情快照显示近期趋势仍保持中性偏强。",
        ],
        "bear_points": [
            "系统性波动仍可能放大利空消息影响。",
            "若成交量与板块共振不足，结论可信度会下降。",
        ],
        "watch_items": [
            "下一次业绩披露后的指引变化。",
            "板块强弱切换是否延续。",
            "市场风险偏好是否持续改善。",
        ],
        "disclaimer": "以上内容为基于公开数据与模型推理的辅助决策输出，不构成任何投资建议。",
        "data_snapshot": {
            "price_series": _build_price_series(task["symbol"], task["depth"]),
            "market_signals": [
                {"label": "沪深300", "value": f"{_stable_int(task['symbol'] + 'hs300', -2, 3)}%"},
                {"label": "上证指数", "value": f"{_stable_int(task['symbol'] + 'sh', -2, 3)}%"},
                {"label": "板块热度", "value": f"{_stable_int(task['symbol'] + 'sector', 48, 89)}"},
            ],
            "source_summary": [
                {"dataset": "quotes", "source": settings["source_priority_by_dataset"]["quotes"][0], "freshness": "本地优先"},
                {"dataset": "financials", "source": settings["source_priority_by_dataset"]["financials"][0], "freshness": "最近一期"},
                {"dataset": "news", "source": settings["source_priority_by_dataset"]["news"][0], "freshness": "最近 24 小时"},
            ],
        },
        "agent_reports": agent_reports,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def process_analysis_task(task_id: str) -> None:
    task = repository.get_task(task_id)
    if not task:
        return

    repository.update_task_status(task_id, "running")
    repository.add_system_log("analysis", "INFO", f"任务 {task_id} 进入执行状态。", task_id)

    result_holder: list[Exception | None] = [None]

    def _run() -> None:
        try:
            time.sleep(1.2)
            settings = load_settings()
            report = build_report(task, settings)
            repository.save_report(task_id, report)
        except Exception as exc:
            result_holder[0] = exc

    worker = threading.Thread(target=_run, daemon=True)
    worker.start()
    worker.join(timeout=TASK_TIMEOUT_SECONDS)

    if worker.is_alive():
        message = f"任务 {task_id} 执行超时（{TASK_TIMEOUT_SECONDS}s）。"
        logger.warning(message)
        repository.update_task_status(task_id, "failed", warnings=[message])
        repository.add_operation_log("analysis", "timeout", "ERROR", message, task_id)
        repository.add_system_log("analysis", "ERROR", message, task_id)
        return

    if result_holder[0] is not None:
        message = f"分析任务执行失败：{result_holder[0]}"
        repository.update_task_status(task_id, "failed")
        repository.add_operation_log("analysis", "failed", "ERROR", message, task_id)
        repository.add_system_log("analysis", "ERROR", message, task_id)
        return

    repository.update_task_status(task_id, "completed")
    repository.add_operation_log("analysis", "complete", "INFO", f"{task['symbol']} 分析完成。", task_id)
    repository.add_system_log("analysis", "INFO", f"任务 {task_id} 报告已落库。", task_id)


SYNC_TIMEOUT_SECONDS = 3600


def process_sync_job(job_id: str) -> None:
    job = repository.get_sync_job(job_id)
    if not job:
        return
    if job["status"] != "queued":
        logger.info("跳过同步任务 %s，当前状态为 %s。", job_id, job["status"])
        return

    repository.update_sync_job(job_id, "running")
    repository.add_system_log("sync", "INFO", f"同步任务 {job_id} 开始执行。", job_id)

    cancel_event, pause_event = register_job_signals(job_id)

    def _progress_callback(
        *,
        total_items: int | None = None,
        completed_items: int | None = None,
        error_items: int | None = None,
        skipped_items: int | None = None,
        current_item: str | None = None,
    ) -> None:
        try:
            repository.update_sync_job_progress(
                job_id,
                total_items=total_items,
                completed_items=completed_items,
                error_items=error_items,
                skipped_items=skipped_items,
                current_item=current_item,
            )
        except Exception:
            pass  # Non-critical — don't break the sync for a progress update failure

    result_holder: list = [None, None]  # [result, exception]

    def _run() -> None:
        try:
            result_holder[0] = execute_sync_job(
                job,
                cancel_event=cancel_event,
                pause_event=pause_event,
                progress=_progress_callback,
            )
        except Exception as exc:
            result_holder[1] = exc

    worker = threading.Thread(target=_run, daemon=True)
    worker.start()
    worker.join(timeout=SYNC_TIMEOUT_SECONDS)

    try:
        def _latest_job() -> dict | None:
            return repository.get_sync_job(job_id)

        def _is_cancelled() -> bool:
            latest_job = _latest_job()
            return latest_job is not None and latest_job["status"] == "cancelled"

        if worker.is_alive():
            cancel_event.set()  # Signal the worker to stop
            worker.join(timeout=10)
            if _is_cancelled():
                return
            message = f"同步任务 {job_id} 执行超时（{SYNC_TIMEOUT_SECONDS}s）。"
            logger.warning(message)
            repository.update_sync_job(job_id, "failed", result_summary=message)
            repository.add_operation_log("sync", "timeout", "ERROR", message, job_id)
            repository.add_system_log("sync", "ERROR", message, job_id)
            return

        if result_holder[1] is not None:
            if _is_cancelled():
                return
            message = f"同步任务执行失败：{result_holder[1]}"
            repository.update_sync_job(job_id, "failed", result_summary=message)
            repository.add_operation_log("sync", "failed", "ERROR", message, job_id)
            repository.add_system_log("sync", "ERROR", message, job_id)
            return

        result = result_holder[0]
        if _is_cancelled():
            latest_job = _latest_job()
            summary = result.summary if result is not None and result.status == "cancelled" else (latest_job or {}).get("result_summary") or "用户手动取消。"
            repository.update_sync_job(job_id, "cancelled", result_summary=summary)
            if result is not None:
                for warning in result.warnings:
                    repository.add_system_log("sync", "WARN", warning, job_id)
            return

        log_level = "WARN" if result.status == "completed_with_warnings" else "INFO"
        repository.update_sync_job(job_id, result.status, result_summary=result.summary)
        repository.add_operation_log("sync", "complete", log_level, result.summary, job_id)
        for warning in result.warnings:
            repository.add_system_log("sync", "WARN", warning, job_id)
        repository.add_system_log("sync", "INFO", f"同步任务 {job_id} 执行完成。", job_id)
    finally:
        unregister_job_signals(job_id)
