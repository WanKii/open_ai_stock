<template>
  <el-drawer
    :model-value="visible"
    title="任务详情"
    size="480px"
    direction="rtl"
    @close="$emit('update:visible', false)"
  >
    <template v-if="job">
      <el-descriptions :column="1" border>
        <el-descriptions-item label="任务 ID">
          <code>{{ job.id }}</code>
        </el-descriptions-item>
        <el-descriptions-item label="任务类型">{{ jobTypeLabel(job.job_type) }}</el-descriptions-item>
        <el-descriptions-item label="数据源">{{ job.source }}</el-descriptions-item>
        <el-descriptions-item label="范围">{{ job.scope }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="statusType(job.status)" size="small">{{ statusLabel(job.status) }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="创建时间">{{ fmtDate(job.created_at) }}</el-descriptions-item>
        <el-descriptions-item label="开始时间">{{ fmtDate(job.started_at) }}</el-descriptions-item>
        <el-descriptions-item label="完成时间">{{ fmtDate(job.finished_at) }}</el-descriptions-item>
        <el-descriptions-item v-if="job.finished_at && job.started_at" label="耗时">
          {{ elapsed }}
        </el-descriptions-item>
      </el-descriptions>

      <!-- Progress section -->
      <el-divider content-position="left">进度</el-divider>
      <div v-if="job.total_items > 0" class="progress-section">
        <el-progress
          :percentage="pct"
          :stroke-width="18"
          :format="() => `${job!.completed_items} / ${job!.total_items}`"
          style="margin-bottom: 12px"
        />
        <el-row :gutter="12">
          <el-col :span="8">
            <el-statistic title="成功" :value="job.completed_items - job.error_items - job.skipped_items">
              <template #suffix>
                <span class="stat-total">/ {{ job.total_items }}</span>
              </template>
            </el-statistic>
          </el-col>
          <el-col :span="8">
            <el-statistic title="失败" :value="job.error_items" class="error-stat" />
          </el-col>
          <el-col :span="8">
            <el-statistic title="跳过" :value="job.skipped_items" class="skip-stat" />
          </el-col>
        </el-row>
        <div v-if="job.current_item && job.status === 'running'" class="current-item-box">
          正在同步: <strong>{{ job.current_item }}</strong>
        </div>
      </div>
      <div v-else class="muted">暂无进度信息</div>

      <!-- Result summary -->
      <template v-if="job.result_summary">
        <el-divider content-position="left">执行结果</el-divider>
        <div class="result-box">{{ job.result_summary }}</div>
      </template>

      <!-- Params -->
      <template v-if="job.params && Object.keys(job.params).length > 0">
        <el-divider content-position="left">任务参数</el-divider>
        <el-descriptions :column="1" border size="small">
          <el-descriptions-item v-for="(val, key) in job.params" :key="key" :label="paramLabel(String(key))">
            <template v-if="Array.isArray(val)">
              <el-tag v-for="v in val.slice(0, 10)" :key="String(v)" size="small" style="margin: 2px">{{ v }}</el-tag>
              <span v-if="val.length > 10" class="muted">... 共 {{ val.length }} 项</span>
            </template>
            <span v-else>{{ val }}</span>
          </el-descriptions-item>
        </el-descriptions>
      </template>
    </template>
  </el-drawer>
</template>

<script setup lang="ts">
import { computed } from "vue";
import type { SyncJob } from "../types";

const props = defineProps<{ visible: boolean; job: SyncJob | null }>();
defineEmits<{ "update:visible": [val: boolean] }>();

const pct = computed(() => {
  if (!props.job || props.job.total_items === 0) return 0;
  return Math.round((props.job.completed_items / props.job.total_items) * 100);
});

const elapsed = computed(() => {
  if (!props.job?.started_at || !props.job?.finished_at) return "—";
  const start = new Date(props.job.started_at).getTime();
  const end = new Date(props.job.finished_at).getTime();
  const sec = Math.round((end - start) / 1000);
  if (sec < 60) return `${sec} 秒`;
  const min = Math.floor(sec / 60);
  const remSec = sec % 60;
  if (min < 60) return `${min} 分 ${remSec} 秒`;
  const hr = Math.floor(min / 60);
  return `${hr} 时 ${min % 60} 分`;
});

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
  const map: Record<string, string> = {
    queued: "排队中", running: "同步中", completed: "已完成",
    completed_with_warnings: "部分完成", failed: "失败", cancelled: "已取消",
  };
  return map[status] || status;
}
function fmtDate(dt: string | null | undefined) {
  if (!dt) return "—";
  return dt.replace("T", " ").slice(0, 19);
}
function paramLabel(key: string) {
  const map: Record<string, string> = {
    symbols: "股票代码", sync_mode: "同步模式", max_workers: "并发数",
    days: "天数", periods: "期数", news_count: "新闻条数",
  };
  return map[key] || key;
}
</script>

<style scoped>
.progress-section {
  padding: 8px 0;
}
.stat-total {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.error-stat :deep(.el-statistic__number) {
  color: var(--el-color-danger);
}
.skip-stat :deep(.el-statistic__number) {
  color: var(--el-color-warning);
}
.current-item-box {
  margin-top: 12px;
  padding: 8px 12px;
  background: var(--el-fill-color-light);
  border-radius: 4px;
  font-size: 13px;
}
.result-box {
  padding: 12px;
  background: var(--el-fill-color-light);
  border-radius: 4px;
  font-size: 13px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-all;
}
.muted {
  color: var(--el-text-color-placeholder);
  font-size: 13px;
}
</style>
