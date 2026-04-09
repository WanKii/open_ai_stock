from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


TaskStatus = Literal["queued", "running", "completed", "completed_with_warnings", "failed", "cancelled"]
AnalysisDepth = Literal["fast", "standard", "deep"]
AgentType = Literal[
    "market_analyst",
    "fundamental_analyst",
    "news_analyst",
    "index_analyst",
    "sector_analyst",
]


class AnalysisTaskCreate(BaseModel):
    symbol: str
    depth: AnalysisDepth
    selected_agents: list[AgentType] = Field(default_factory=list)


class AnalysisTask(BaseModel):
    id: str
    symbol: str
    depth: AnalysisDepth
    selected_agents: list[str]
    status: TaskStatus
    queue_position: int | None = None
    warnings: list[str] = Field(default_factory=list)
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


class TaskCreatedResponse(BaseModel):
    task_id: str
    status: TaskStatus
    queue_position: int


class PricePoint(BaseModel):
    label: str
    value: float


class AgentReport(BaseModel):
    agent_type: str
    status: str
    summary: str
    positives: list[str]
    risks: list[str]
    confidence: int
    score_delta: int
    evidence: list[str]
    missing_data: list[str]
    provider: str
    model: str
    prompt_snapshot_id: str


class AnalysisReport(BaseModel):
    task_id: str
    overall_score: int
    action_tag: str
    confidence: int
    thesis: str
    bull_points: list[str]
    bear_points: list[str]
    watch_items: list[str]
    disclaimer: str
    data_snapshot: dict[str, Any]
    agent_reports: list[AgentReport]
    updated_at: datetime


class LogEntry(BaseModel):
    id: int
    module: str
    level: str
    message: str
    task_id: str | None = None
    created_at: datetime
    action: str | None = None


class SyncJobCreate(BaseModel):
    job_type: Literal["health_check", "symbol_sync", "history_sync", "financial_sync", "news_sync"]
    source: Literal["tushare", "akshare", "baostock"]
    scope: str = "all"
    params: dict[str, Any] = Field(default_factory=dict)


class SyncJob(BaseModel):
    id: str
    job_type: str
    source: str
    scope: str
    params: dict[str, Any]
    status: TaskStatus
    result_summary: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


class DataSourceConfig(BaseModel):
    enabled: bool
    priority: int
    token: str = ""
    base_url: str
    supports: list[str] = Field(default_factory=list)
    configured: bool | None = None


class LlmProviderConfig(BaseModel):
    enabled: bool
    base_url: str
    model: str
    api_key: str = ""
    timeout: int
    max_tokens: int
    configured: bool | None = None


class SystemSettings(BaseModel):
    data_sources: dict[str, DataSourceConfig]
    llm_providers: dict[str, LlmProviderConfig]
    source_priority_by_dataset: dict[str, list[str]]
    prompts: dict[str, str]
    local_config_path: str | None = None


class TestConnectionRequest(BaseModel):
    category: Literal["data_source", "llm_provider"]
    provider: str


class TestConnectionResponse(BaseModel):
    success: bool
    message: str


class DataSourceStatus(BaseModel):
    source: str
    enabled: bool
    configured: bool
    priority: int = 0
    supports: list[str] = Field(default_factory=list)
    status: str = "unknown"
    note: str = ""


# ---------------------------------------------------------------------------
# 股票数据管理
# ---------------------------------------------------------------------------


class StockListItem(BaseModel):
    symbol: str
    name: str
    exchange: str
    industry: str | None = None
    area: str | None = None
    listing_date: str | None = None
    status: str


class StockListResponse(BaseModel):
    items: list[StockListItem]
    total: int
    page: int
    page_size: int


class DataTypeSummary(BaseModel):
    source: str
    data_type: str
    record_count: int
    latest_date: str | None = None


class StockDataSummaryResponse(BaseModel):
    symbol: str
    name: str
    summaries: list[DataTypeSummary]


class StockDataPageResponse(BaseModel):
    rows: list[dict[str, Any]]
    total: int
    page: int
    page_size: int
    columns: list[str]


class DeleteDataResponse(BaseModel):
    deleted_count: int
