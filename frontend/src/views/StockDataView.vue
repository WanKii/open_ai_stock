<template>
  <div class="stock-data-page">
    <section class="panel">
      <div class="panel__header">
        <div>
          <p class="eyebrow">STOCK DATA MANAGER</p>
          <h3>股票数据管理</h3>
        </div>
        <div class="panel__actions">
          <el-input
            v-model="searchText"
            placeholder="搜索代码或名称"
            clearable
            style="width: 260px"
            @clear="handleSearch"
            @keyup.enter="handleSearch"
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
          <el-button @click="handleSearch">搜索</el-button>
          <el-button text @click="refresh">刷新</el-button>
          <el-dropdown @command="handleFullSync">
            <el-button type="primary">
              全量同步<el-icon class="el-icon--right"><ArrowDown /></el-icon>
            </el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item v-for="src in SOURCES" :key="src" :command="src">
                  {{ src.toUpperCase() }}
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
          <el-button type="danger" plain @click="handleResetAll">清空数据</el-button>
        </div>
      </div>

      <el-table
        :data="stocks"
        row-key="symbol"
        :expand-row-keys="expandedKeys"
        @expand-change="handleExpand"
        stripe
      >
        <el-table-column type="expand">
          <template #default="{ row }">
            <div class="expand-content" v-loading="summaryLoading[row.symbol]">
              <div class="source-columns">
                <div v-for="src in SOURCES" :key="src" class="source-column">
                  <div class="source-column__header">
                    <strong>{{ src.toUpperCase() }}</strong>
                    <el-button
                      size="small"
                      type="primary"
                      plain
                      :loading="syncLoading[`${row.symbol}_${src}`]"
                      @click="handleSync(row.symbol, src)"
                    >
                      同步
                    </el-button>
                  </div>

                  <div class="data-type-cards">
                    <div v-for="dt in DATA_TYPES" :key="dt.key" class="data-type-card">
                      <div class="data-type-card__header">
                        <span class="data-type-card__label">{{ dt.label }}</span>
                      </div>

                      <template v-if="getSummary(row.symbol, src, dt.key)">
                        <div class="data-type-card__stats">
                          <span>条目: <strong>{{ getSummary(row.symbol, src, dt.key)!.record_count }}</strong></span>
                          <span>截止: <strong>{{ formatDate(getSummary(row.symbol, src, dt.key)!.latest_date) }}</strong></span>
                        </div>
                        <div class="data-type-card__actions">
                          <el-button size="small" text type="primary" @click="openDrawer(row.symbol, src, dt.key)">
                            查看
                          </el-button>
                          <el-button size="small" text type="primary" @click="downloadCSV(row.symbol, src, dt.key)">
                            下载
                          </el-button>
                          <el-popconfirm
                            title="确定删除这类数据？"
                            @confirm="handleDelete(row.symbol, src, dt.key)"
                          >
                            <template #reference>
                              <el-button size="small" text type="danger">删除</el-button>
                            </template>
                          </el-popconfirm>
                        </div>
                      </template>

                      <template v-else>
                        <span class="muted" style="font-size: 12px">暂无数据</span>
                      </template>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </template>
        </el-table-column>

        <el-table-column prop="symbol" label="代码" width="120" />
        <el-table-column prop="name" label="名称" min-width="140" />
        <el-table-column prop="exchange" label="交易所" width="100" />
        <el-table-column prop="industry" label="行业" min-width="120">
          <template #default="{ row }">{{ row.industry || "—" }}</template>
        </el-table-column>
        <el-table-column prop="area" label="地区" width="100">
          <template #default="{ row }">{{ row.area || "—" }}</template>
        </el-table-column>
        <el-table-column prop="listing_date" label="上市日期" width="120">
          <template #default="{ row }">{{ row.listing_date || "—" }}</template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="80" />
      </el-table>

      <div class="table-pagination">
        <el-pagination
          v-model:current-page="currentPage"
          :page-size="pageSize"
          :total="total"
          :page-sizes="[20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="handlePageSizeChange"
          @current-change="loadStocks"
        />
      </div>
    </section>

    <StockDataDrawer
      v-model:visible="drawerVisible"
      :symbol="drawerSymbol"
      :source="drawerSource"
      :data-type="drawerDataType"
    />

    <el-button
      class="sync-jobs-btn"
      type="primary"
      plain
      size="small"
      style="position: fixed; top: 38px; right: 48px; z-index: 1001"
      @click="syncJobsVisible = true"
    >
      同步任务
    </el-button>
    <SyncJobsDrawer v-model:visible="syncJobsVisible" />

    <!-- Full Sync Dialog -->
    <el-dialog v-model="fullSyncDialogVisible" title="全量同步配置" width="440px">
      <el-form label-width="90px">
        <el-form-item label="数据源">
          <el-tag>{{ fullSyncSource.toUpperCase() }}</el-tag>
        </el-form-item>
        <el-form-item label="同步模式">
          <el-radio-group v-model="fullSyncMode">
            <el-radio value="standard">标准 (1年)</el-radio>
            <el-radio value="full">全量 (10年)</el-radio>
            <el-radio value="incremental">增量 (30天)</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="并发数">
          <el-input-number v-model="fullSyncWorkers" :min="1" :max="8" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="fullSyncDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="fullSyncLoading" @click="confirmFullSync">
          开始同步
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { Search, ArrowDown } from "@element-plus/icons-vue";
import { ElMessage, ElMessageBox } from "element-plus";

import {
  createFullSync,
  deleteStockData,
  getStockDataDownloadUrl,
  getStockDataSummary,
  listStocks,
  resetAllData,
  syncStockBySource
} from "../api/client";
import StockDataDrawer from "../components/StockDataDrawer.vue";
import SyncJobsDrawer from "../components/SyncJobsDrawer.vue";
import type { DataTypeSummary, StockListItem } from "../types";

const SOURCES = ["akshare", "tushare", "baostock"] as const;

const DATA_TYPES = [
  { key: "daily_quotes", label: "日线" },
  { key: "financial_reports", label: "财务数据" },
  { key: "news_items", label: "新闻" },
  { key: "announcements", label: "公告" }
] as const;

const stocks = ref<StockListItem[]>([]);
const total = ref(0);
const currentPage = ref(1);
const pageSize = ref(50);
const searchText = ref("");
const expandedKeys = ref<string[]>([]);

const summaryCache = reactive<Record<string, DataTypeSummary[]>>({});
const summaryLoading = reactive<Record<string, boolean>>({});
const syncLoading = reactive<Record<string, boolean>>({});

const drawerVisible = ref(false);
const drawerSymbol = ref("");
const drawerSource = ref("");
const drawerDataType = ref("");
const syncJobsVisible = ref(false);

async function loadStocks() {
  const res = await listStocks(currentPage.value, pageSize.value, searchText.value || undefined);
  stocks.value = res.items;
  total.value = res.total;
}

function handleSearch() {
  currentPage.value = 1;
  expandedKeys.value = [];
  void loadStocks();
}

function handlePageSizeChange(val: number) {
  pageSize.value = val;
  currentPage.value = 1;
  void loadStocks();
}

function refresh() {
  expandedKeys.value = [];
  Object.keys(summaryCache).forEach((key) => delete summaryCache[key]);
  void loadStocks();
}

async function handleExpand(row: StockListItem, expanded: StockListItem[]) {
  const isExpanded = expanded.some((item) => item.symbol === row.symbol);
  expandedKeys.value = expanded.map((item) => item.symbol);

  if (isExpanded && !summaryCache[row.symbol]) {
    await loadSummary(row.symbol);
  }
}

async function loadSummary(symbol: string) {
  summaryLoading[symbol] = true;
  try {
    const res = await getStockDataSummary(symbol);
    summaryCache[symbol] = res.summaries;
  } catch {
    summaryCache[symbol] = [];
  } finally {
    summaryLoading[symbol] = false;
  }
}

function getSummary(symbol: string, source: string, dataType: string): DataTypeSummary | undefined {
  const list = summaryCache[symbol];
  if (!list) return undefined;
  return list.find((item) => item.source === source && item.data_type === dataType);
}

function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  return value.slice(0, 10);
}

function openDrawer(symbol: string, source: string, dataType: string) {
  drawerSymbol.value = symbol;
  drawerSource.value = source;
  drawerDataType.value = dataType;
  drawerVisible.value = true;
}

function downloadCSV(symbol: string, source: string, dataType: string) {
  const url = getStockDataDownloadUrl(symbol, source, dataType);
  window.open(url, "_blank");
}

async function handleDelete(symbol: string, source: string, dataType: string) {
  try {
    const res = await deleteStockData(symbol, source, dataType);
    ElMessage.success(`已删除 ${res.deleted_count} 条数据`);
    await loadSummary(symbol);
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "删除失败");
  }
}

async function handleSync(symbol: string, source: string) {
  const key = `${symbol}_${source}`;
  syncLoading[key] = true;
  try {
    await syncStockBySource(symbol, source);
    ElMessage.success(`${source} 同步任务已提交，请查看同步任务结果`);
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "同步失败");
  } finally {
    syncLoading[key] = false;
  }
}

// --- Full Sync ---
const fullSyncDialogVisible = ref(false);
const fullSyncSource = ref("");
const fullSyncMode = ref("standard");
const fullSyncWorkers = ref(3);
const fullSyncLoading = ref(false);

function handleFullSync(source: string) {
  fullSyncSource.value = source;
  fullSyncMode.value = "standard";
  fullSyncWorkers.value = 3;
  fullSyncDialogVisible.value = true;
}

async function confirmFullSync() {
  fullSyncLoading.value = true;
  try {
    const jobs = await createFullSync({
      source: fullSyncSource.value,
      sync_mode: fullSyncMode.value,
      max_workers: fullSyncWorkers.value,
    });
    fullSyncDialogVisible.value = false;
    syncJobsVisible.value = true;
    ElMessage.success(`已创建 ${jobs.length} 个全量同步任务，请在同步任务面板查看进度`);
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "创建全量同步失败");
  } finally {
    fullSyncLoading.value = false;
  }
}

// --- Reset all data ---
async function handleResetAll() {
  try {
    await ElMessageBox.prompt(
      '此操作将删除所有已同步的市场数据和同步任务记录，无法恢复！请输入 "CONFIRM" 确认。',
      "⚠️ 清空所有数据",
      {
        confirmButtonText: "确认清空",
        cancelButtonText: "取消",
        inputPattern: /^CONFIRM$/,
        inputErrorMessage: '请输入 "CONFIRM"',
        type: "warning",
        confirmButtonClass: "el-button--danger",
      }
    );
    const res = await resetAllData("CONFIRM");
    ElMessage.success(`已清空所有数据，共删除 ${res.total_records} 条数据记录`);
    refresh();
  } catch { /* user cancelled */ }
}

onMounted(() => {
  void loadStocks();
});
</script>

<style scoped>
.stock-data-page {
  display: grid;
  gap: 18px;
}

.table-pagination {
  display: flex;
  justify-content: center;
  padding: 16px 0 0;
}

.expand-content {
  padding: 12px 20px 20px;
}

.source-columns {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}

.source-column {
  padding: 14px;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.5);
  border: 1px solid var(--border);
}

.source-column__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--border);
}

.data-type-cards {
  display: grid;
  gap: 10px;
}

.data-type-card {
  padding: 10px 12px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.6);
  border: 1px solid var(--border);
}

.data-type-card__header {
  margin-bottom: 6px;
}

.data-type-card__label {
  font-size: 13px;
  font-weight: 600;
  color: var(--ink);
}

.data-type-card__stats {
  display: flex;
  gap: 16px;
  font-size: 12px;
  color: var(--muted);
  margin-bottom: 6px;
}

.data-type-card__stats strong {
  color: var(--ink);
}

.data-type-card__actions {
  display: flex;
  gap: 4px;
}

.sync-jobs-btn {
  box-shadow: 0 2px 12px rgba(23, 54, 47, 0.12);
}
</style>
