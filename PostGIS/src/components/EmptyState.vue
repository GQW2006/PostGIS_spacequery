<script setup>
defineProps({
  text: { type: String, default: '暂无数据' },
  hint: { type: String, default: '' },
})
</script>

<template>
  <div class="empty">
    <svg width="56" height="56" viewBox="0 0 24 24" fill="none" stroke="#C9CDD4" stroke-width="1.5">
      <circle cx="11" cy="11" r="7" />
      <path d="M20 20l-3.5-3.5" />
      <path d="M8 11h6" />
    </svg>
    <p class="text">{{ text }}</p>
    <p v-if="hint" class="hint">{{ hint }}</p>
  </div>
</template>

<style scoped>
.empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  padding: 16px;
  text-align: center;
}
.text {
  margin: 4px 0 0;
  font-size: var(--fs-body);
  color: var(--c-text-2);
}
.hint {
  margin: 0;
  font-size: var(--fs-caption);
  color: var(--c-text-disabled);
}
</style>
