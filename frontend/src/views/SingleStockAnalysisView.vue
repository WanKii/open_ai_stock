<template>
  <div class="workspace-grid">
    <section class="panel panel--form">
      <div class="panel__header">
        <div>
          <p class="eyebrow">ANALYSIS ENTRY</p>
          <h3>提交单股分析任务</h3>
        </div>
        <StatusBadge label="本地队列" tone="warn" />
      </div>

      <el-form label-position="top" class="analysis-form">
        <el-form-item label="股票代码">
          <el-autocomplete
            v-model="form.symbol"
            :fetch-suggestions="queryStockSuggestions"
            value-key="symbol"
            trigger-on-focus="false"
            fit-input-width
            clearable
            placeholder="例如 600519.SH / 000001.SZ"
            @select="handleSuggestionSelect"
          >
            <template #default="{ item }">
              <div class="stock-suggestion">
                <div class="stock-suggestion__headline">
                  <strong>{{ item.symbol }}</strong>
                  <span>{{ item.name }}</span>
                </div>
                <small>{{ item.exchange }} / {{ item.industry || item.area || "已同步基础信息" }}</small>
              </div>
            </template>
          </el-autocomplete>
        </el-form-item>

        <el-form-item label="分析深度">
          <el-radio-group v-model="form.depth" class="depth-switch">
            <el-radio-button label="fast">快速</el-radio-button>
            <el-radio-button label="standard">标准</el-radio-button>
            <el-radio-button label="deep">深度</el-radio-button>
          </el-radio-group>
        </el-form-item>

        <el-form-item label="分析团队">
          <el-checkbox-group v-model="form.selected_agents" class="agent-grid">
            <el-checkbox
              v-for="agent in agentOptions"
              :key="agent.value"
              :label="agent.value"
              border
            >
              {{ agent.label }}
            </el-checkbox>
          </el-checkbox-group>
        </el-form-item>

        <div class="panel__actions">
          <el-button type="primary" size="large" :loading="submitting" @click="submitAnalysis">
            开始智能分析
          </el-button>
          <span class="muted">任务、报告、提示词快照与日志会自动持久化。</span>
        </div>
      </el-form>
    </section>

    <section class="panel panel--queue">
      <div class="panel__header">
        <div>
          <p class="eyebrow">QUEUE</p>
          <h3>任务队列</h3>
        </div>
        <el-button text @click="refreshTasks">刷新</el-button>
      </div>

      <div v-if="tasks.length" class="task-list">
        <button
          v-for="task in tasks.slice(0, 6)"
          :key="task.id"
          class="task-item"
          :class="{ 'task-item--active': task.id === selectedTaskId }"
          @click="selectedTaskId = task.id"
        >
          <div class="task-item__body">
            <strong>{{ task.symbol }}</strong>
            <p>{{ depthLabelMap[task.depth] }} / {{ task.selected_agents.length }} 个角色</p>
            <small v-if="task.status === 'running' || task.status === 'queued'">
              {{ task.progress.current_step }}
            </small>
          </div>
          <StatusBadge
            :label="statusLabelMap[task.status]"
            :tone="isReportReady(task.status) ? 'good' : task.status === 'failed' ? 'danger' : 'warn'"
            :pulse="task.status === 'running'"
          />
        </button>
      </div>
      <div v-else class="empty-state">还没有分析任务，先提交一只股票试试。</div>
    </section>

    <section class="panel panel--report">
      <div class="panel__header">
        <div>
          <p class="eyebrow">REPORT</p>
          <h3>报告概览</h3>
        </div>
        <div class="report-status">
          <StatusBadge
            v-if="selectedTask"
            :label="isReportReady(selectedTask.status) ? '报告已就绪' : '实时推送中'"
            :tone="isReportReady(selectedTask.status) ? 'good' : 'warn'"
            :pulse="selectedTask.status === 'running'"
          />
          <span v-if="selectedTask && !isReportReady(selectedTask.status)" class="stream-indicator">
            {{ streamConnected ? "SSE 已连接" : "回退轮询中" }}
          </span>
        </div>
      </div>

      <template v-if="activeReport && selectedTask">
        <div class="report-hero">
          <div>
            <p class="report-hero__symbol">{{ selectedTask.symbol }}</p>
            <h3>{{ activeReport.thesis }}</h3>
            <p class="muted">{{ activeReport.disclaimer }}</p>
          </div>
          <div class="score-ring">
            <span>综合评分</span>
            <strong>{{ activeReport.overall_score }}</strong>
            <small>{{ activeReport.action_tag }}</small>
          </div>
        </div>

        <div class="metric-strip">
          <div class="metric-block">
            <span>结论标签</span>
            <strong>{{ activeReport.action_tag }}</strong>
          </div>
          <div class="metric-block">
            <span>置信度</span>
            <strong>{{ activeReport.confidence }}</strong>
          </div>
          <div class="metric-block">
            <span>已分析角色</span>
            <strong>{{ activeReport.agent_reports.length }}</strong>
          </div>
        </div>

        <div class="report-grid">
          <div class="report-chart">
            <p class="mini-title">价格脉冲</p>
            <PricePulseChart :points="activeReport.data_snapshot.price_series" />
          </div>

          <div class="report-signals">
            <p class="mini-title">市场信号</p>
            <div class="signal-list">
              <div v-for="signal in activeReport.data_snapshot.market_signals" :key="signal.label" class="signal-item">
                <span>{{ signal.label }}</span>
                <strong>{{ signal.value }}</strong>
              </div>
            </div>
          </div>
        </div>

        <div class="summary-columns">
          <div>
            <p class="mini-title">看多线索</p>
            <ul>
              <li v-for="item in activeReport.bull_points" :key="item">{{ item }}</li>
            </ul>
          </div>
          <div>
            <p class="mini-title">风险线索</p>
            <ul>
              <li v-for="item in activeReport.bear_points" :key="item">{{ item }}</li>
            </ul>
          </div>
          <div>
            <p class="mini-title">继续跟踪</p>
            <ul>
              <li v-for="item in activeReport.watch_items" :key="item">{{ item }}</li>
            </ul>
          </div>
        </div>

        <div class="agent-report-grid">
          <AgentInsightCard
            v-for="report in activeReport.agent_reports"
            :key="report.agent_type"
            :report="report"
          />
        </div>
      </template>

      <template v-else-if="selectedTask">
        <div class="progress-hero">
          <div>
            <p class="report-hero__symbol">{{ selectedTask.symbol }}</p>
            <h3>{{ phaseLabel(selectedTask.progress.phase) }}</h3>
            <p class="muted">{{ selectedTask.progress.current_step }}</p>
          </div>
          <div class="score-ring score-ring--progress">
            <span>分析进度</span>
            <strong>{{ progressPercentage }}%</strong>
            <small>{{ selectedTask.progress.completed_agents }}/{{ selectedTask.progress.total_agents }} Agents</small>
          </div>
        </div>

        <div class="progress-track">
          <el-progress
            :percentage="progressPercentage"
            :indeterminate="selectedTask.status === 'running' && progressPercentage < 15"
            :stroke-width="14"
          />
        </div>

        <div class="metric-strip">
          <div class="metric-block">
            <span>任务状态</span>
            <strong>{{ statusLabelMap[selectedTask.status] }}</strong>
          </div>
          <div class="metric-block">
            <span>运行中 Agent</span>
            <strong>{{ selectedTask.progress.current_agent_types.length }}</strong>
          </div>
          <div class="metric-block">
            <span>队列位置</span>
            <strong>{{ selectedTask.queue_position ?? "-" }}</strong>
          </div>
        </div>

        <div class="agent-progress-grid">
          <article
            v-for="agent in selectedTask.progress.agent_states"
            :key="agent.agent_type"
            class="agent-progress-card"
            :class="`agent-progress-card--${agent.status}`"
          >
            <div class="agent-progress-card__header">
              <div>
                <p class="eyebrow">{{ agentLabelMap[agent.agent_type] || agent.agent_type }}</p>
                <h4>{{ agentStatusLabel(agent.status) }}</h4>
              </div>
              <StatusBadge
                :label="agentStatusLabel(agent.status)"
                :tone="agentStatusTone(agent.status)"
                :pulse="agent.status === 'running'"
              />
            </div>
            <p class="agent-progress-card__summary">
              {{ agent.summary || agentStatusHint(agent.status) }}
            </p>
          </article>
        </div>
      </template>

      <div v-else class="empty-state">
        选择右侧任务，或者先提交一个新的分析任务。
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { ElMessage } from "element-plus";

import {
  createAnalysisTask,
  getAnalysisReport,
  getAnalysisTaskStreamUrl,
  listAnalysisTasks,
  listStocks
} from "../api/client";
import AgentInsightCard from "../components/AgentInsightCard.vue";
import PricePulseChart from "../components/PricePulseChart.vue";
import StatusBadge from "../components/StatusBadge.vue";
import type {
  AgentProgressStatus,
  AnalysisDepth,
  AnalysisReport,
  AnalysisTask,
  StockListItem
} from "../types";
import { useWorkspaceStore } from "../stores/workspace";

const workspaceStore = useWorkspaceStore();

const form = ref<{
  symbol: string;
  depth: AnalysisDepth;
  selected_agents: string[];
}>({
  symbol: "600519.SH",
  depth: "standard",
  selected_agents: ["market_analyst", "fundamental_analyst", "news_analyst"]
});

const tasks = ref<AnalysisTask[]>([]);
const selectedTaskId = ref("");
const activeReport = ref<AnalysisReport | null>(null);
const submitting = ref(false);
const streamConnected = ref(false);

let eventSource: EventSource | null = null;
let fallbackTimer: number | undefined;
let suggestionRequestId = 0;

const agentOptions = [
  { label: "市场分析师", value: "market_analyst" },
  { label: "基本面分析师", value: "fundamental_analyst" },
  { label: "新闻分析师", value: "news_analyst" },
  { label: "大盘分析师", value: "index_analyst" },
  { label: "板块分析师", value: "sector_analyst" }
];

const agentLabelMap: Record<string, string> = Object.fromEntries(
  agentOptions.map((item) => [item.value, item.label])
);

const depthLabelMap: Record<AnalysisDepth, string> = {
  fast: "快速",
  standard: "标准",
  deep: "深度"
};

const statusLabelMap: Record<string, string> = {
  queued: "排队中",
  running: "执行中",
  completed: "已完成",
  completed_with_warnings: "带警告完成",
  failed: "失败",
  cancelled: "已取消"
};

const selectedTask = computed(() => tasks.value.find((task) => task.id === selectedTaskId.value) || null);

const progressPercentage = computed(() => {
  const task = selectedTask.value;
  if (!task) return 0;
  if (isTerminal(task.status)) return 100;

  const progress = task.progress;
  if (!progress.total_agents) return progress.phase === "loading_data" ? 12 : 0;
  if (progress.phase === "summarizing") return 92;

  const base = Math.round((progress.completed_agents / progress.total_agents) * 80);
  const runningBonus = progress.current_agent_types.length > 0 ? 8 : 0;
  return Math.min(88, Math.max(8, base + runningBonus));
});

function isTerminal(status: string) {
  return ["completed", "completed_with_warnings", "failed", "cancelled"].includes(status);
}

function isReportReady(status: string) {
  return status === "completed" || status === "completed_with_warnings";
}

function phaseLabel(phase: string) {
  const phaseMap: Record<string, string> = {
    queued: "等待调度",
    running: "任务已启动",
    loading_data: "正在准备数据",
    running_agents: "多 Agent 分析中",
    summarizing: "汇总结论中",
    completed: "分析完成",
    failed: "分析失败",
    cancelled: "任务已取消"
  };
  return phaseMap[phase] || "分析处理中";
}

function agentStatusLabel(status: AgentProgressStatus) {
  const labelMap: Record<AgentProgressStatus, string> = {
    pending: "等待执行",
    running: "执行中",
    completed: "已完成",
    failed: "失败"
  };
  return labelMap[status];
}

function agentStatusTone(status: AgentProgressStatus) {
  const toneMap: Record<AgentProgressStatus, "neutral" | "warn" | "good" | "danger"> = {
    pending: "neutral",
    running: "warn",
    completed: "good",
    failed: "danger"
  };
  return toneMap[status];
}

function agentStatusHint(status: AgentProgressStatus) {
  const hintMap: Record<AgentProgressStatus, string> = {
    pending: "等待调度到本轮分析流程。",
    running: "该 Agent 正在产出结构化结论。",
    completed: "该 Agent 已提交分析结果。",
    failed: "该 Agent 执行异常，最终报告会标出风险。"
  };
  return hintMap[status];
}

function mergeTask(task: AnalysisTask) {
  const index = tasks.value.findIndex((item) => item.id === task.id);
  if (index >= 0) {
    tasks.value[index] = task;
  } else {
    tasks.value.unshift(task);
  }
  tasks.value = [...tasks.value].sort((left, right) => right.created_at.localeCompare(left.created_at));
}

function stopFallbackPolling() {
  if (fallbackTimer) {
    window.clearInterval(fallbackTimer);
    fallbackTimer = undefined;
  }
}

function stopTaskTracking() {
  stopFallbackPolling();
  if (eventSource) {
    eventSource.close();
    eventSource = null;
  }
  streamConnected.value = false;
}

async function loadReport(taskId: string) {
  try {
    activeReport.value = await getAnalysisReport(taskId);
  } catch {
    activeReport.value = null;
  }
}

async function queryStockSuggestions(query: string, callback: (items: StockListItem[]) => void) {
  const keyword = query.trim();
  if (!keyword) {
    callback([]);
    return;
  }

  const requestId = ++suggestionRequestId;
  try {
    const { items } = await listStocks(1, 8, keyword);
    if (requestId === suggestionRequestId) {
      callback(items);
    }
  } catch {
    if (requestId === suggestionRequestId) {
      callback([]);
    }
  }
}

function handleSuggestionSelect(item: StockListItem) {
  form.value.symbol = item.symbol;
}

async function refreshTasks() {
  tasks.value = await listAnalysisTasks();

  if (!selectedTaskId.value && tasks.value.length) {
    selectedTaskId.value = tasks.value[0].id;
  }

  const task = tasks.value.find((item) => item.id === selectedTaskId.value);
  if (!task) {
    activeReport.value = null;
    return;
  }

  if (isReportReady(task.status)) {
    await loadReport(task.id);
  } else if (!isTerminal(task.status)) {
    activeReport.value = null;
  }
}

function startFallbackPolling(taskId: string) {
  stopFallbackPolling();
  fallbackTimer = window.setInterval(async () => {
    try {
      await refreshTasks();
      const task = tasks.value.find((item) => item.id === taskId);
      if (task && isTerminal(task.status)) {
        stopTaskTracking();
        if (isReportReady(task.status)) {
          await loadReport(taskId);
        }
        await workspaceStore.refreshOverview();
      }
    } catch {
      // Ignore periodic polling errors and keep retrying.
    }
  }, 1500);
}

function startTaskStream(taskId: string) {
  stopTaskTracking();
  eventSource = new EventSource(getAnalysisTaskStreamUrl(taskId));

  eventSource.onopen = () => {
    streamConnected.value = true;
  };

  eventSource.onmessage = async (event) => {
    try {
      const task = JSON.parse(event.data) as AnalysisTask & { finished?: boolean };
      mergeTask(task);

      if (task.id === selectedTaskId.value && isReportReady(task.status)) {
        await loadReport(task.id);
      }

      if (task.finished) {
        stopTaskTracking();
        await workspaceStore.refreshOverview();
      }
    } catch {
      // Ignore malformed events and keep the stream alive.
    }
  };

  eventSource.onerror = () => {
    streamConnected.value = false;
    if (eventSource) {
      eventSource.close();
      eventSource = null;
    }
    startFallbackPolling(taskId);
  };
}

async function submitAnalysis() {
  if (!form.value.symbol.trim()) {
    ElMessage.warning("请输入股票代码。");
    return;
  }

  if (!form.value.selected_agents.length) {
    ElMessage.warning("至少选择一个分析角色。");
    return;
  }

  submitting.value = true;
  try {
    const response = await createAnalysisTask({
      symbol: form.value.symbol.trim(),
      depth: form.value.depth,
      selected_agents: form.value.selected_agents
    });
    selectedTaskId.value = response.task_id;
    activeReport.value = null;
    await refreshTasks();
    await workspaceStore.refreshOverview();
    startTaskStream(response.task_id);
    ElMessage.success(`任务已入队，当前位置 ${response.queue_position}`);
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "任务提交失败");
  } finally {
    submitting.value = false;
  }
}

watch(selectedTaskId, async (taskId) => {
  if (!taskId) {
    stopTaskTracking();
    activeReport.value = null;
    return;
  }

  const task = tasks.value.find((item) => item.id === taskId);
  if (!task) {
    activeReport.value = null;
    return;
  }

  if (isReportReady(task.status)) {
    stopTaskTracking();
    await loadReport(taskId);
    return;
  }

  if (isTerminal(task.status)) {
    stopTaskTracking();
    activeReport.value = null;
    return;
  }

  activeReport.value = null;
  startTaskStream(taskId);
});

onMounted(async () => {
  await refreshTasks();
  const task = selectedTask.value;
  if (task && !isTerminal(task.status)) {
    startTaskStream(task.id);
  }
});

onBeforeUnmount(stopTaskTracking);
</script>

<style scoped>
.stock-suggestion {
  display: grid;
  gap: 4px;
  padding: 4px 0;
}

.stock-suggestion strong,
.stock-suggestion span,
.stock-suggestion small {
  line-height: 1.4;
}

.stock-suggestion__headline {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.stock-suggestion__headline span,
.stock-suggestion small,
.task-item__body small,
.stream-indicator {
  color: var(--muted);
}

.task-item__body {
  display: grid;
  gap: 4px;
}

.report-status {
  display: flex;
  align-items: center;
  gap: 12px;
}

.stream-indicator {
  font-size: 12px;
}

.progress-hero {
  display: flex;
  justify-content: space-between;
  gap: 24px;
  align-items: flex-start;
}

.score-ring--progress {
  min-width: 140px;
}

.progress-track {
  margin: 20px 0 24px;
}

.agent-progress-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 16px;
}

.agent-progress-card {
  border: 1px solid var(--border);
  border-radius: 18px;
  padding: 18px;
  background: color-mix(in srgb, var(--paper) 92%, transparent);
  display: grid;
  gap: 14px;
}

.agent-progress-card--running {
  box-shadow: 0 0 0 1px color-mix(in srgb, var(--accent) 22%, transparent);
}

.agent-progress-card__header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
}

.agent-progress-card__header h4 {
  margin: 4px 0 0;
}

.agent-progress-card__summary {
  margin: 0;
  line-height: 1.6;
  color: var(--muted);
}
</style>
