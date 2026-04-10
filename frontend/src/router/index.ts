import { createRouter, createWebHistory } from "vue-router";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: "/",
      redirect: "/analysis"
    },
    {
      path: "/analysis",
      component: () => import("../views/SingleStockAnalysisView.vue"),
      meta: {
        title: "单股分析",
        subtitle: "输入股票代码，调度多角色 Agent 生成结构化结论。"
      }
    },
    {
      path: "/history",
      component: () => import("../views/HistoryView.vue"),
      meta: {
        title: "历史分析记录",
        subtitle: "回看历史任务、最终总结和每个 Agent 的原始判断。"
      }
    },
    {
      path: "/settings",
      component: () => import("../views/SettingsView.vue"),
      meta: {
        title: "系统设置",
        subtitle: "管理数据源优先级、大模型连接和提示词模板。"
      }
    },
    {
      path: "/logs",
      component: () => import("../views/LogsView.vue"),
      meta: {
        title: "日志",
        subtitle: "查看操作日志与系统日志，定位任务状态变化。"
      }
    },
    {
      path: "/sources",
      component: () => import("../views/DataSourcesView.vue"),
      meta: {
        title: "数据源",
        subtitle: "执行接口状态校验与手动同步，掌握本地数据基础。"
      }
    },
    {
      path: "/stock-data",
      component: () => import("../views/StockDataView.vue"),
      meta: {
        title: "股票数据",
        subtitle: "查看与管理各数据源、各类型的股票数据。"
      }
    },
    {
      path: "/:pathMatch(.*)*",
      component: () => import("../views/NotFoundView.vue"),
      meta: {
        title: "页面不存在",
        subtitle: "当前访问的路径不存在。"
      }
    }
  ]
});

export default router;
