// 界面状态（Pinia）：抽屉、坐标/缩放、网络、登录态、飞行定位指令
// 说明：任务书只列了 layer / filter 两个 store；抽屉与全局 UI 状态与筛选无关，
// 单独拆出 ui.js，避免 filter store 职责膨胀。

import { ref } from 'vue'
import { defineStore } from 'pinia'

export const useUiStore = defineStore('ui', () => {
  // 右侧抽屉：{ open, kind: 'facility'|'district'|'point', data }
  const drawer = ref({ open: false, kind: null, data: null })

  // 鼠标坐标与缩放（状态栏）
  const hover = ref({ lng: 104.0658, lat: 30.6571 })
  const zoom = ref(10)
  const center = ref({ lng: 104.0658, lat: 30.6571 })

  // 底图：light | dark | satellite
  const baseMap = ref('light')

  // 左侧面板是否收起
  const sideCollapsed = ref(false)

  // 网络状态（无网络横幅）
  const offline = ref(!navigator.onLine)

  // 登录态（演示：按钮禁用态用；真实项目接 JWT 后替换）
  const isLoggedIn = ref(false)

  // 飞行定位指令：{ lng, lat, zoom, ts }，ts 用于重复点击同一位置也能触发
  const flyTo = ref(null)

  // 轻提示
  const toast = ref('')

  let toastTimer = null

  function openDrawer(kind, data) {
    drawer.value = { open: true, kind, data }
  }

  function closeDrawer() {
    drawer.value = { ...drawer.value, open: false }
  }

  function fly(lng, lat, zoomLevel = 15) {
    flyTo.value = { lng, lat, zoom: zoomLevel, ts: Date.now() }
  }

  function showToast(message, ms = 3200) {
    toast.value = message
    clearTimeout(toastTimer)
    toastTimer = setTimeout(() => (toast.value = ''), ms)
  }

  return {
    drawer,
    hover,
    zoom,
    center,
    baseMap,
    sideCollapsed,
    offline,
    isLoggedIn,
    flyTo,
    toast,
    openDrawer,
    closeDrawer,
    fly,
    showToast,
  }
})
