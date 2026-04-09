<template>
  <div class="workspace-grid workspace-grid--history">
    <section class="panel">
      <div class="panel__header">
        <div>
          <p class="eyebrow">ARCHIVE</p>
          <h3>历史分析记录</h3>
        </div>
        <el-button text @click="loadHistory">刷新</el-button>
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

      <el-table :data="filteredTasks" height="540" @row-click="selectTask">
        <el-table-column prop="symbol" label="股票代码" min-width="140" />
        <el-table-column prop="depth" label="深度" min-width="90" />
        <el-table-column prop="status" label="状态" min-width="120" />
        <el-table-column prop="created_at" label="创建时间" min-width="180" />
      </el-table>
    </section>

    <section class="panel">
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
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import { getAnalysisReport, listAnalysisTasks } from "../api/client";
import AgentInsightCard from "../components/AgentInsightCard.vue";
import PricePulseChart from "../components/PricePulseChart.vue";
import type { AnalysisReport, AnalysisTask } from "../types";

const tasks = ref<AnalysisTask[]>([]);
const selectedTask = ref<AnalysisTask | null>(null);
const selectedReport = ref<AnalysisReport | null>(null);
const keyword = ref("");
const statusFilter = ref("");

const filteredTasks = computed(() =>
  tasks.value.filter((task) => {
    const matchKeyword = !keyword.value || task.symbol.toLowerCase().includes(keyword.value.toLowerCase());
    const matchStatus = !statusFilter.value || task.status === statusFilter.value;
    return matchKeyword && matchStatus;
  })
);

async function loadHistory() {
  tasks.value = await listAnalysisTasks();
}

async function selectTask(task: AnalysisTask) {
  selectedTask.value = task;
  if (task.status === "completed" || task.status === "completed_with_warnings") {
    selectedReport.value = await getAnalysisReport(task.id);
  } else {
    selectedReport.value = null;
  }
}

onMounted(loadHistory);
</script>
