<template>
  <el-drawer
    :model-value="visible"
    :title="`${symbol} — ${sourceLabel} / ${dataTypeLabel}`"
    size="70%"
    direction="rtl"
    @close="$emit('update:visible', false)"
  >
    <el-table :data="rows" height="calc(100vh - 200px)" stripe border>
      <el-table-column
        v-for="col in columns"
        :key="col"
        :prop="col"
        :label="columnLabel(col)"
        :min-width="columnWidth(col)"
        show-overflow-tooltip
      />
    </el-table>

    <div class="drawer-pagination">
      <el-pagination
        v-model:current-page="currentPage"
        :page-size="pageSize"
        :total="total"
        layout="total, prev, pager, next"
        @current-change="loadData"
      />
    </div>
  </el-drawer>
</template>

<script setup lang="ts">
import { ref, watch } from "vue";

import { getStockData } from "../api/client";

const props = defineProps<{
  visible: boolean;
  symbol: string;
  source: string;
  dataType: string;
}>();

defineEmits<{ "update:visible": [val: boolean] }>();

const rows = ref<Record<string, unknown>[]>([]);
const columns = ref<string[]>([]);
const total = ref(0);
const currentPage = ref(1);
const pageSize = 50;

const sourceLabel = props.source.toUpperCase();

const DATA_TYPE_LABELS: Record<string, string> = {
  daily_quotes: "日K线",
  financial_reports: "财务数据",
  news_items: "新闻",
  announcements: "公告"
};
const dataTypeLabel = DATA_TYPE_LABELS[props.dataType] || props.dataType;

const COLUMN_LABELS: Record<string, string> = {
  trade_date: "交易日期",
  open: "开盘价",
  high: "最高价",
  low: "最低价",
  close: "收盘价",
  volume: "成交量",
  amount: "成交额",
  source: "数据源",
  report_date: "报告日期",
  report_type: "报告类型",
  revenue: "营业收入",
  net_profit: "净利润",
  roe: "ROE",
  gross_margin: "毛利率",
  news_id: "新闻ID",
  published_at: "发布时间",
  title: "标题",
  content: "内容",
  url: "链接",
  announcement_id: "公告ID"
};

function columnLabel(col: string) {
  return COLUMN_LABELS[col] || col;
}

function columnWidth(col: string) {
  if (col === "content") return 300;
  if (col === "title") return 200;
  if (col === "url") return 160;
  return 120;
}

async function loadData() {
  try {
    const resp = await getStockData(props.symbol, props.source, props.dataType, currentPage.value, pageSize);
    rows.value = resp.rows;
    columns.value = resp.columns;
    total.value = resp.total;
  } catch {
    rows.value = [];
    columns.value = [];
    total.value = 0;
  }
}

watch(
  () => props.visible,
  (val) => {
    if (val) {
      currentPage.value = 1;
      loadData();
    }
  }
);
</script>

<style scoped>
.drawer-pagination {
  display: flex;
  justify-content: center;
  padding: 16px 0;
}
</style>
