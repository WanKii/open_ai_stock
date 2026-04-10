export type TaskStatus =
  | "queued"
  | "running"
  | "completed"
  | "completed_with_warnings"
  | "failed"
  | "cancelled";

export type AnalysisDepth = "fast" | "standard" | "deep";

export interface AnalysisTask {
  id: string;
  symbol: string;
  depth: AnalysisDepth;
  selected_agents: string[];
  status: TaskStatus;
  queue_position?: number | null;
  warnings: string[];
  created_at: string;
  started_at?: string | null;
  finished_at?: string | null;
}

export interface AgentReport {
  agent_type: string;
  status: string;
  summary: string;
  positives: string[];
  risks: string[];
  confidence: number;
  score_delta: number;
  evidence: string[];
  missing_data: string[];
  provider: string;
  model: string;
  prompt_snapshot_id: string;
}

export interface PricePoint {
  label: string;
  value: number;
}

export interface AnalysisReport {
  task_id: string;
  overall_score: number;
  action_tag: string;
  confidence: number;
  thesis: string;
  bull_points: string[];
  bear_points: string[];
  watch_items: string[];
  disclaimer: string;
  data_snapshot: {
    price_series: PricePoint[];
    market_signals: Array<{ label: string; value: string }>;
    source_summary: Array<{ dataset: string; source: string; freshness: string }>;
  };
  agent_reports: AgentReport[];
  updated_at: string;
}

export interface TaskCreatedResponse {
  task_id: string;
  status: TaskStatus;
  queue_position: number;
}

export interface DataSourceConfig {
  enabled: boolean;
  priority: number;
  token: string;
  base_url: string;
  supports: string[];
  configured?: boolean;
}

export interface LlmProviderConfig {
  enabled: boolean;
  base_url: string;
  model: string;
  api_key: string;
  timeout: number;
  max_tokens: number;
  configured?: boolean;
}

export interface SystemSettings {
  data_sources: Record<string, DataSourceConfig>;
  llm_providers: Record<string, LlmProviderConfig>;
  source_priority_by_dataset: Record<string, string[]>;
  prompts: Record<string, string>;
  local_config_path?: string;
}

export interface LogEntry {
  id: number;
  module: string;
  action?: string | null;
  level: string;
  message: string;
  task_id?: string | null;
  created_at: string;
}

export interface DataSourceStatus {
  source: string;
  enabled: boolean;
  configured: boolean;
  priority: number;
  supports: string[];
  status: string;
  note: string;
}

export interface SyncJob {
  id: string;
  job_type: string;
  source: string;
  scope: string;
  params: Record<string, unknown>;
  status: TaskStatus;
  result_summary?: string | null;
  total_items: number;
  completed_items: number;
  error_items: number;
  skipped_items: number;
  current_item?: string | null;
  created_at: string;
  started_at?: string | null;
  finished_at?: string | null;
}

// ---------------------------------------------------------------------------
// 股票数据管理
// ---------------------------------------------------------------------------

export interface StockListItem {
  symbol: string;
  name: string;
  exchange: string;
  industry?: string | null;
  area?: string | null;
  listing_date?: string | null;
  status: string;
}

export interface StockListResponse {
  items: StockListItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface DataTypeSummary {
  source: string;
  data_type: string;
  record_count: number;
  latest_date?: string | null;
}

export interface StockDataSummaryResponse {
  symbol: string;
  name: string;
  summaries: DataTypeSummary[];
}

export interface StockDataPageResponse {
  rows: Record<string, unknown>[];
  total: number;
  page: number;
  page_size: number;
  columns: string[];
}
