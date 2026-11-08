<script setup>
/**
 * 地图容器组件。
 *
 * 这个文件只做「组合」，不装业务细节：
 *   - map/constants.js   常量配置
 *   - map/layers.js      画什么（source + layer 定义、显隐、聚焦）
 *   - map/mapActions.js  怎么动（拉数据、响应点击、跟随尺寸）
 *
 * 这里保留的只有三件事：创建地图实例、绑定事件、把 store 变化同步到地图。
 */

import { computed, onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue'
import mapboxgl from 'mapbox-gl'
import 'mapbox-gl/dist/mapbox-gl.css'

import EmptyState from '@/components/EmptyState.vue'
import Legend from '@/components/Legend.vue'
import {
  CHENGDU_BOUNDS,
  EMPTY_FC,
  MAPBOX_TOKEN,
  MAP_STYLES,
  POI_LAYERS,
} from '@/map/constants'
import {
  applyDistrictFocus,
  applyVisibility,
  installLayers,
  setHighlight,
} from '@/map/layers'
import { createMapActions } from '@/map/mapActions'
import { useFilterStore } from '@/stores/filter'
import { useLayerStore } from '@/stores/layer'
import { useUiStore } from '@/stores/ui'

const layer = useLayerStore()
const filter = useFilterStore()
const ui = useUiStore()

const mapEl = ref(null)
const map = shallowRef(null)

// 三份常驻内存的 GeoJSON。用 shallowRef：整体替换才触发更新，
// 不做深层代理（几千个要素的深层 Proxy 会明显拖慢）
const districtsFC = shallowRef(EMPTY_FC)
const boundaryFC = shallowRef(EMPTY_FC)
const lastFacilityFC = shallowRef(EMPTY_FC)

/** 空态：已经加载完、不在加载中、且当前视口 0 个设施 */
const showEmpty = computed(
  () => filter.stats.loaded && !filter.stats.loading && filter.stats.count === 0,
)

const actions = createMapActions({
  map,
  mapEl,
  districtsFC,
  boundaryFC,
  lastFacilityFC,
  layer,
  filter,
  ui,
})

/** 换底图后重建图层，并把设施数据补回去 */
function reinstallAfterStyleChange(m) {
  installLayers(m, {
    districts: districtsFC.value,
    boundary: boundaryFC.value,
    facilities: lastFacilityFC.value,
  })
  m.getSource('facilities')?.setData(lastFacilityFC.value)
}

onMounted(() => {
  mapboxgl.accessToken = MAPBOX_TOKEN

  const m = new mapboxgl.Map({
    container: mapEl.value,
    style: MAP_STYLES[ui.baseMap],
    center: [104.0658, 30.6571],
    zoom: 10,
    attributionControl: false,
  })
  map.value = m

  m.addControl(new mapboxgl.AttributionControl({ compact: true }), 'bottom-right')

  // 容器尺寸稳定后再渲染，避免尺寸为 0 时生成 NaN 变换矩阵
  requestAnimationFrame(() => m.resize())

  m.on('load', async () => {
    // 再等一帧，确保容器已完成布局
    requestAnimationFrame(() => {
      m.resize()
      if (mapEl.value?.clientHeight > 0) m.fitBounds(CHENGDU_BOUNDS, { padding: 24 })
    })

    installLayers(m, {
      districts: districtsFC.value,
      boundary: boundaryFC.value,
      facilities: lastFacilityFC.value,
    })
    await actions.loadReferenceLayers()
    await actions.loadCounts()
    actions.refresh()
  })

  // 视口联动：moveend + 300ms 防抖（用 move 会每帧触发）
  m.on('moveend', () => {
    if (!actions.hasValidBounds(m)) return
    ui.zoom = m.getZoom()
    const c = m.getCenter()
    ui.center = { lng: c.lng, lat: c.lat }
    actions.refresh()
  })

  m.on('mousemove', (e) => {
    if (!Number.isFinite(e.lngLat.lng) || !Number.isFinite(e.lngLat.lat)) return
    ui.hover = { lng: e.lngLat.lng, lat: e.lngLat.lat }
  })

  // 逐图层注册光标样式（避免依赖数组重载的行为差异）
  for (const id of POI_LAYERS) {
    m.on('mouseenter', id, () => {
      m.getCanvas().style.cursor = 'pointer'
    })
    m.on('mouseleave', id, () => {
      m.getCanvas().style.cursor = ''
    })
  }

  m.on('click', actions.onClick)

  window.addEventListener('resize', actions.resizeMap)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', actions.resizeMap)
  map.value?.remove()
})

// =====================================================================
// store → 地图 的同步
// =====================================================================

watch(
  () => ui.baseMap,
  (value) => {
    const m = map.value
    if (!m) return
    m.setStyle(MAP_STYLES[value])
    // setStyle 会清空所有图层，必须重装
    m.once('style.load', () => reinstallAfterStyleChange(m))
  },
)

watch(
  () => layer.visibleTypes.slice(),
  () => {
    applyVisibility(map.value)
    actions.refresh()
  },
)

watch(
  () => ({ ...layer.geoserver }),
  () => applyVisibility(map.value),
)

watch(
  () => ({ ...layer.analysis }),
  () => applyVisibility(map.value),
)

watch(
  () => filter.district,
  () => {
    applyDistrictFocus(map.value, districtsFC.value)
    actions.refresh()
  },
)

// 抽屉切换时同步区县高亮
watch(
  () => [ui.drawer.open, ui.drawer.kind, ui.drawer.data?.adcode],
  () => {
    const m = map.value
    if (!m) return
    const adcode =
      ui.drawer.open && ui.drawer.kind === 'district' ? ui.drawer.data?.adcode : null
    setHighlight(m, adcode, districtsFC.value)
  },
)

// 左侧面板收起/展开后容器尺寸变化，等过渡结束再 resize
watch(
  () => ui.sideCollapsed,
  () => setTimeout(actions.resizeMap, 240),
)

// 分析结果：整体替换 source 数据
watch(
  () => layer.coverageData,
  (fc) => {
    if (fc) map.value?.getSource('coverage')?.setData(fc)
  },
)

watch(
  () => layer.accessibilityData,
  (fc) => {
    if (fc) map.value?.getSource('accessibility')?.setData(fc)
  },
)

watch(
  () => layer.isochroneData,
  (fc) => {
    if (fc) map.value?.getSource('isochrone')?.setData(fc)
  },
)

watch(
  () => ui.flyTo,
  (target) => {
    if (!target) return
    if (!Number.isFinite(target.lng) || !Number.isFinite(target.lat)) return
    map.value?.flyTo({
      center: [target.lng, target.lat],
      zoom: Number.isFinite(target.zoom) ? target.zoom : 15,
      duration: 800,
    })
  },
)
</script>

<template>
  <div class="map-root">
    <div ref="mapEl" class="map"></div>

    <Legend />

    <div v-if="filter.stats.loading" class="pill">刷新中…</div>

    <div v-if="showEmpty" class="empty-overlay">
      <EmptyState text="当前视口内没有设施" hint="试试缩小地图范围" />
    </div>

    <div v-if="filter.stats.error" class="error-overlay">
      <span>统计服务响应超时：{{ filter.stats.error }}</span>
      <button @click="actions.refresh">重试</button>
    </div>

    <div v-if="filter.district" class="chip">
      只看：{{ filter.district.name }}
      <button aria-label="取消区县筛选" title="取消筛选" @click="actions.clearDistrict">
        ✕
      </button>
    </div>
  </div>
</template>

<style scoped>
.map-root {
  position: absolute;
  inset: 0;
}
.map {
  position: absolute;
  inset: 0;
}
.pill {
  position: absolute;
  left: 16px;
  bottom: 16px;
  padding: 4px 12px;
  background: rgba(255, 255, 255, 0.94);
  border: 1px solid var(--c-line);
  border-radius: 999px;
  font-size: var(--fs-caption);
  color: var(--c-text-2);
  z-index: 5;
}
.empty-overlay {
  position: absolute;
  left: 50%;
  top: 50%;
  transform: translate(-50%, -50%);
  background: rgba(255, 255, 255, 0.96);
  border: 1px solid var(--c-line);
  border-radius: var(--radius-panel);
  z-index: 5;
}
.error-overlay {
  position: absolute;
  left: 50%;
  top: 16px;
  transform: translateX(-50%);
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  background: #fff1f0;
  border: 1px solid var(--c-error);
  border-radius: var(--radius-btn);
  font-size: var(--fs-caption);
  color: var(--c-error);
  z-index: 6;
}
.error-overlay button {
  height: 24px;
  padding: 0 8px;
  font-size: var(--fs-caption);
}
.chip {
  position: absolute;
  top: 16px;
  left: 16px;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 8px 4px 12px;
  background: var(--c-warning);
  color: #fff;
  border-radius: 999px;
  font-size: var(--fs-caption);
  z-index: 5;
}
.chip button {
  width: 20px;
  height: 20px;
  border: none;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.25);
  color: #fff;
  font-size: 11px;
}
</style>
