<template>
  <div class="sources-layout">
    <!-- 数据质量仪表板 -->
    <section class="panel quality-panel">
      <div class="panel__header">
        <div>
          <p class="eyebrow">DATA QUALITY</p>
          <h3>数据质量仪表板</h3>
        </div>
        <el-button text @click="loadQuality">刷新</el-button>
      </div>

      <template v-if="qualityLoading">
        <div class="skeleton-grid" style="grid-template-columns: repeat(auto-fit, minmax(160px, 1fr))">
          <div v-for="i in 4" :key="i" class="skeleton-card skeleton-card--short" />
        </div>
      </template>
      <template v-else-if="quality">
        <!-- 总览指标 -->
        <div class="quality-metrics">
          <div class="metric-block">
            <span>已入库股票数</span>
            <strong>{{ quality.total_symbols }}</strong>
          </div>
          <div class="metric-block">
            <span>数据表数量</span>
            <strong>{{ quality.tables.length }}</strong>
          </div>
          <div class="metric-block">
            <span>总记录数</span>
            <strong>{{ totalRows.toLocaleString() }}</strong>
          </div>
          <div class="metric-block">
            <span>数据源覆盖</span>
            <strong>{{ allSources.length }}</strong>
          </div>
        </div>

        <!-- 各表详情 -->
        <div class="quality-table-grid">
          <article
            v-for="t in quality.tables"
            :key="t.table_name"
            class="quality-card"
          >
            <div class="quality-card__header">
              <h4>{{ tableLabel(t.table_name) }}</h4>
              <StatusBadge
                :label="t.row_count > 0 ? '有数据' : '空'"
                :tone="t.row_count > 0 ? 'good' : 'neutral'"
              />
            </div>
            <div class="quality-card__stats">
              <div>
                <span>行数</span>
                <strong>{{ t.row_count.toLocaleString() }}</strong>
              </div>
              <div>
                <span>覆盖标的</span>
                <strong>{{ t.distinct_symbols }}</strong>
              </div>
              <div>
                <span>最新日期</span>
                <strong>{{ t.latest_date ? formatQualityDate(t.latest_date) : "—" }}</strong>
              </div>
              <div>
                <span>最早日期</span>
                <strong>{{ t.oldest_date ? formatQualityDate(t.oldest_date) : "—" }}</strong>
              </div>
            </div>
            <div v-if="t.sources.length" class="cap-list">
              <span v-for="s in t.sources" :key="s">{{ s }}</span>
            </div>
            <!-- 覆盖率进度条 -->
            <div v-if="quality.total_symbols > 0 && isSymbolTable(t.table_name)" class="quality-coverage">
              <div class="quality-coverage__bar">
                <div
                  class="quality-coverage__fill"
                  :style="{ width: coveragePercent(t) + '%' }"
                />
              </div>
              <span class="quality-coverage__label">覆盖率 {{ coveragePercent(t) }}%</span>
            </div>
          </article>
        </div>
      </template>
    </section>

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
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";

import { createSyncJob, getDataQuality, getSourceStatuses, listSyncJobs } from "../api/client";
import StatusBadge from "../components/StatusBadge.vue";
import type { DataQualityOverview, DataSourceStatus, SyncJob, TableQualityStat } from "../types";
import { useWorkspaceStore } from "../stores/workspace";

const statuses = ref<DataSourceStatus[]>([]);
const jobs = ref<SyncJob[]>([]);
const loading = ref(false);
const submittingJobs = reactive<Record<string, boolean>>({});
const workspaceStore = useWorkspaceStore();

// 数据质量
const quality = ref<DataQualityOverview | null>(null);
const qualityLoading = ref(false);

const totalRows = computed(() =>
  quality.value ? quality.value.tables.reduce((sum, t) => sum + t.row_count, 0) : 0
);

const allSources = computed(() => {
  if (!quality.value) return [];
  const s = new Set<string>();
  for (const t of quality.value.tables) {
    for (const src of t.sources) s.add(src);
  }
  return [...s];
});

const tableLabelMap: Record<string, string> = {
  symbol_master: "股票主表",
  company_profile: "公司概况",
  daily_quotes: "日线行情",
  financial_reports: "财务报告",
  news_items: "新闻资讯",
  announcements: "公告信息",
  index_daily: "指数日线",
  sector_daily: "板块日线",
};

const symbolTables = new Set([
  "daily_quotes", "financial_reports", "news_items", "announcements",
]);

function tableLabel(name: string) {
  return tableLabelMap[name] || name;
}

function isSymbolTable(name: string) {
  return symbolTables.has(name);
}

function coveragePercent(t: TableQualityStat) {
  if (!quality.value || quality.value.total_symbols === 0) return 0;
  return Math.min(100, Math.round((t.distinct_symbols / quality.value.total_symbols) * 100));
}

function formatQualityDate(dateStr: string) {
  // Trim to date portion
  return dateStr.length > 10 ? dateStr.substring(0, 10) : dateStr;
}

async function loadQuality() {
  qualityLoading.value = true;
  try {
    quality.value = await getDataQuality();
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "数据质量加载失败");
  } finally {
    qualityLoading.value = false;
  }
}

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

onMounted(() => {
  loadSourceData();
  loadQuality();
});
</script>
