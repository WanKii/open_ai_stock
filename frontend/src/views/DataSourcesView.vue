<template>
  <div class="workspace-grid workspace-grid--sources">
    <section class="panel">
      <div class="panel__header">
        <div>
          <p class="eyebrow">SOURCE MATRIX</p>
          <h3>数据源状态</h3>
        </div>
        <el-button text @click="loadSourceData">刷新</el-button>
      </div>

      <template v-if="loading">
        <div class="skeleton-grid" style="grid-template-columns: repeat(auto-fit, minmax(280px, 1fr))">
          <div v-for="i in 3" :key="i" class="skeleton-card skeleton-card--tall" />
        </div>
      </template>
      <div v-else class="config-grid">
        <article v-for="source in statuses" :key="source.source" class="config-card">
          <div class="config-card__header">
            <div>
              <p class="eyebrow">{{ source.source.toUpperCase() }}</p>
              <h4>优先级 {{ source.priority }}</h4>
            </div>
            <StatusBadge
              :label="source.status"
              :tone="source.status === 'online' ? 'good' : source.status === 'missing_token' ? 'warn' : 'neutral'"
            />
          </div>

          <p class="muted">{{ source.note }}</p>
          <div class="cap-list">
            <span v-for="cap in source.supports" :key="cap">{{ cap }}</span>
          </div>

          <div class="sync-actions">
            <el-button
              size="small"
              :loading="isSubmitting(source.source, 'health_check')"
              :disabled="isJobLocked(source.source, 'health_check')"
              @click="createJob(source.source, 'health_check')"
            >
              接口校验
            </el-button>
            <el-button
              size="small"
              :loading="isSubmitting(source.source, 'symbol_sync')"
              :disabled="isJobLocked(source.source, 'symbol_sync')"
              @click="createJob(source.source, 'symbol_sync')"
            >
              基本信息
            </el-button>
            <el-button
              size="small"
              :loading="isSubmitting(source.source, 'history_sync')"
              :disabled="isJobLocked(source.source, 'history_sync')"
              @click="createJob(source.source, 'history_sync')"
            >
              历史数据
            </el-button>
            <el-button
              size="small"
              :loading="isSubmitting(source.source, 'financial_sync')"
              :disabled="isJobLocked(source.source, 'financial_sync')"
              @click="createJob(source.source, 'financial_sync')"
            >
              财务数据
            </el-button>
            <el-button
              size="small"
              :loading="isSubmitting(source.source, 'news_sync')"
              :disabled="isJobLocked(source.source, 'news_sync')"
              @click="createJob(source.source, 'news_sync')"
            >
              新闻数据
            </el-button>
          </div>
        </article>
      </div>
    </section>

    <section class="panel">
      <div class="panel__header">
        <div>
          <p class="eyebrow">SYNC JOBS</p>
          <h3>同步任务</h3>
        </div>
      </div>

      <template v-if="loading">
        <div class="skeleton-grid">
          <div v-for="i in 4" :key="i" class="skeleton-card skeleton-card--short" />
        </div>
      </template>
      <el-table v-else :data="jobs" height="520">
        <el-table-column prop="source" label="数据源" min-width="110" />
        <el-table-column prop="job_type" label="任务类型" min-width="140" />
        <el-table-column prop="status" label="状态" min-width="100" />
        <el-table-column prop="scope" label="范围" min-width="90" />
        <el-table-column prop="result_summary" label="结果摘要" min-width="280" />
      </el-table>
    </section>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";

import { createSyncJob, getSourceStatuses, listSyncJobs } from "../api/client";
import StatusBadge from "../components/StatusBadge.vue";
import type { DataSourceStatus, SyncJob } from "../types";
import { useWorkspaceStore } from "../stores/workspace";

const statuses = ref<DataSourceStatus[]>([]);
const jobs = ref<SyncJob[]>([]);
const loading = ref(false);
const submittingJobs = reactive<Record<string, boolean>>({});
const workspaceStore = useWorkspaceStore();

async function loadSourceData() {
  loading.value = true;
  try {
    const [statusList, jobList] = await Promise.all([getSourceStatuses(), listSyncJobs()]);
    statuses.value = statusList;
    jobs.value = jobList;
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "数据源状态加载失败");
  } finally {
    loading.value = false;
  }
}

function getJobKey(source: string, jobType: string) {
  return `${source}:${jobType}`;
}

function isSubmitting(source: string, jobType: string) {
  return Boolean(submittingJobs[getJobKey(source, jobType)]);
}

function isJobLocked(source: string, jobType: string) {
  return (
    isSubmitting(source, jobType) ||
    jobs.value.some(
      (job) =>
        job.source === source &&
        job.job_type === jobType &&
        (job.status === "queued" || job.status === "running")
    )
  );
}

async function createJob(source: string, jobType: string) {
  if (isJobLocked(source, jobType)) {
    ElMessage.warning("相同数据源的同类同步任务正在执行，请稍后再试。");
    return;
  }

  const jobKey = getJobKey(source, jobType);
  submittingJobs[jobKey] = true;
  try {
    await createSyncJob({
      source,
      job_type: jobType,
      scope: "all",
      params: {}
    });
    await loadSourceData();
    await workspaceStore.refreshOverview();
    ElMessage.success(`${source} ${jobType} 已加入队列。`);
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "同步任务提交失败");
  } finally {
    delete submittingJobs[jobKey];
  }
}

onMounted(loadSourceData);
</script>
