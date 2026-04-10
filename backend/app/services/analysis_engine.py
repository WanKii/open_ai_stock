"""真实分析引擎 — 使用 DuckDB 本地数据 + LLM 多 Agent 并行分析。

当 LLM 配置可用时使用真实模型调用；否则回退到 demo_engine 模拟引擎。
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import threading
import time
from datetime import datetime, timezone
from typing import Any

from app.core.config import load_settings
from app.core.market_store import (
    get_announcements,
    get_daily_quotes,
    get_financials,
    get_index_daily,
    get_news,
    get_sector_daily,
    get_symbol_info,
)
from app.services import repository
from app.services.llm.base import LLMProvider

logger = logging.getLogger(__name__)

TASK_TIMEOUT_SECONDS = 300

AGENT_LABELS = {
    "market_analyst": "市场分析师",
    "fundamental_analyst": "基本面分析师",
    "news_analyst": "新闻分析师",
    "index_analyst": "大盘分析师",
    "sector_analyst": "板块分析师",
}

DEPTH_CONFIG = {
    "fast": {"quote_days": 60, "fin_quarters": 1, "news_count": 10},
    "standard": {"quote_days": 180, "fin_quarters": 12, "news_count": 30},
    "deep": {"quote_days": 365, "fin_quarters": 20, "news_count": 50},
}


def _get_llm_provider(settings: dict[str, Any]) -> tuple[LLMProvider | None, str, str]:
    """根据设置返回可用的 LLM 提供者，优先选择已启用且有 key 的。"""
    for name, config in settings.get("llm_providers", {}).items():
        if config.get("enabled") and config.get("api_key"):
            if name == "openai":
                from app.services.llm.openai_provider import OpenAIProvider
                return OpenAIProvider(config), name, config.get("model", "gpt-4.1-mini")
            elif name == "anthropic":
                from app.services.llm.anthropic_provider import AnthropicProvider
                return AnthropicProvider(config), name, config.get("model", "claude-3-5-sonnet-latest")
    return None, "", ""


def _build_data_package(symbol: str, depth: str) -> dict[str, Any]:
    """从 DuckDB 构建分析数据包。"""
    cfg = DEPTH_CONFIG[depth]

    symbol_info = get_symbol_info(symbol)
    quotes = get_daily_quotes(symbol, cfg["quote_days"])
    financials = get_financials(symbol, cfg["fin_quarters"])
    news = get_news(symbol, cfg["news_count"])
    announcements = get_announcements(symbol, cfg["news_count"])

    # 大盘数据
    index_data = get_index_daily("000300.SH", cfg["quote_days"])  # 沪深300
    sh_index = get_index_daily("000001.SH", cfg["quote_days"])  # 上证

    return {
        "symbol": symbol,
        "depth": depth,
        "symbol_info": symbol_info,
        "quotes": quotes,
        "financials": financials,
        "news": news,
        "announcements": announcements,
        "index_300": index_data,
        "index_sh": sh_index,
    }


def _format_quotes_summary(quotes: list[dict]) -> str:
    if not quotes:
        return "无历史行情数据。"
    latest = quotes[-1] if quotes else {}
    lines = [
        f"共 {len(quotes)} 个交易日数据。",
        f"最新日期: {latest.get('trade_date', 'N/A')}",
        f"最新收盘: {latest.get('close', 'N/A')}",
    ]
    if len(quotes) >= 2:
        first_close = quotes[0].get("close", 0)
        last_close = quotes[-1].get("close", 0)
        if first_close and first_close > 0:
            change = (last_close - first_close) / first_close * 100
            lines.append(f"区间涨跌幅: {change:.2f}%")

    # 高低点
    highs = [q.get("high", 0) for q in quotes if q.get("high")]
    lows = [q.get("low", 0) for q in quotes if q.get("low")]
    if highs:
        lines.append(f"区间最高: {max(highs)}")
    if lows:
        lines.append(f"区间最低: {min(lows)}")

    # 最近5日明细
    recent = quotes[-5:]
    lines.append("\n最近5个交易日:")
    for q in recent:
        lines.append(
            f"  {q.get('trade_date', '')}: 开{q.get('open','')}/高{q.get('high','')}"
            f"/低{q.get('low','')}/收{q.get('close','')}, 量{q.get('volume','')}"
        )
    return "\n".join(lines)


def _format_financials_summary(financials: list[dict]) -> str:
    if not financials:
        return "无财务数据。"
    lines = [f"共 {len(financials)} 期财务报告："]
    for f in financials[:8]:
        lines.append(
            f"  {f.get('report_date', 'N/A')} ({f.get('report_type', '')}): "
            f"营收={f.get('revenue', 0):.0f}, 净利润={f.get('net_profit', 0):.0f}, "
            f"ROE={f.get('roe', 0):.2f}%, 毛利率={f.get('gross_margin', 0):.2f}%"
        )
    return "\n".join(lines)


def _format_news_summary(news: list[dict]) -> str:
    if not news:
        return "无近期新闻。"
    lines = [f"共 {len(news)} 条新闻/公告："]
    for n in news[:10]:
        lines.append(f"  [{n.get('published_at', '')}] {n.get('title', '')}")
        content = n.get("content", "")
        if content:
            lines.append(f"    {content[:150]}...")
    return "\n".join(lines)


def _build_agent_user_message(agent_type: str, data_package: dict) -> str:
    """构建发送给每个 Agent 的用户消息（数据部分）。"""
    symbol = data_package["symbol"]
    info = data_package.get("symbol_info") or {}
    depth = data_package["depth"]

    header = (
        f"## 分析标的\n"
        f"- 代码: {symbol}\n"
        f"- 名称: {info.get('name', '未知')}\n"
        f"- 行业: {info.get('industry', '未知')}\n"
        f"- 地区: {info.get('area', '未知')}\n"
        f"- 分析深度: {depth}\n\n"
    )

    if agent_type == "market_analyst":
        return (
            header
            + f"## 价格走势\n{_format_quotes_summary(data_package['quotes'])}\n\n"
            + f"## 大盘参考（沪深300）\n{_format_quotes_summary(data_package.get('index_300', []))}\n"
        )
    elif agent_type == "fundamental_analyst":
        return (
            header
            + f"## 财务数据\n{_format_financials_summary(data_package['financials'])}\n\n"
            + f"## 价格走势\n{_format_quotes_summary(data_package['quotes'])}\n"
        )
    elif agent_type == "news_analyst":
        return (
            header
            + f"## 近期新闻与公告\n{_format_news_summary(data_package['news'])}\n\n"
            + f"## 近期公告\n{_format_news_summary(data_package.get('announcements', []))}\n"
        )
    elif agent_type == "index_analyst":
        return (
            header
            + f"## 上证指数走势\n{_format_quotes_summary(data_package.get('index_sh', []))}\n\n"
            + f"## 沪深300走势\n{_format_quotes_summary(data_package.get('index_300', []))}\n"
        )
    elif agent_type == "sector_analyst":
        return (
            header
            + f"## 个股走势\n{_format_quotes_summary(data_package['quotes'])}\n\n"
            + f"## 财务概况\n{_format_financials_summary(data_package['financials'])}\n"
        )
    return header


AGENT_RESPONSE_SCHEMA = """\
请以 JSON 格式输出你的分析结论，严格遵循以下结构：
```json
{
  "summary": "一段话概括你的分析结论",
  "positives": ["积极因素1", "积极因素2"],
  "risks": ["风险点1", "风险点2"],
  "confidence": 75,
  "score_delta": 3,
  "evidence": ["支撑论据1", "支撑论据2"],
  "missing_data": ["缺失的数据项（如有）"]
}
```
注意：
- confidence: 0-100 的整数，表示你对结论的置信度
- score_delta: -10 到 10 的整数，表示对总体评分的影响方向（正=看多, 负=看空）
- 请只输出 JSON，不要添加额外文字
"""


def _parse_agent_response(raw: str) -> dict[str, Any]:
    """从 LLM 回复中提取 JSON 结构，多级回退策略。"""
    # 1. 尝试提取 ```json ... ``` 中的内容（贪婪匹配最外层花括号）
    match = re.search(r"```(?:json)?\s*(\{[\s\S]*\})\s*```", raw)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # 2. 尝试直接解析整体为 JSON
    stripped = raw.strip()
    if stripped.startswith("{"):
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            pass

    # 3. 尝试提取第一个完整的 {...} 块（平衡花括号）
    brace_start = raw.find("{")
    if brace_start != -1:
        depth = 0
        for i in range(brace_start, len(raw)):
            if raw[i] == "{":
                depth += 1
            elif raw[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(raw[brace_start : i + 1])
                    except json.JSONDecodeError:
                        break

    # 4. 回退到默认结构
    return {
        "summary": raw[:500],
        "positives": [],
        "risks": [],
        "confidence": 60,
        "score_delta": 0,
        "evidence": [],
        "missing_data": ["LLM 返回格式不符合预期，已使用原始文本。"],
    }


async def _call_agent(
    llm: LLMProvider,
    agent_type: str,
    system_prompt: str,
    user_message: str,
    task_id: str,
    provider_name: str,
    model_name: str,
) -> dict[str, Any]:
    """调用单个 Agent 并解析结果。"""
    full_prompt = system_prompt + "\n\n" + AGENT_RESPONSE_SCHEMA
    label = AGENT_LABELS.get(agent_type, agent_type)

    try:
        raw_response = await llm.chat(full_prompt, user_message)
        parsed = _parse_agent_response(raw_response)
    except Exception as exc:
        logger.error("Agent %s 调用失败: %s", agent_type, exc)
        parsed = {
            "summary": f"{label}分析失败：{exc}",
            "positives": [],
            "risks": [f"Agent 调用异常: {exc}"],
            "confidence": 0,
            "score_delta": 0,
            "evidence": [],
            "missing_data": [f"LLM 调用失败: {exc}"],
        }

    prompt_snapshots = repository.list_prompt_snapshots(task_id)
    prompt_id = next(
        (s["id"] for s in prompt_snapshots if s["prompt_key"] == agent_type),
        prompt_snapshots[0]["id"] if prompt_snapshots else "",
    )

    return {
        "agent_type": agent_type,
        "status": "completed" if parsed.get("confidence", 0) > 0 else "failed",
        "summary": parsed.get("summary", ""),
        "positives": parsed.get("positives", []),
        "risks": parsed.get("risks", []),
        "confidence": parsed.get("confidence", 60),
        "score_delta": parsed.get("score_delta", 0),
        "evidence": parsed.get("evidence", []),
        "missing_data": parsed.get("missing_data", []),
        "provider": provider_name,
        "model": model_name,
        "prompt_snapshot_id": prompt_id,
    }


SUMMARIZER_RESPONSE_SCHEMA = """\
请以 JSON 格式输出你的汇总结论，严格遵循以下结构：
```json
{
  "overall_score": 72,
  "action_tag": "关注",
  "confidence": 78,
  "thesis": "一段话概括整体分析结论",
  "bull_points": ["看多理由1", "看多理由2"],
  "bear_points": ["看空理由1", "看空理由2"],
  "watch_items": ["后续关注事项1", "后续关注事项2"]
}
```
注意：
- overall_score: 35-92 之间的整数
- action_tag: 仅限"关注"、"观望"、"谨慎"三选一
- 请只输出 JSON，不要添加额外文字
"""


async def _call_summarizer(
    llm: LLMProvider,
    task: dict,
    agent_reports: list[dict],
    settings: dict,
) -> dict[str, Any]:
    """调用总结 Agent 汇总各角色结论。"""
    system_prompt = settings["prompts"].get("final_summarizer", "") + "\n\n" + SUMMARIZER_RESPONSE_SCHEMA

    # 构建各 Agent 报告摘要
    report_lines = []
    for r in agent_reports:
        label = AGENT_LABELS.get(r["agent_type"], r["agent_type"])
        report_lines.append(
            f"## {label}\n"
            f"- 结论: {r['summary']}\n"
            f"- 积极因素: {', '.join(r['positives'])}\n"
            f"- 风险点: {', '.join(r['risks'])}\n"
            f"- 置信度: {r['confidence']}%\n"
            f"- 评分影响: {r['score_delta']:+d}\n"
        )

    user_message = (
        f"股票代码: {task['symbol']}, 分析深度: {task['depth']}\n\n"
        f"以下是各分析师的结论：\n\n"
        + "\n".join(report_lines)
    )

    try:
        raw = await llm.chat(system_prompt, user_message)
        parsed = _parse_agent_response(raw)  # 复用多级回退解析
    except Exception as exc:
        logger.error("总结 Agent 调用失败: %s", exc)
        parsed = {}

    overall_score = parsed.get("overall_score", 65)
    overall_score = max(35, min(92, overall_score))

    return {
        "overall_score": overall_score,
        "action_tag": parsed.get("action_tag", "观望"),
        "confidence": parsed.get("confidence", 65),
        "thesis": parsed.get("thesis", f"{task['symbol']} 分析完成，请参考各 Agent 报告。"),
        "bull_points": parsed.get("bull_points", ["多角色分析已完成。"]),
        "bear_points": parsed.get("bear_points", ["请关注系统性风险。"]),
        "watch_items": parsed.get("watch_items", ["后续公告与业绩披露。"]),
    }


def _build_price_series(quotes: list[dict]) -> list[dict[str, Any]]:
    """从真实行情数据构建价格脉冲序列。"""
    if not quotes:
        return []
    return [
        {
            "label": str(q.get("trade_date", f"T-{i}")),
            "value": float(q.get("close", 0)),
        }
        for i, q in enumerate(quotes[-30:])  # 最近30个交易日
    ]


def _build_market_signals(data_package: dict) -> list[dict[str, str]]:
    """从真实数据构建市场信号。"""
    signals = []

    # 沪深300
    idx300 = data_package.get("index_300", [])
    if len(idx300) >= 2:
        change = (idx300[-1].get("close", 0) - idx300[-2].get("close", 1)) / max(idx300[-2].get("close", 1), 1) * 100
        signals.append({"label": "沪深300", "value": f"{change:.2f}%"})
    else:
        signals.append({"label": "沪深300", "value": "N/A"})

    # 上证
    idx_sh = data_package.get("index_sh", [])
    if len(idx_sh) >= 2:
        change = (idx_sh[-1].get("close", 0) - idx_sh[-2].get("close", 1)) / max(idx_sh[-2].get("close", 1), 1) * 100
        signals.append({"label": "上证指数", "value": f"{change:.2f}%"})
    else:
        signals.append({"label": "上证指数", "value": "N/A"})

    return signals


async def _run_analysis(task: dict, settings: dict) -> dict[str, Any]:
    """异步执行真实分析流程。"""
    llm, provider_name, model_name = _get_llm_provider(settings)

    # 如果没有可用的 LLM，回退到 demo
    if llm is None:
        logger.info("无可用 LLM 配置，回退到模拟引擎。")
        from app.services.demo_engine import build_report
        return build_report(task, settings)

    # 1. 构建数据包
    data_package = _build_data_package(task["symbol"], task["depth"])

    # 2. 并行调用各 Agent
    prompts = settings.get("prompts", {})
    agent_tasks = []
    for agent_type in task["selected_agents"]:
        system_prompt = prompts.get(agent_type, f"你是一名{AGENT_LABELS.get(agent_type, 'A股')}分析师。")
        user_message = _build_agent_user_message(agent_type, data_package)
        agent_tasks.append(
            _call_agent(llm, agent_type, system_prompt, user_message, task["id"], provider_name, model_name)
        )

    agent_reports = await asyncio.gather(*agent_tasks, return_exceptions=True)

    # 处理异常的 Agent 结果
    cleaned_reports = []
    for i, result in enumerate(agent_reports):
        if isinstance(result, Exception):
            agent_type = task["selected_agents"][i]
            cleaned_reports.append({
                "agent_type": agent_type,
                "status": "failed",
                "summary": f"{AGENT_LABELS.get(agent_type, agent_type)} 调用失败: {result}",
                "positives": [],
                "risks": [str(result)],
                "confidence": 0,
                "score_delta": 0,
                "evidence": [],
                "missing_data": [f"异常: {result}"],
                "provider": provider_name,
                "model": model_name,
                "prompt_snapshot_id": "",
            })
        else:
            cleaned_reports.append(result)

    # 3. 总结 Agent
    summarizer_result = await _call_summarizer(llm, task, cleaned_reports, settings)

    # 4. 构建完整报告
    source_priority = settings.get("source_priority_by_dataset", {})
    report = {
        "task_id": task["id"],
        "overall_score": summarizer_result["overall_score"],
        "action_tag": summarizer_result["action_tag"],
        "confidence": summarizer_result["confidence"],
        "thesis": summarizer_result["thesis"],
        "bull_points": summarizer_result["bull_points"],
        "bear_points": summarizer_result["bear_points"],
        "watch_items": summarizer_result["watch_items"],
        "disclaimer": "以上内容为基于公开数据与模型推理的辅助决策输出，不构成任何投资建议。",
        "data_snapshot": {
            "price_series": _build_price_series(data_package["quotes"]),
            "market_signals": _build_market_signals(data_package),
            "source_summary": [
                {
                    "dataset": ds,
                    "source": source_priority.get(ds, ["unknown"])[0],
                    "freshness": "本地数据",
                }
                for ds in ("quotes", "financials", "news")
            ],
        },
        "agent_reports": cleaned_reports,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    return report


def process_analysis_task(task_id: str) -> None:
    """处理分析任务 — 入口函数，由 BackgroundTasks 调用。"""
    task = repository.get_task(task_id)
    if not task:
        return

    repository.update_task_status(task_id, "running")
    repository.add_system_log("analysis", "INFO", f"任务 {task_id} 进入执行状态。", task_id)

    settings = load_settings()
    llm, _, _ = _get_llm_provider(settings)

    # 如果无可用 LLM，直接走 demo_engine 的同步路径
    if llm is None:
        logger.info("无可用 LLM，使用模拟引擎处理任务 %s", task_id)
        _run_demo_fallback(task_id, task, settings)
        return

    # 有可用 LLM，使用真实引擎
    result_holder: list[Any] = [None, None]  # [report, exception]

    def _run() -> None:
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                report = loop.run_until_complete(_run_analysis(task, settings))
                result_holder[0] = report
            finally:
                loop.close()
        except Exception as exc:
            result_holder[1] = exc

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

    if result_holder[1] is not None:
        message = f"分析任务执行失败：{result_holder[1]}"
        repository.update_task_status(task_id, "failed")
        repository.add_operation_log("analysis", "failed", "ERROR", message, task_id)
        repository.add_system_log("analysis", "ERROR", message, task_id)
        return

    report = result_holder[0]
    repository.save_report(task_id, report)

    # 检查是否有 Agent 失败
    warnings = []
    for ar in report.get("agent_reports", []):
        if ar.get("status") == "failed":
            warnings.append(f"{ar['agent_type']} 分析失败。")

    status = "completed_with_warnings" if warnings else "completed"
    repository.update_task_status(task_id, status, warnings=warnings)
    repository.add_operation_log("analysis", "complete", "INFO", f"{task['symbol']} 分析完成。", task_id)
    repository.add_system_log("analysis", "INFO", f"任务 {task_id} 报告已落库。", task_id)


def _run_demo_fallback(task_id: str, task: dict, settings: dict) -> None:
    """Demo 引擎回退路径。"""
    from app.services.demo_engine import build_report

    result_holder: list[Any] = [None, None]

    def _run() -> None:
        try:
            import time
            time.sleep(1.2)
            result_holder[0] = build_report(task, settings)
        except Exception as exc:
            result_holder[1] = exc

    worker = threading.Thread(target=_run, daemon=True)
    worker.start()
    worker.join(timeout=TASK_TIMEOUT_SECONDS)

    if worker.is_alive():
        message = f"任务 {task_id} 执行超时（{TASK_TIMEOUT_SECONDS}s）。"
        repository.update_task_status(task_id, "failed", warnings=[message])
        repository.add_system_log("analysis", "ERROR", message, task_id)
        return

    if result_holder[1] is not None:
        message = f"分析任务执行失败：{result_holder[1]}"
        repository.update_task_status(task_id, "failed")
        repository.add_system_log("analysis", "ERROR", message, task_id)
        return

    repository.save_report(task_id, result_holder[0])
    repository.update_task_status(task_id, "completed_with_warnings", warnings=["当前使用模拟引擎，未配置可用的 LLM。"])
    repository.add_operation_log("analysis", "complete", "INFO", f"{task['symbol']} 分析完成（模拟引擎）。", task_id)
    repository.add_system_log("analysis", "INFO", f"任务 {task_id} 报告已落库（模拟引擎）。", task_id)
