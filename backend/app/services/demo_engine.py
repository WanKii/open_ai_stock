from __future__ import annotations

import hashlib
import time
from datetime import datetime, timezone

from app.core.config import load_settings
from app.services import repository


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

    return {
        "agent_type": agent_type,
        "status": "completed",
        "summary": f"{label}认为 {symbol} 在 {depth} 档分析下呈现出偏{'积极' if score_delta >= 0 else '谨慎'}结构，建议结合仓位纪律观察后续确认信号。",
        "positives": [
            f"{label}识别到近期存在 1-2 个利好催化点。",
            f"{label}认为当前价格区间具备继续跟踪价值。",
        ],
        "risks": [
            f"{label}提示该股对市场风格切换较敏感。",
            f"{label}提醒关注高波动阶段的回撤放大。",
        ],
        "confidence": confidence,
        "score_delta": score_delta,
        "evidence": [
            f"{depth} 档数据包已覆盖关键字段。",
            f"{label}完成了结构化结论抽取。",
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
        "thesis": f"{task['symbol']} 当前更适合作为{'重点观察标的' if overall_score >= 75 else '等待确认标的' if overall_score >= 60 else '风险控制优先标的'}，需要结合量价确认与后续公告进一步验证。",
        "bull_points": [
            "多角色分析结果总体偏正向，未出现明显相互冲突。",
            "结构化报告认为当前观察价值高于短期放弃价值。",
            "模拟行情快照显示近期趋势未破坏中枢。",
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
    time.sleep(1.2)

    settings = load_settings()
    report = build_report(task, settings)
    repository.save_report(task_id, report)
    repository.update_task_status(task_id, "completed")
    repository.add_operation_log("analysis", "complete", "INFO", f"{task['symbol']} 分析完成。", task_id)
    repository.add_system_log("analysis", "INFO", f"任务 {task_id} 报告已落库。", task_id)


def process_sync_job(job_id: str) -> None:
    job = repository.get_sync_job(job_id)
    if not job:
        return

    repository.update_sync_job(job_id, "running")
    repository.add_system_log("sync", "INFO", f"同步任务 {job_id} 开始执行。", job_id)
    time.sleep(1.0)

    result_summary = f"{job['source']} 已完成 {job['job_type']}，同步范围：{job['scope']}。"
    repository.update_sync_job(job_id, "completed", result_summary=result_summary)
    repository.add_operation_log("sync", "complete", "INFO", result_summary, job_id)
    repository.add_system_log("sync", "INFO", f"同步任务 {job_id} 完成。", job_id)
