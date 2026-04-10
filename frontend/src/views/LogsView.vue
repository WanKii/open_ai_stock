<template>
  <div class="panel">
    <div class="panel__header">
      <div>
        <p class="eyebrow">TRACE CENTER</p>
        <h3>日志</h3>
      </div>
      <el-button text @click="loadLogsData">刷新</el-button>
    </div>

    <div class="toolbar">
      <el-select v-model="kind" placeholder="日志类型">
        <el-option label="全部" value="all" />
        <el-option label="操作日志" value="operation" />
        <el-option label="系统日志" value="system" />
      </el-select>
      <el-select v-model="level" clearable placeholder="级别">
        <el-option label="INFO" value="INFO" />
        <el-option label="WARNING" value="WARNING" />
        <el-option label="ERROR" value="ERROR" />
      </el-select>
      <el-input v-model="taskId" clearable placeholder="任务 ID" />
      <el-button type="primary" @click="loadLogsData">查询</el-button>
    </div>

    <template v-if="loading">
      <div class="skeleton-grid">
        <div v-for="i in 8" :key="i" class="skeleton-card skeleton-card--short" />
      </div>
    </template>
    <div v-else class="log-list">
      <article v-for="entry in logs" :key="`${entry.module}-${entry.id}-${entry.created_at}`" class="log-item">
        <div class="log-item__meta">
          <StatusBadge :label="entry.level" :tone="entry.level === 'ERROR' ? 'danger' : entry.level === 'WARNING' ? 'warn' : 'good'" />
          <span>{{ entry.module }}</span>
          <span v-if="entry.action">{{ entry.action }}</span>
          <span>{{ formatDate(entry.created_at) }}</span>
        </div>
        <p>{{ entry.message }}</p>
        <small v-if="entry.task_id">任务 ID: {{ entry.task_id }}</small>
      </article>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { ElMessage } from "element-plus";

import { listLogs } from "../api/client";
import StatusBadge from "../components/StatusBadge.vue";
import type { LogEntry } from "../types";

const logs = ref<LogEntry[]>([]);
const kind = ref<"all" | "operation" | "system">("all");
const level = ref("");
const taskId = ref("");
const loading = ref(false);

function formatDate(value: string) {
  return new Date(value).toLocaleString("zh-CN");
}

async function loadLogsData() {
  loading.value = true;
  try {
    logs.value = await listLogs({
      kind: kind.value,
      level: level.value || undefined,
      task_id: taskId.value || undefined,
      limit: 120
    });
  } catch (error) {
    logs.value = [];
    ElMessage.error(error instanceof Error ? error.message : "日志加载失败");
  } finally {
    loading.value = false;
  }
}

onMounted(loadLogsData);
</script>
