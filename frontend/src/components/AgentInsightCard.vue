<template>
  <article class="agent-card">
    <div class="agent-card__header">
      <div>
        <p class="eyebrow">{{ agentLabelMap[report.agent_type] || report.agent_type }}</p>
        <h4>{{ report.summary }}</h4>
      </div>
      <StatusBadge :label="`置信度 ${report.confidence}`" :tone="report.confidence >= 80 ? 'good' : 'warn'" />
    </div>

    <div class="agent-card__metrics">
      <span>得分影响 {{ report.score_delta >= 0 ? `+${report.score_delta}` : report.score_delta }}</span>
      <span>{{ report.provider }} / {{ report.model }}</span>
    </div>

    <div class="agent-card__columns">
      <div>
        <p class="mini-title">看多要点</p>
        <ul>
          <li v-for="item in report.positives" :key="item">{{ item }}</li>
        </ul>
      </div>
      <div>
        <p class="mini-title">风险提醒</p>
        <ul>
          <li v-for="item in report.risks" :key="item">{{ item }}</li>
        </ul>
      </div>
    </div>
  </article>
</template>

<script setup lang="ts">
import StatusBadge from "./StatusBadge.vue";
import type { AgentReport } from "../types";

defineProps<{
  report: AgentReport;
}>();

const agentLabelMap: Record<string, string> = {
  market_analyst: "市场分析师",
  fundamental_analyst: "基本面分析师",
  news_analyst: "新闻分析师",
  index_analyst: "大盘分析师",
  sector_analyst: "板块分析师"
};
</script>
