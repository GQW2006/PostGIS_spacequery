<script setup>
import { onBeforeUnmount, onMounted } from 'vue'

import DetailDrawer from '@/components/DetailDrawer.vue'
import MapView from '@/components/MapView.vue'
import SidePanel from '@/components/SidePanel.vue'
import StatusBar from '@/components/StatusBar.vue'
import TopBar from '@/components/TopBar.vue'
import { useUiStore } from '@/stores/ui'

const ui = useUiStore()

function onOnline() {
  ui.offline = false
}
function onOffline() {
  ui.offline = true
}

onMounted(() => {
  window.addEventListener('online', onOnline)
  window.addEventListener('offline', onOffline)
  // 窄屏默认收起左侧面板（对应 UI 任务书 §7 响应式断点）
  if (window.innerWidth < 1024) ui.sideCollapsed = true
})
onBeforeUnmount(() => {
  window.removeEventListener('online', onOnline)
  window.removeEventListener('offline', onOffline)
})
</script>

<template>
  <div class="shell">
    <TopBar />

    <!-- 状态 5：无网络 -->
    <div v-if="ui.offline" class="offline-banner">
      网络已断开，数据可能不是最新
    </div>

    <main class="body">
      <SidePanel />
      <section class="map-wrap">
        <MapView />
      </section>
      <DetailDrawer />
    </main>

    <StatusBar />

    <div v-if="ui.toast" class="toast">{{ ui.toast }}</div>
  </div>
</template>

<style scoped>
.shell {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--c-bg);
}
.body {
  flex: 1;
  display: flex;
  min-height: 0;
  position: relative;
}
.map-wrap {
  flex: 1;
  min-width: 0;
  position: relative;
}
.offline-banner {
  height: 28px;
  line-height: 28px;
  padding: 0 16px;
  background: #fff7e8;
  color: var(--c-warning);
  font-size: var(--fs-caption);
  border-bottom: 1px solid var(--c-line);
}
.toast {
  position: fixed;
  left: 50%;
  bottom: 56px;
  transform: translateX(-50%);
  padding: 8px 16px;
  background: rgba(31, 35, 41, 0.9);
  color: #fff;
  border-radius: var(--radius-btn);
  font-size: var(--fs-body);
  z-index: 30;
}
</style>
