<template>
  <div class="panel">
    <div class="panel__header">
      <div>
        <p class="eyebrow">CONFIG CENTER</p>
        <h3>系统设置</h3>
      </div>
      <div class="panel__actions">
        <el-button @click="loadSettingsData">重载</el-button>
        <el-button type="primary" :loading="saving" @click="saveAll">保存设置</el-button>
      </div>
    </div>

    <template v-if="settings">
      <el-tabs>
        <el-tab-pane label="数据源配置">
          <div class="config-grid">
            <article v-for="(source, name) in settings.data_sources" :key="name" class="config-card">
              <div class="config-card__header">
                <div>
                  <p class="eyebrow">{{ name.toUpperCase() }}</p>
                  <h4>{{ source.base_url }}</h4>
                </div>
                <el-switch v-model="source.enabled" />
              </div>

              <el-form label-position="top">
                <el-form-item label="优先级">
                  <el-input-number v-model="source.priority" :min="1" :max="10" />
                </el-form-item>
                <el-form-item label="Token">
                  <el-input v-model="source.token" show-password />
                </el-form-item>
                <el-form-item label="Base URL">
                  <el-input v-model="source.base_url" />
                </el-form-item>
              </el-form>

              <div class="cap-list">
                <span v-for="cap in source.supports" :key="cap">{{ cap }}</span>
              </div>

              <el-button text @click="runConnectionTest('data_source', name)">连接测试</el-button>
            </article>
          </div>
        </el-tab-pane>

        <el-tab-pane label="大模型连接">
          <div class="config-grid">
            <article v-for="(provider, name) in settings.llm_providers" :key="name" class="config-card">
              <div class="config-card__header">
                <div>
                  <p class="eyebrow">{{ name.toUpperCase() }}</p>
                  <h4>{{ provider.model }}</h4>
                </div>
                <el-switch v-model="provider.enabled" />
              </div>

              <el-form label-position="top">
                <el-form-item label="Base URL">
                  <el-input v-model="provider.base_url" />
                </el-form-item>
                <el-form-item label="模型名称">
                  <el-input v-model="provider.model" />
                </el-form-item>
                <el-form-item label="API Key">
                  <el-input v-model="provider.api_key" show-password />
                </el-form-item>
                <div class="inline-fields">
                  <el-form-item label="Timeout">
                    <el-input-number v-model="provider.timeout" :min="10" :max="600" />
                  </el-form-item>
                  <el-form-item label="Max Tokens">
                    <el-input-number v-model="provider.max_tokens" :min="256" :max="16000" />
                  </el-form-item>
                </div>
              </el-form>

              <el-button text @click="runConnectionTest('llm_provider', name)">连接测试</el-button>
            </article>
          </div>
        </el-tab-pane>

        <el-tab-pane label="提示词配置">
          <div class="prompt-grid">
            <article v-for="(prompt, name) in settings.prompts" :key="name" class="prompt-card">
              <div class="config-card__header">
                <div>
                  <p class="eyebrow">PROMPT</p>
                  <h4>{{ promptLabelMap[name] || name }}</h4>
                </div>
              </div>
              <el-input v-model="settings.prompts[name]" type="textarea" :rows="5" />
            </article>
          </div>
        </el-tab-pane>
      </el-tabs>

      <p class="muted config-path">当前本机配置文件：{{ settings.local_config_path }}</p>
    </template>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { ElMessage } from "element-plus";

import { getSettings, testConnection, updateSettings } from "../api/client";
import type { SystemSettings } from "../types";
import { useWorkspaceStore } from "../stores/workspace";

const settings = ref<SystemSettings | null>(null);
const saving = ref(false);
const workspaceStore = useWorkspaceStore();

const promptLabelMap: Record<string, string> = {
  market_analyst: "市场分析师 Prompt",
  fundamental_analyst: "基本面分析师 Prompt",
  news_analyst: "新闻分析师 Prompt",
  index_analyst: "大盘分析师 Prompt",
  sector_analyst: "板块分析师 Prompt",
  final_summarizer: "总结 Agent Prompt"
};

async function loadSettingsData() {
  const payload = await getSettings();
  settings.value = JSON.parse(JSON.stringify(payload));
}

async function saveAll() {
  if (!settings.value) {
    return;
  }

  saving.value = true;
  try {
    settings.value = await updateSettings(settings.value);
    await workspaceStore.refreshOverview();
    ElMessage.success("设置已保存。");
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "保存失败");
  } finally {
    saving.value = false;
  }
}

async function runConnectionTest(category: "data_source" | "llm_provider", provider: string) {
  try {
    const result = await testConnection({ category, provider });
    if (result.success) {
      ElMessage.success(result.message);
    } else {
      ElMessage.warning(result.message);
    }
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "连接测试失败");
  }
}

onMounted(loadSettingsData);
</script>
