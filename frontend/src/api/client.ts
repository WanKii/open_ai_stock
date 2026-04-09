import type {
  AnalysisReport,
  AnalysisTask,
  DataSourceStatus,
  LogEntry,
  StockDataPageResponse,
  StockDataSummaryResponse,
  StockListResponse,
  SyncJob,
  SystemSettings,
  TaskCreatedResponse
} from "../types";

const baseUrl = (import.meta.env.VITE_API_BASE_URL || "/api").replace(/\/$/, "");

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const { headers: customHeaders, ...rest } = init || {};
  const response = await fetch(`${baseUrl}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(customHeaders || {})
    },
    ...rest
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || "请求失败");
  }

  return response.json() as Promise<T>;
}

export function listAnalysisTasks() {
  return request<AnalysisTask[]>("/analysis/tasks");
}

export function createAnalysisTask(payload: {
  symbol: string;
  depth: string;
  selected_agents: string[];
}) {
  return request<TaskCreatedResponse>("/analysis/tasks", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function getAnalysisTask(taskId: string) {
  return request<AnalysisTask>(`/analysis/tasks/${taskId}`);
}

export function getAnalysisReport(taskId: string) {
  return request<AnalysisReport>(`/analysis/tasks/${taskId}/report`);
}

export function getSettings() {
  return request<SystemSettings>("/settings");
}

export function updateSettings(payload: Partial<SystemSettings>) {
  return request<SystemSettings>("/settings", {
    method: "PUT",
    body: JSON.stringify(payload)
  });
}

export function testConnection(payload: { category: "data_source" | "llm_provider"; provider: string }) {
  return request<{ success: boolean; message: string }>("/settings/test-connection", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function listLogs(params: { kind?: "all" | "operation" | "system"; level?: string; task_id?: string; limit?: number }) {
  const query = new URLSearchParams();
  if (params.kind) query.set("kind", params.kind);
  if (params.level) query.set("level", params.level);
  if (params.task_id) query.set("task_id", params.task_id);
  if (params.limit) query.set("limit", String(params.limit));
  return request<LogEntry[]>(`/logs?${query.toString()}`);
}

export function getSourceStatuses() {
  return request<DataSourceStatus[]>("/data-sources/status");
}

export function listSyncJobs() {
  return request<SyncJob[]>("/sync/jobs");
}

export function createSyncJob(payload: {
  job_type: string;
  source: string;
  scope: string;
  params: Record<string, unknown>;
}) {
  return request<SyncJob>("/sync/jobs", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

// ---------------------------------------------------------------------------
// 股票数据管理
// ---------------------------------------------------------------------------

export function listStocks(page = 1, pageSize = 50, search?: string) {
  const query = new URLSearchParams();
  query.set("page", String(page));
  query.set("page_size", String(pageSize));
  if (search) query.set("search", search);
  return request<StockListResponse>(`/stocks?${query.toString()}`);
}

export function getStockDataSummary(symbol: string) {
  return request<StockDataSummaryResponse>(`/stocks/${encodeURIComponent(symbol)}/data-summary`);
}

export function getStockData(
  symbol: string,
  source: string,
  dataType: string,
  page = 1,
  pageSize = 50
) {
  const query = new URLSearchParams({
    source,
    data_type: dataType,
    page: String(page),
    page_size: String(pageSize)
  });
  return request<StockDataPageResponse>(
    `/stocks/${encodeURIComponent(symbol)}/data?${query.toString()}`
  );
}

export function getStockDataDownloadUrl(symbol: string, source: string, dataType: string) {
  const query = new URLSearchParams({ source, data_type: dataType });
  return `${baseUrl}/stocks/${encodeURIComponent(symbol)}/data/download?${query.toString()}`;
}

export function deleteStockData(symbol: string, source: string, dataType: string) {
  const query = new URLSearchParams({ source, data_type: dataType });
  return request<{ deleted_count: number }>(
    `/stocks/${encodeURIComponent(symbol)}/data?${query.toString()}`,
    { method: "DELETE" }
  );
}

export function syncStockBySource(symbol: string, source: string) {
  return request<SyncJob[]>(
    `/stocks/${encodeURIComponent(symbol)}/sync`,
    { method: "POST", body: JSON.stringify({ source }) }
  );
}
