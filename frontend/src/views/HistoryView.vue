<template>
  <div class="workspace-grid workspace-grid--history">
    <section class="panel">
      <div class="panel__header">
        <div>
          <p class="eyebrow">ARCHIVE</p>
          <h3>历史分析记录</h3>
        </div>
        <div class="panel__actions">
          <el-button
            :type="compareMode ? 'primary' : ''"
            text
            @click="toggleCompareMode"
          >
            {{ compareMode ? "退出对比" : "报告对比" }}
          </el-button>
          <el-button text @click="loadHistory">刷新</el-button>
        </div>
      </div>

      <div class="toolbar">
        <el-input v-model="keyword" placeholder="按股票代码筛选" clearable />
        <el-select v-model="statusFilter" clearable placeholder="状态">
          <el-option label="排队中" value="queued" />
          <el-option label="执行中" value="running" />
          <el-option label="已完成" value="completed" />
          <el-option label="失败" value="failed" />
        </el-select>
      </div>

      <!-- 对比模式选择提示 -->
      <div v-if="compareMode" class="compare-hint">
        <p>
          已选择 <strong>{{ selectedIds.length }}</strong> / 5 个报告
          <el-button
            v-if="selectedIds.length >= 2"
            type="primary"
            size="small"
            :loading="compareLoading"
            @click="doCompare"
          >
            开始对比
          </el-button>
        </p>
      </div>

      <template v-if="historyLoading">
        <div class="skeleton-grid">
          <div v-for="i in 6" :key="i" class="skeleton-card" />
        </div>
      </template>
      <el-table
        v-else
        :data="filteredTasks"
        height="540"
        @row-click="handleRowClick"
      >
        <el-table-column v-if="compareMode" width="50" align="center">
          <template #default="{ row }">
            <el-checkbox
              v-if="row.status === 'completed' || row.status === 'completed_with_warnings'"
              :model-value="selectedIds.includes(row.id)"
              :disabled="!selectedIds.includes(row.id) && selectedIds.length >= 5"
              @change="(val: boolean) => toggleSelection(row.id, val)"
            />
          </template>
        </el-table-column>
        <el-table-column prop="symbol" label="股票代码" min-width="140" />
        <el-table-column prop="depth" label="深度" min-width="90" />
        <el-table-column prop="status" label="状态" min-width="120" />
        <el-table-column prop="created_at" label="创建时间" min-width="180" />
      </el-table>
    </section>

    <!-- 普通详情面板 -->
    <section v-if="!compareMode && !comparisonData.length" v-loading="reportLoading" class="panel">
      <div class="panel__header">
        <div>
          <p class="eyebrow">DETAIL</p>
          <h3>任务详情</h3>
        </div>
      </div>

      <template v-if="selectedTask && selectedReport">
        <div class="detail-headline">
          <div>
            <p class="report-hero__symbol">{{ selectedTask.symbol }}</p>
            <h3>{{ selectedReport.thesis }}</h3>
          </div>
          <div class="score-ring score-ring--small">
            <span>{{ selectedReport.action_tag }}</span>
            <strong>{{ selectedReport.overall_score }}</strong>
          </div>
        </div>

        <PricePulseChart :points="selectedReport.data_snapshot.price_series" />

        <div class="agent-report-grid">
          <AgentInsightCard
            v-for="report in selectedReport.agent_reports"
            :key="report.agent_type"
            :report="report"
          />
        </div>
      </template>

      <div v-else class="empty-state">
        从左侧列表选择一条已完成的分析记录后，这里会显示对应报告。
      </div>
    </section>

    <!-- 对比视图面板 -->
    <section v-if="compareMode || comparisonData.length" v-loading="compareLoading" class="panel">
      <div class="panel__header">
        <div>
          <p class="eyebrow">COMPARISON</p>
          <h3>报告对比</h3>
        </div>
        <el-button v-if="comparisonData.length" text @click="clearComparison">清除对比</el-button>
      </div>

      <template v-if="comparisonData.length">
        <!-- 概览对比表 -->
        <div class="compare-overview">
          <table class="compare-table">
            <thead>
              <tr>
                <th>指标</th>
                <th v-for="r in comparisonData" :key="r.task_id">
                  {{ formatDate(r.created_at) }}
                </th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td class="compare-table__label">股票代码</td>
                <td v-for="r in comparisonData" :key="r.task_id">{{ r.symbol }}</td>
              </tr>
              <tr>
                <td class="compare-table__label">分析深度</td>
                <td v-for="r in comparisonData" :key="r.task_id">{{ depthLabel(r.depth) }}</td>
              </tr>
              <tr>
                <td class="compare-table__label">综合评分</td>
                <td v-for="r in comparisonData" :key="r.task_id">
                  <strong :class="scoreClass(r.overall_score)">{{ r.overall_score }}</strong>
                </td>
              </tr>
              <tr>
                <td class="compare-table__label">行动标签</td>
                <td v-for="r in comparisonData" :key="r.task_id">
                  <span class="action-chip">{{ r.action_tag }}</span>
                </td>
              </tr>
              <tr>
                <td class="compare-table__label">置信度</td>
                <td v-for="r in comparisonData" :key="r.task_id">{{ r.confidence }}%</td>
              </tr>
              <tr>
                <td class="compare-table__label">投资论点</td>
                <td v-for="r in comparisonData" :key="r.task_id" class="compare-table__thesis">{{ r.thesis }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- 看多/看空对比 -->
        <div class="compare-points-grid">
          <div v-for="r in comparisonData" :key="r.task_id" class="compare-points-col">
            <p class="eyebrow">{{ formatDate(r.created_at) }}</p>
            <div class="compare-points-section">
              <p class="mini-title">看多要点</p>
              <ul>
                <li v-for="(p, i) in r.bull_points" :key="i">{{ p }}</li>
              </ul>
            </div>
            <div class="compare-points-section">
              <p class="mini-title">看空要点</p>
              <ul>
                <li v-for="(p, i) in r.bear_points" :key="i">{{ p }}</li>
              </ul>
            </div>
          </div>
        </div>

        <!-- Agent 级别对比 -->
        <div class="compare-agents">
          <p class="eyebrow" style="margin-bottom: 12px">AGENT COMPARISON</p>
          <table class="compare-table">
            <thead>
              <tr>
                <th>Agent</th>
                <th v-for="r in comparisonData" :key="r.task_id">
                  {{ formatDate(r.created_at) }}
                </th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="agentType in allAgentTypes" :key="agentType">
                <td class="compare-table__label">{{ agentLabelMap[agentType] || agentType }}</td>
                <td v-for="r in comparisonData" :key="r.task_id">
                  <template v-if="getAgent(r, agentType)">
                    <div class="compare-agent-cell">
                      <span>置信 {{ getAgent(r, agentType)!.confidence }}%</span>
                      <span :class="deltaClass(getAgent(r, agentType)!.score_delta)">
                        {{ getAgent(r, agentType)!.score_delta >= 0 ? "+" : "" }}{{ getAgent(r, agentType)!.score_delta }}
                      </span>
                    </div>
                  </template>
                  <template v-else>
                    <span class="muted">—</span>
                  </template>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </template>

      <div v-else class="empty-state">
        从左侧列表勾选 2-5 个已完成的分析报告，然后点击"开始对比"。
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { ElMessage } from "element-plus";

import { compareReports, getAnalysisReport, listAnalysisTasks } from "../api/client";
import AgentInsightCard from "../components/AgentInsightCard.vue";
import PricePulseChart from "../components/PricePulseChart.vue";
import type { AnalysisReport, AnalysisTask, ComparisonReport, ComparisonAgentSummary } from "../types";

const tasks = ref<AnalysisTask[]>([]);
const selectedTask = ref<AnalysisTask | null>(null);
const selectedReport = ref<AnalysisReport | null>(null);
const keyword = ref("");
const statusFilter = ref("");
const historyLoading = ref(false);
const reportLoading = ref(false);

// 对比模式
const compareMode = ref(false);
const selectedIds = ref<string[]>([]);
const comparisonData = ref<ComparisonReport[]>([]);
const compareLoading = ref(false);

const agentLabelMap: Record<string, string> = {
  market_analyst: "市场分析师",
  fundamental_analyst: "基本面分析师",
  news_analyst: "新闻分析师",
  index_analyst: "大盘分析师",
  sector_analyst: "板块分析师",
};

const filteredTasks = computed(() =>
  tasks.value.filter((task) => {
    const matchKeyword = !keyword.value || task.symbol.toLowerCase().includes(keyword.value.toLowerCase());
    const matchStatus = !statusFilter.value || task.status === statusFilter.value;
    return matchKeyword && matchStatus;
  })
);

const allAgentTypes = computed(() => {
  const types = new Set<string>();
  for (const r of comparisonData.value) {
    for (const a of r.agent_reports) {
      types.add(a.agent_type);
    }
  }
  return [...types];
});

function toggleCompareMode() {
  compareMode.value = !compareMode.value;
  if (!compareMode.value) {
    selectedIds.value = [];
    comparisonData.value = [];
  }
}

function toggleSelection(taskId: string, checked: boolean) {
  if (checked) {
    if (selectedIds.value.length < 5) {
      selectedIds.value.push(taskId);
    }
  } else {
    selectedIds.value = selectedIds.value.filter((id) => id !== taskId);
  }
}

function clearComparison() {
  comparisonData.value = [];
  selectedIds.value = [];
}

async function doCompare() {
  if (selectedIds.value.length < 2) {
    ElMessage.warning("至少选择两个报告进行对比。");
    return;
  }
  compareLoading.value = true;
  try {
    comparisonData.value = await compareReports(selectedIds.value);
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "对比加载失败");
  } finally {
    compareLoading.value = false;
  }
}

function getAgent(report: ComparisonReport, agentType: string): ComparisonAgentSummary | undefined {
  return report.agent_reports.find((a) => a.agent_type === agentType);
}

function formatDate(dateStr: string) {
  const d = new Date(dateStr);
  return `${d.getMonth() + 1}/${d.getDate()} ${d.getHours().toString().padStart(2, "0")}:${d.getMinutes().toString().padStart(2, "0")}`;
}

function depthLabel(depth: string) {
  return { fast: "快速", standard: "标准", deep: "深度" }[depth] || depth;
}

function scoreClass(score: number) {
  if (score >= 70) return "score--good";
  if (score >= 40) return "score--neutral";
  return "score--bad";
}

function deltaClass(delta: number) {
  if (delta > 0) return "delta--positive";
  if (delta < 0) return "delta--negative";
  return "";
}

async function loadHistory() {
  historyLoading.value = true;
  try {
    tasks.value = await listAnalysisTasks();
  } catch (error) {
    tasks.value = [];
    ElMessage.error(error instanceof Error ? error.message : "历史记录加载失败");
  } finally {
    historyLoading.value = false;
  }
}

function handleRowClick(task: AnalysisTask) {
  if (compareMode.value) return; // 对比模式下通过 checkbox 操作
  selectTask(task);
}

async function selectTask(task: AnalysisTask) {
  selectedTask.value = task;
  if (task.status === "completed" || task.status === "completed_with_warnings") {
    reportLoading.value = true;
    try {
      selectedReport.value = await getAnalysisReport(task.id);
    } catch (error) {
      selectedReport.value = null;
      ElMessage.error(error instanceof Error ? error.message : "报告加载失败");
    } finally {
      reportLoading.value = false;
    }
  } else {
    reportLoading.value = false;
    selectedReport.value = null;
  }
}

onMounted(loadHistory);
</script>
