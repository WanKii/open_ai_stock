import type {
  AnalysisReport,
  AnalysisTask,
  DataSourceStatus,
  LogEntry,
  SyncJob,
  SystemSettings,
  TaskCreatedResponse
} from "../types";

const baseUrl = (import.meta.env.VITE_API_BASE_URL || "/api").replace(/\/$/, "");

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${baseUrl}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {})
    },
    ...init
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
