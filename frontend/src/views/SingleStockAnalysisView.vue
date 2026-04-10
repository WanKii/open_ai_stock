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
                <small>{{ item.exchange }} · {{ item.industry || item.area || "已同步基础信息" }}</small>
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
          <span class="muted">默认会保存任务、报告、提示词快照与日志。</span>
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
          <div>
            <strong>{{ task.symbol }}</strong>
            <p>{{ depthLabelMap[task.depth] }} / {{ task.selected_agents.length }} 个角色</p>
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
        <StatusBadge
          v-if="selectedTask"
          :label="isReportReady(selectedTask.status) ? '报告已就绪' : '等待生成中'"
          :tone="isReportReady(selectedTask.status) ? 'good' : 'warn'"
        />
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

      <div v-else class="empty-state">
        <template v-if="selectedTask">
          当前任务还在执行，报告生成后会自动显示在这里。
        </template>
        <template v-else>
          选择右侧任务，或者先提交一个新的分析任务。
        </template>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { ElMessage } from "element-plus";

import { createAnalysisTask, getAnalysisReport, listAnalysisTasks, listStocks } from "../api/client";
import AgentInsightCard from "../components/AgentInsightCard.vue";
import PricePulseChart from "../components/PricePulseChart.vue";
import StatusBadge from "../components/StatusBadge.vue";
import type { AnalysisDepth, AnalysisReport, AnalysisTask, StockListItem } from "../types";
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
let pollTimer: number | undefined;
let abortController: AbortController | null = null;
let suggestionRequestId = 0;

const agentOptions = [
  { label: "市场分析师", value: "market_analyst" },
  { label: "基本面分析师", value: "fundamental_analyst" },
  { label: "新闻分析师", value: "news_analyst" },
  { label: "大盘分析师", value: "index_analyst" },
  { label: "板块分析师", value: "sector_analyst" }
];

const depthLabelMap: Record<AnalysisDepth, string> = {
  fast: "快速",
  standard: "标准",
  deep: "深度"
};

const statusLabelMap: Record<string, string> = {
  queued: "排队中",
  running: "执行中",
  completed: "已完成",
  completed_with_warnings: "警告完成",
  failed: "失败",
  cancelled: "已取消"
};

const selectedTask = computed(() => tasks.value.find((task) => task.id === selectedTaskId.value) || null);

function isTerminal(status: string) {
  return ["completed", "completed_with_warnings", "failed", "cancelled"].includes(status);
}

function isReportReady(status: string) {
  return status === "completed" || status === "completed_with_warnings";
}

function stopPolling() {
  if (pollTimer) {
    window.clearInterval(pollTimer);
    pollTimer = undefined;
  }
  if (abortController) {
    abortController.abort();
    abortController = null;
  }
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
  if (task && isTerminal(task.status)) {
    await loadReport(task.id);
  }
}

function startPolling(taskId: string) {
  stopPolling();
  abortController = new AbortController();
  pollTimer = window.setInterval(async () => {
    if (abortController?.signal.aborted) return;
    try {
      await refreshTasks();
      const task = tasks.value.find((item) => item.id === taskId);
      if (task && isTerminal(task.status)) {
        stopPolling();
        await loadReport(taskId);
        await workspaceStore.refreshOverview();
      }
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") return;
    }
  }, 1500);
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
    startPolling(response.task_id);
    ElMessage.success(`任务已入队，当前位置 ${response.queue_position}`);
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "任务提交失败");
  } finally {
    submitting.value = false;
  }
}

watch(selectedTaskId, async (taskId) => {
  const task = tasks.value.find((item) => item.id === taskId);
  if (!task) {
    activeReport.value = null;
    return;
  }

  if (isTerminal(task.status)) {
    await loadReport(taskId);
  } else {
    activeReport.value = null;
  }
});

onMounted(refreshTasks);
onBeforeUnmount(stopPolling);
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
.stock-suggestion small {
  color: var(--muted);
}
</style>
