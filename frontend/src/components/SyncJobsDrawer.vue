<template>
  <el-drawer
    :model-value="visible"
    title="同步任务队列"
    size="68%"
    direction="rtl"
    @close="$emit('update:visible', false)"
  >
    <div class="drawer-toolbar">
      <el-button size="small" @click="refresh">刷新</el-button>
      <el-switch v-model="useSSE" active-text="实时推送" inactive-text="轮询" />
      <el-switch v-if="!useSSE" v-model="autoRefresh" active-text="自动刷新" />
      <span v-if="sseConnected" class="sse-badge">● SSE 已连接</span>
    </div>
    <el-table :data="jobs" height="calc(100vh - 220px)" stripe border row-key="id" highlight-current-row @row-click="openDetail">
      <el-table-column prop="source" label="数据源" width="100" />
      <el-table-column prop="job_type" label="任务类型" width="130">
        <template #default="{ row }">{{ jobTypeLabel(row.job_type) }}</template>
      </el-table-column>
      <el-table-column prop="status" label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="statusType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="进度" min-width="240">
        <template #default="{ row }">
          <template v-if="row.status === 'running' && row.total_items > 0">
            <el-progress
              :percentage="Math.round((row.completed_items / row.total_items) * 100)"
              :stroke-width="14"
              :format="() => `${row.completed_items}/${row.total_items}`"
              style="margin-bottom: 4px"
            />
            <div class="progress-detail">
              <span v-if="row.current_item" class="current-item">
                正在同步: <strong>{{ row.current_item }}</strong>
              </span>
              <span class="progress-stats">
                <el-tag v-if="row.error_items > 0" type="danger" size="small" effect="plain">
                  失败 {{ row.error_items }}
                </el-tag>
                <el-tag v-if="row.skipped_items > 0" type="warning" size="small" effect="plain">
                  跳过 {{ row.skipped_items }}
                </el-tag>
              </span>
            </div>
          </template>
          <template v-else-if="row.status === 'running'">
            <el-progress :percentage="50" :indeterminate="true" :stroke-width="14" />
          </template>
          <template v-else-if="row.result_summary">
            <span class="result-summary">{{ row.result_summary }}</span>
          </template>
          <template v-else>
            <span class="muted">—</span>
          </template>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="140" fixed="right">
        <template #default="{ row }">
          <template v-if="row.status === 'running'">
            <el-button size="small" text type="warning" @click="handlePause(row.id)">暂停</el-button>
            <el-button size="small" text type="danger" @click="handleCancel(row.id)">取消</el-button>
          </template>
          <template v-else-if="row.status === 'queued'">
            <el-button size="small" text type="danger" @click="handleCancel(row.id)">取消</el-button>
          </template>
          <template v-else>
            <span class="muted">—</span>
          </template>
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="创建时间" width="155">
        <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
      </el-table-column>
      <el-table-column prop="finished_at" label="完成时间" width="155">
        <template #default="{ row }">{{ formatDate(row.finished_at) }}</template>
      </el-table-column>
    </el-table>
    <SyncJobDetailDrawer v-model:visible="detailVisible" :job="selectedJob" />
  </el-drawer>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import {
  listSyncJobs,
  cancelSyncJob,
  pauseSyncJob,
  resumeSyncJob,
  getSyncProgressStreamUrl,
} from "../api/client";
import type { SyncJob } from "../types";
import SyncJobDetailDrawer from "./SyncJobDetailDrawer.vue";

const props = defineProps<{ visible: boolean }>();
defineEmits<{ "update:visible": [val: boolean] }>();

const detailVisible = ref(false);
const selectedJob = ref<SyncJob | null>(null);

function openDetail(row: SyncJob) {
  selectedJob.value = row;
  detailVisible.value = true;
}

const jobs = ref<SyncJob[]>([]);
const autoRefresh = ref(true);
const useSSE = ref(true);
const sseConnected = ref(false);
let timer: number | null = null;
let eventSource: EventSource | null = null;

function jobTypeLabel(jt: string) {
  const map: Record<string, string> = {
    health_check: "连接检测",
    symbol_sync: "股票列表",
    history_sync: "历史行情",
    financial_sync: "财务数据",
    news_sync: "新闻公告",
  };
  return map[jt] || jt;
}

function statusType(status: string) {
  if (status === "completed") return "success";
  if (status === "completed_with_warnings") return "warning";
  if (status === "running" || status === "queued") return "info";
  if (status === "failed" || status === "cancelled") return "danger";
  return "";
}
function statusLabel(status: string) {
  switch (status) {
    case "queued": return "排队中";
    case "running": return "同步中";
    case "completed": return "已完成";
    case "completed_with_warnings": return "部分完成";
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

// --- SSE ---
function startSSE() {
  stopSSE();
  const url = getSyncProgressStreamUrl();
  eventSource = new EventSource(url);
  eventSource.onopen = () => { sseConnected.value = true; };
  eventSource.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      // Update matching job in the list
      const idx = jobs.value.findIndex((j) => j.id === data.id);
      if (idx >= 0) {
        const job = jobs.value[idx];
        if (data.status) job.status = data.status;
        if (data.total_items != null) job.total_items = data.total_items;
        if (data.completed_items != null) job.completed_items = data.completed_items;
        if (data.error_items != null) job.error_items = data.error_items;
        if (data.skipped_items != null) job.skipped_items = data.skipped_items;
        if (data.current_item !== undefined) job.current_item = data.current_item;
        if (data.result_summary !== undefined) job.result_summary = data.result_summary;
      }
      if (data.finished) {
        // Refresh full list to pick up final state
        refresh();
      }
    } catch { /* ignore malformed */ }
  };
  eventSource.onerror = () => {
    sseConnected.value = false;
    // Reconnect after a delay
    stopSSE();
    setTimeout(() => {
      if (props.visible && useSSE.value) startSSE();
    }, 3000);
  };
}

function stopSSE() {
  if (eventSource) {
    eventSource.close();
    eventSource = null;
  }
  sseConnected.value = false;
}

// --- Control actions ---
async function handleCancel(jobId: string) {
  try {
    await ElMessageBox.confirm("确定取消此同步任务？", "取消确认", { type: "warning" });
    await cancelSyncJob(jobId);
    ElMessage.success("任务已取消");
    refresh();
  } catch { /* user cancelled dialog */ }
}

async function handlePause(jobId: string) {
  try {
    await pauseSyncJob(jobId);
    ElMessage.info("任务已暂停");
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : "暂停失败");
  }
}

// --- Lifecycle ---
watch(() => props.visible, (val) => {
  if (val) {
    refresh();
    if (useSSE.value) {
      startSSE();
    } else if (autoRefresh.value) {
      startTimer();
    }
  } else {
    stopTimer();
    stopSSE();
  }
});

watch(useSSE, (val) => {
  if (val && props.visible) {
    stopTimer();
    startSSE();
    // Still do a periodic full refresh for new jobs
    timer = window.setInterval(refresh, 5000);
  } else {
    stopSSE();
    if (autoRefresh.value && props.visible) startTimer();
  }
});

watch(autoRefresh, (val) => {
  if (!useSSE.value) {
    if (val && props.visible) startTimer();
    else stopTimer();
  }
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
onMounted(() => {
  if (props.visible) {
    if (useSSE.value) startSSE();
    else if (autoRefresh.value) startTimer();
  }
});
onUnmounted(() => { stopTimer(); stopSSE(); });
</script>

<style scoped>
.drawer-toolbar {
  display: flex;
  gap: 18px;
  align-items: center;
  margin-bottom: 16px;
}

.sse-badge {
  font-size: 12px;
  color: var(--el-color-success);
}

.progress-detail {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
  margin-top: 2px;
}

.current-item {
  color: var(--el-text-color-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 160px;
}

.progress-stats {
  display: flex;
  gap: 4px;
}

.result-summary {
  font-size: 12px;
  color: var(--el-text-color-regular);
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.muted {
  color: var(--el-text-color-placeholder);
}
</style>
