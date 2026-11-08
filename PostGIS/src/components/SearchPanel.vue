<script setup>
defineProps({
  items: { type: Array, default: () => [] },
  visible: { type: Boolean, default: false },
  loading: { type: Boolean, default: false },
})

const emit = defineEmits(['select'])
</script>

<template>
  <div v-if="visible" class="panel">
    <div v-if="loading" class="tip">搜索中…</div>
    <div v-else-if="items.length === 0" class="tip">没有匹配的设施</div>
    <button
      v-for="item in items"
      :key="item.poi_id"
      class="item"
      @mousedown.prevent="emit('select', item)"
    >
      <span class="name">{{ item.name }}</span>
      <span class="meta">{{ item.category }} · {{ item.district }}</span>
    </button>
  </div>
</template>

<style scoped>
.panel {
  position: absolute;
  top: 42px;
  left: 0;
  right: 0;
  background: var(--c-panel);
  border: 1px solid var(--c-line);
  border-radius: var(--radius-panel);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.12);
  overflow: hidden;
  z-index: 30;
}
.item {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: flex-start;
  gap: 2px;
  width: 100%;
  height: 40px;
  padding: 0 12px;
  border: none;
  border-bottom: 1px solid var(--c-line);
  background: transparent;
  text-align: left;
}
.item:hover {
  background: var(--c-card);
}
.name {
  font-size: var(--fs-body);
}
.meta {
  font-size: var(--fs-caption);
  color: var(--c-text-2);
}
.tip {
  padding: 12px;
  font-size: var(--fs-caption);
  color: var(--c-text-2);
}
</style>
