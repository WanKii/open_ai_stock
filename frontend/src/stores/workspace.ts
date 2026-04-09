import { defineStore } from "pinia";

import { getSettings, getSourceStatuses, listAnalysisTasks } from "../api/client";

export const useWorkspaceStore = defineStore("workspace", {
  state: () => ({
    queuedCount: 0,
    completedCount: 0,
    sourcesOnline: 0,
    llmConfigured: 0,
    loading: false
  }),
  actions: {
    async refreshOverview() {
      this.loading = true;

      try {
        const [tasks, statuses, settings] = await Promise.all([
          listAnalysisTasks(),
          getSourceStatuses(),
          getSettings()
        ]);

        this.queuedCount = tasks.filter((task) => task.status === "queued" || task.status === "running").length;
        this.completedCount = tasks.filter((task) => task.status === "completed").length;
        this.sourcesOnline = statuses.filter((status) => status.status === "online").length;
        this.llmConfigured = Object.values(settings.llm_providers).filter((provider) => provider.configured).length;
      } finally {
        this.loading = false;
      }
    }
  }
});
