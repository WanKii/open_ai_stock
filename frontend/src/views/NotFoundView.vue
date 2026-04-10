<template>
  <div class="empty-state" style="min-height: 400px">
    <div style="display: grid; gap: 16px; place-items: center">
      <svg
        width="80"
        height="80"
        viewBox="0 0 80 80"
        fill="none"
        style="opacity: 0.35"
      >
        <circle cx="40" cy="40" r="36" stroke="currentColor" stroke-width="2" />
        <text
          x="40"
          y="46"
          text-anchor="middle"
          font-size="24"
          font-weight="700"
          fill="currentColor"
        >
          404
        </text>
      </svg>
      <h3 style="margin: 0">页面不存在</h3>
      <p class="muted" style="margin: 0">请检查地址或返回分析页面。</p>
      <RouterLink to="/analysis" class="el-button el-button--primary">
        返回首页
      </RouterLink>
    </div>
  </div>
</template>

<script setup lang="ts">
import { RouterLink } from "vue-router";
</script>
