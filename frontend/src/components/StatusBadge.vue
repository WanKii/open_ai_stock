<template>
  <span class="status-badge" :class="[toneClass, { 'status-badge--pulse': pulse }]">
    {{ label }}
  </span>
</template>

<script setup lang="ts">
import { computed } from "vue";

const props = defineProps<{
  label: string;
  tone?: "neutral" | "good" | "warn" | "danger";
  pulse?: boolean;
}>();

const toneClass = computed(() => props.tone || "neutral");
</script>
