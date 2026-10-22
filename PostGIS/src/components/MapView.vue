<script setup>
import { onBeforeUnmount, onMounted, ref, shallowRef } from 'vue'
import mapboxgl from 'mapbox-gl'
import 'mapbox-gl/dist/mapbox-gl.css'

import { fetchCities } from '@/api/geo'
import { useAreaLayer } from '@/composables/useAreaLayer'

const TOKEN = import.meta.env.VITE_TOKEN

const mapEl = ref(null)
const map = shallowRef(null)
const cities = ref([])
const selected = ref({})

const { loading, error, refresh, queryPoint } = useAreaLayer(map, () =>
  Object.keys(selected.value).filter((k) => selected.value[k]),
)

function formatPopup(feature) {
  const p = feature?.properties ?? {}
  if (!p.name) return '未命中行政区'
  let html = `<b>${p.name}</b><br/>所属城市：${p.city}`
  if (p.gb) html += `<br/>行政区码：${p.gb}`
  return html
}

onMounted(() => {
  mapboxgl.accessToken = TOKEN
  map.value = new mapboxgl.Map({
    container: mapEl.value,
    style: 'mapbox://styles/mapbox/light-v11',
    center: [103.6, 27.95], // 成都-昆明 两城居中
    zoom: 6,
  })

  map.value.on('load', async () => {
    cities.value = await fetchCities()
    selected.value = Object.fromEntries(cities.value.map((c) => [c.key, true]))
    refresh()
  })

  // 视口联动：缩放/平移结束时按当前视口防抖刷新行政区面
  map.value.on('moveend', refresh)

  // 点击弹窗：调用点查面接口显示所属行政区
  map.value.on('click', async (e) => {
    try {
      const fc = await queryPoint(e.lngLat)
      new mapboxgl.Popup({ closeButton: true, closeOnClick: false })
        .setLngLat(e.lngLat)
        .setHTML(formatPopup(fc.features?.[0]))
        .addTo(map.value)
    } catch (err) {
      console.error('点查面失败：', err)
    }
  })
})

onBeforeUnmount(() => {
  map.value?.remove()
})
</script>

<template>
  <div class="map-page">
    <header class="topbar">
      <span class="title">多城市行政区 · 视口联动</span>
      <div class="city-panel">
        <label v-for="c in cities" :key="c.key" class="city-item">
          <input
            type="checkbox"
            v-model="selected[c.key]"
            @change="refresh"
          />
          {{ c.label }}
        </label>
      </div>
      <span v-if="loading" class="loading">刷新中…</span>
      <span v-else-if="error" class="error">{{ error }}</span>
    </header>
    <div ref="mapEl" class="map-container"></div>
  </div>
</template>

<style scoped>
.map-page {
  position: relative;
  width: 100%;
  height: 100vh;
}
.topbar {
  position: absolute;
  top: 12px;
  left: 12px;
  z-index: 10;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 14px;
  background: rgba(255, 255, 255, 0.92);
  border-radius: 8px;
  box-shadow: 0 1px 6px rgba(0, 0, 0, 0.2);
  font-size: 14px;
}
.title {
  font-weight: 600;
}
.city-panel {
  display: flex;
  gap: 10px;
}
.city-item {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  cursor: pointer;
}
.loading {
  color: #64748b;
}
.error {
  color: #dc2626;
}
.map-container {
  width: 100%;
  height: 100%;
}
</style>
