<template>
  <el-drawer
    :model-value="visible"
    title="同步任务队列"
    size="60%"
    direction="rtl"
    @close="$emit('update:visible', false)"
  >
    <div class="drawer-toolbar">
      <el-button size="small" @click="refresh">刷新</el-button>
      <el-switch v-model="autoRefresh" active-text="自动刷新" />
    </div>
    <el-table :data="jobs" height="calc(100vh - 220px)" stripe border>
      <el-table-column prop="source" label="数据源" width="110" />
      <el-table-column prop="job_type" label="任务类型" width="140" />
      <el-table-column prop="status" label="状态" width="110">
        <template #default="{ row }">
          <el-tag :type="statusType(row.status)">{{ statusLabel(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="scope" label="范围" width="90" />
      <el-table-column prop="result_summary" label="结果摘要" min-width="220" />
      <el-table-column prop="created_at" label="创建时间" width="160">
        <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
      </el-table-column>
      <el-table-column prop="finished_at" label="完成时间" width="160">
        <template #default="{ row }">{{ formatDate(row.finished_at) }}</template>
      </el-table-column>
    </el-table>
  </el-drawer>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted } from "vue";
import { listSyncJobs } from "../api/client";
import type { SyncJob } from "../types";

const props = defineProps<{ visible: boolean }>();
defineEmits<{ "update:visible": [val: boolean] }>();

const jobs = ref<SyncJob[]>([]);
const autoRefresh = ref(true);
let timer: number | null = null;

function statusType(status: string) {
  if (status === "completed" || status === "completed_with_warnings") return "success";
  if (status === "running" || status === "queued") return "info";
  if (status === "failed" || status === "cancelled") return "danger";
  return "";
}
function statusLabel(status: string) {
  switch (status) {
    case "queued": return "排队中";
    case "running": return "同步中";
    case "completed": return "已完成";
    case "completed_with_warnings": return "警告完成";
    case "failed": return "失败";
    case "cancelled": return "已取消";
    default: return status;
  }
}
function formatDate(dt: string | null | undefined) {
  if (!dt) return "—";
  return dt.replace("T", " ").slice(0, 19);
}
async function refresh() {
  jobs.value = await listSyncJobs();
}

watch(() => props.visible, (val) => {
  if (val) {
    refresh();
    if (autoRefresh.value) startTimer();
  } else {
    stopTimer();
  }
});

watch(autoRefresh, (val) => {
  if (val && props.visible) startTimer();
  else stopTimer();
});

function startTimer() {
  stopTimer();
  timer = window.setInterval(refresh, 2000);
}
function stopTimer() {
  if (timer) {
    clearInterval(timer);
    timer = null;
  }
}
onMounted(() => { if (props.visible && autoRefresh.value) startTimer(); });
onUnmounted(stopTimer);
</script>

<style scoped>
.drawer-toolbar {
  display: flex;
  gap: 18px;
  align-items: center;
  margin-bottom: 16px;
}
</style>
