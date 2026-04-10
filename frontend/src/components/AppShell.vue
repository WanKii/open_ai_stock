<template>
  <div class="shell">
    <aside class="shell__sidebar">
      <div class="brand-panel">
        <p class="brand-panel__eyebrow">A-SHARE INTELLIGENCE DESK</p>
        <h1>闻价台</h1>
        <p class="brand-panel__copy">
          用多角色 Agent 串起 A 股分析主链路，把行情、财务、新闻和板块脉搏折叠进一个本地工作台。
        </p>
      </div>

      <nav class="nav-list">
        <RouterLink
          v-for="item in navItems"
          :key="item.path"
          :to="item.path"
          class="nav-item"
          active-class="nav-item--active"
        >
          <component :is="item.icon" class="nav-item__icon" />
          <div>
            <strong>{{ item.label }}</strong>
            <span>{{ item.hint }}</span>
          </div>
        </RouterLink>
      </nav>

      <div class="sidebar-stats">
        <div class="sidebar-stat">
          <span>排队中</span>
          <strong>{{ workspaceStore.queuedCount }}</strong>
        </div>
        <div class="sidebar-stat">
          <span>已完成</span>
          <strong>{{ workspaceStore.completedCount }}</strong>
        </div>
        <div class="sidebar-stat">
          <span>在线数据源</span>
          <strong>{{ workspaceStore.sourcesOnline }}</strong>
        </div>
        <div class="sidebar-stat">
          <span>模型配置</span>
          <strong>{{ workspaceStore.llmConfigured }}</strong>
        </div>
      </div>
    </aside>

    <main class="shell__main">
      <header class="page-header">
        <div>
          <p class="page-header__eyebrow">MVP WORKBENCH</p>
          <h2>{{ headerTitle }}</h2>
          <p>{{ headerSubtitle }}</p>
        </div>

        <div class="page-header__meta">
          <div>
            <span>文档基线</span>
            <strong>v0.1.0 / 2026-04-09</strong>
          </div>
          <div>
            <span>运行模式</span>
            <strong>单用户本机</strong>
          </div>
        </div>
      </header>

      <section class="page-body">
        <RouterView v-slot="{ Component }">
          <Transition name="page-fade" mode="out-in">
            <component :is="Component" />
          </Transition>
        </RouterView>
      </section>
    </main>
  </div>
</template>

<script setup lang="ts">
import {
  Collection,
  DataAnalysis,
  Grid,
  Memo,
  Setting,
  TrendCharts
} from "@element-plus/icons-vue";
import { computed, onMounted } from "vue";
import { RouterLink, RouterView, useRoute } from "vue-router";

import { useWorkspaceStore } from "../stores/workspace";

const route = useRoute();
const workspaceStore = useWorkspaceStore();
const headerTitle = computed(() => String(route.meta.title || ""));
const headerSubtitle = computed(() => String(route.meta.subtitle || ""));

const navItems = [
  { path: "/analysis", label: "单股分析", hint: "提交任务与查看即时报告", icon: TrendCharts },
  { path: "/history", label: "历史分析记录", hint: "回看历史任务与结论", icon: Collection },
  { path: "/settings", label: "系统设置", hint: "维护模型、数据源和提示词", icon: Setting },
  { path: "/logs", label: "日志", hint: "跟踪系统与操作日志", icon: Memo },
  { path: "/sources", label: "数据源", hint: "校验状态并手动同步", icon: DataAnalysis },
  { path: "/stock-data", label: "股票数据", hint: "查看与管理各源各类型数据", icon: Grid }
];

onMounted(() => {
  workspaceStore.refreshOverview();
});
</script>
