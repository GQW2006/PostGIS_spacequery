<script setup>
import { useFilterStore } from '@/stores/filter'
import { useUiStore } from '@/stores/ui'

const ui = useUiStore()
const filter = useFilterStore()
</script>

<template>
  <footer class="status">
    <span class="num coord">
      {{ ui.hover.lng.toFixed(6) }}, {{ ui.hover.lat.toFixed(6) }}
    </span>
    <span class="num">Z{{ Math.round(ui.zoom) }}</span>
    <span class="num">视口内 {{ filter.stats.count }} 个设施</span>
    <span v-if="filter.stats.truncated" class="truncated">已截断显示前 3000 个</span>
    <span class="spacer"></span>
    <span class="source">数据：高德 POI · 2026-11</span>
  </footer>
</template>

<style scoped>
.status {
  height: var(--h-status);
  flex: 0 0 var(--h-status);
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 0 16px;
  background: var(--c-panel);
  border-top: 1px solid var(--c-line);
  font-size: var(--fs-caption);
  color: var(--c-text-2);
  overflow: hidden;
}
.status > span {
  flex: 0 0 auto;
}
.coord {
  white-space: nowrap;
}
.truncated {
  color: var(--c-warning);
}
.spacer {
  flex: 1 1 auto;
}
.source {
  color: var(--c-text-2);
}

/* 窄屏：次要元信息让位，保证坐标/缩放/数量三项不重叠 */
@media (max-width: 767px) {
  .status {
    gap: 8px;
  }
  .source,
  .truncated {
    display: none;
  }
}
</style>
