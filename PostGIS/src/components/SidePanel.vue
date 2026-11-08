<script setup>
import LayerTree from '@/components/LayerTree.vue'
import AnalysisPanel from '@/components/AnalysisPanel.vue'
import { useFilterStore } from '@/stores/filter'
import { useUiStore } from '@/stores/ui'

const ui = useUiStore()
const filter = useFilterStore()
</script>

<template>
  <aside class="side" :class="{ collapsed: ui.sideCollapsed }">
    <div class="inner">
      <div class="tabs">
        <button
          class="tab"
          :class="{ active: filter.tab === 'layers' }"
          @click="filter.tab = 'layers'"
        >
          图层
        </button>
        <button
          class="tab"
          :class="{ active: filter.tab === 'analysis' }"
          @click="filter.tab = 'analysis'"
        >
          分析
        </button>
      </div>

      <div class="content">
        <LayerTree v-if="filter.tab === 'layers'" />
        <AnalysisPanel v-else />
      </div>

      <button class="collapse" @click="ui.sideCollapsed = true">收起 ◀</button>
    </div>
  </aside>
</template>

<style scoped>
.side {
  width: var(--w-side);
  flex: 0 0 var(--w-side);
  background: var(--c-panel);
  border-right: 1px solid var(--c-line);
  transition: width 0.2s ease, flex-basis 0.2s ease;
  overflow: hidden;
}
.side.collapsed {
  width: 0;
  flex-basis: 0;
  border-right: none;
}
.inner {
  width: var(--w-side);
  height: 100%;
  display: flex;
  flex-direction: column;
}
.tabs {
  display: flex;
  height: 40px;
}
.tab {
  flex: 1;
  height: 40px;
  border: none;
  border-bottom: 1px solid var(--c-line);
  background: transparent;
  font-size: var(--fs-body);
  color: var(--c-text-2);
}
.tab.active {
  color: var(--c-action);
  border-bottom: 2px solid var(--c-action);
  font-weight: 600;
}
.content {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}
.collapse {
  height: 40px;
  margin-top: auto;
  border: none;
  border-top: 1px solid var(--c-line);
  background: transparent;
  color: var(--c-text-2);
  font-size: var(--fs-caption);
}

/* 1024–1365px：面板收窄至 280px */
@media (max-width: 1365px) {
  .side {
    width: 280px;
    flex-basis: 280px;
  }
  .inner {
    width: 280px;
  }
}

/* 768–1023px：面板改为浮层抽屉，默认收起（由 AppShell 设置） */
@media (max-width: 1023px) {
  .side:not(.collapsed) {
    position: absolute;
    left: 0;
    top: 0;
    height: 100%;
    width: 320px;
    flex-basis: 320px;
    z-index: 18;
    box-shadow: 4px 0 16px rgba(0, 0, 0, 0.12);
  }
  .side:not(.collapsed) .inner {
    width: 320px;
  }
}
</style>
