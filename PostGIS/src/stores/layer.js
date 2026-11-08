// 图层状态（Pinia）：图层显隐、数量、分析结果数据

import { computed, reactive, ref, shallowRef } from 'vue'
import { defineStore } from 'pinia'

/** 三类设施的符号与颜色（与 UI 任务书 §3.2 一致） */
export const CATEGORY_META = {
  小学: { color: '#1668DC', shape: 'circle' },
  中学: { color: '#722ED1', shape: 'square' },
  菜市场: { color: '#00B42A', shape: 'circle' },
}

export const FACILITY_CATEGORIES = Object.keys(CATEGORY_META)

/**
 * 图例项统一契约：所有字段都显式存在（不适用的为 null），
 * 避免编辑器把数组推断成"只有 color 的单色项"而标红 stops。
 *
 * @typedef {Object} LegendStop
 * @property {string} label
 * @property {string} color
 *
 * @typedef {Object} LegendItem
 * @property {string} key
 * @property {string} label
 * @property {'circle'|'square'|'ring'|'line'|'ramp'} shape
 * @property {string|null} color
 * @property {LegendStop[]|null} stops
 * @property {string|null} note
 */

/**
 * 构造图例项，补齐可选字段。
 * @param {{key: string, label: string, shape: string}} item
 * @returns {LegendItem}
 */
function legendItem(item) {
  return { color: null, stops: null, note: null, ...item }
}

export const useLayerStore = defineStore('layer', () => {
  // GeoServer 发布的 WMS 图层（默认关闭：默认视觉改用矢量描边，避免默认 SLD 灰板压住底图）
  const geoserver = reactive({
    districts: false,
    boundary: false,
    roads: false,
    population: false,
  })

  // 设施图层（visible 控制地图与图例，count 来自 /api/facilities/stats）
  const facilities = reactive({
    小学: { visible: true, count: 0 },
    中学: { visible: true, count: 0 },
    菜市场: { visible: false, count: 0 },
  })

  // 分析结果图层
  const analysis = reactive({
    coverage: false,
    accessibility: false,
    isochrone: false,
  })

  // 分析结果数据（GeoJSON），整对象替换，用 shallowRef 避免深层代理
  const coverageData = shallowRef(null)
  const accessibilityData = shallowRef(null)
  const isochroneData = shallowRef(null)

  // 供地图请求使用的可见类型
  const visibleTypes = computed(() =>
    FACILITY_CATEGORIES.filter((c) => facilities[c].visible),
  )

  // 图例项：只显示当前可见的图层
  const legendItems = computed(() => {
    const items = []
    if (geoserver.districts) {
      items.push(legendItem({ key: 'wms-districts', label: '区县界', color: '#1668DC', shape: 'ring' }))
    }
    if (geoserver.boundary) {
      items.push(legendItem({ key: 'wms-boundary', label: '市界', color: '#FF7D00', shape: 'ring' }))
    }
    if (geoserver.roads) {
      items.push(legendItem({ key: 'wms-roads', label: '路网', color: '#8C8C8C', shape: 'line' }))
    }
    if (geoserver.population) {
      // 色值取自 GeoServer GetLegendGraphic 的实际渲染色，保证与地图一致
      items.push(
        legendItem({
          key: 'wms-population',
          label: '人口密度（人/100m 格）',
          shape: 'ramp',
          stops: [
            { label: '≤ 5', color: '#F6FAFD' },
            { label: '5–20', color: '#DEE9F3' },
            { label: '20–60', color: '#8FB4DF' },
            { label: '60–150', color: '#F6DD84' },
            { label: '150–400', color: '#EB8553' },
            { label: '> 400', color: '#A4285E' },
          ],
          note: '空白表示无数据 · 缩放 ≤13 时显示',
        }),
      )
    }
    items.push(
      ...FACILITY_CATEGORIES.filter((c) => facilities[c].visible).map((c) =>
        legendItem({ key: c, label: c, shape: CATEGORY_META[c].shape, color: CATEGORY_META[c].color }),
      ),
    )
    if (analysis.accessibility) {
      items.push(
        legendItem({ key: 'lvl-a', label: '可达性：优', color: '#0050B3', shape: 'square' }),
        legendItem({ key: 'lvl-b', label: '可达性：良', color: '#4E9BE8', shape: 'square' }),
        legendItem({ key: 'lvl-c', label: '可达性：一般', color: '#FAAD14', shape: 'square' }),
        legendItem({ key: 'lvl-d', label: '可达性：差', color: '#F5222D', shape: 'square' }),
      )
    }
    if (analysis.coverage) {
      items.push(legendItem({ key: 'coverage', label: '服务区覆盖', color: '#1668DC', shape: 'ring' }))
    }
    return items
  })

  function setCounts(list) {
    for (const item of list) {
      if (facilities[item.category]) facilities[item.category].count = item.count
    }
  }

  function toggleFacility(category) {
    facilities[category].visible = !facilities[category].visible
  }

  function toggleGeo(key) {
    geoserver[key] = !geoserver[key]
  }

  function toggleAnalysis(key) {
    analysis[key] = !analysis[key]
  }

  return {
    geoserver,
    facilities,
    analysis,
    coverageData,
    accessibilityData,
    isochroneData,
    visibleTypes,
    legendItems,
    setCounts,
    toggleFacility,
    toggleGeo,
    toggleAnalysis,
  }
})
