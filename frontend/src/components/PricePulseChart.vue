<template>
  <VChart class="price-chart" :option="option" autoresize />
</template>

<script setup lang="ts">
import { computed } from "vue";
import VChart from "vue-echarts";
import { use } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { LineChart } from "echarts/charts";
import { GridComponent, TooltipComponent } from "echarts/components";

import type { PricePoint } from "../types";

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent]);

const props = defineProps<{
  points: PricePoint[];
}>();

const option = computed(() => ({
  backgroundColor: "transparent",
  tooltip: {
    trigger: "axis"
  },
  grid: {
    left: 8,
    right: 8,
    top: 20,
    bottom: 10
  },
  xAxis: {
    type: "category",
    boundaryGap: false,
    data: props.points.map((point) => point.label),
    axisLine: {
      lineStyle: {
        color: "rgba(20, 50, 42, 0.18)"
      }
    },
    axisLabel: {
      color: "#4c625d",
      fontSize: 10
    }
  },
  yAxis: {
    type: "value",
    splitLine: {
      lineStyle: {
        color: "rgba(20, 50, 42, 0.08)"
      }
    },
    axisLabel: {
      color: "#4c625d",
      fontSize: 10
    }
  },
  series: [
    {
      type: "line",
      smooth: true,
      showSymbol: false,
      data: props.points.map((point) => point.value),
      lineStyle: {
        width: 3,
        color: "#d15d38"
      },
      areaStyle: {
        color: "rgba(209, 93, 56, 0.12)"
      }
    }
  ]
}));
</script>
