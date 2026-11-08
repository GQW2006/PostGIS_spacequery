/**
 * 地图图层：定义"地图上画什么"。
 *
 * 一个文件装下全部图层定义，因为它们的性质完全一样——
 * 都是「给 Mapbox 加 source + layer」。切成多个文件反而要在
 * 五个小文件之间跳来跳去，读一遍看不全。
 *
 * 文件内的分区（按渲染顺序，后加的在上）：
 *   ① 图标      canvas 现画的设施符号
 *   ② WMS 栅格  GeoServer 出图（人口/路网/行政）
 *   ③ 矢量装饰  区县描边、市界
 *   ④ 设施点    聚类气泡 + 三类单点
 *   ⑤ 分析结果  覆盖 / 可达性 / 等时圈
 *   ⑥ 浮层      选中高亮、点击标记
 *   ⑦ 显隐与聚焦
 */

import { WMS_LAYERS, wmsSource } from '@/api/geoserver'
import {
  CATEGORY_LAYER,
  CITY_LINE_COLOR,
  EMPTY_FC,
  WARD_LINE_COLOR,
} from '@/map/constants'
import { CATEGORY_META, FACILITY_CATEGORIES, useLayerStore } from '@/stores/layer'
import { useFilterStore } from '@/stores/filter'

// 注意：store 必须在函数内获取，不能在模块顶层。
// 本模块会在 main.js 装载 Pinia 之前被 import 求值，
// 顶层调用 useLayerStore() 会抛 "getActivePinia was called with no active Pinia"。

// =====================================================================
// ① 图标：用 canvas 现画，省掉图片资源，颜色跟着 CATEGORY_META 走
// =====================================================================

const ICON_SIZE = 40
const ICON_HALF = ICON_SIZE / 2
const ICON_RADIUS = 11
const ICON_SQUARE_HALF = 10
const ICON_STROKE = 4

function makeIcon(color, shape) {
  const canvas = document.createElement('canvas')
  canvas.width = ICON_SIZE
  canvas.height = ICON_SIZE
  const ctx = canvas.getContext('2d')

  ctx.fillStyle = color
  ctx.strokeStyle = '#ffffff'
  ctx.lineWidth = ICON_STROKE

  if (shape === 'square') {
    // 正方形旋转 45°，与图例里的菱形保持一致
    ctx.translate(ICON_HALF, ICON_HALF)
    ctx.rotate(Math.PI / 4)
    ctx.beginPath()
    ctx.rect(-ICON_SQUARE_HALF, -ICON_SQUARE_HALF, ICON_SQUARE_HALF * 2, ICON_SQUARE_HALF * 2)
  } else {
    ctx.beginPath()
    ctx.arc(ICON_HALF, ICON_HALF, ICON_RADIUS, 0, Math.PI * 2)
  }
  ctx.fill()
  ctx.stroke()

  return ctx.getImageData(0, 0, ICON_SIZE, ICON_SIZE)
}

function addFacilityIcons(m) {
  for (const [category, meta] of Object.entries(CATEGORY_META)) {
    const id = `icon-${category}`
    // 已存在则跳过，因此 setStyle 之后可以安全地重复调用
    if (!m.hasImage(id)) {
      m.addImage(id, makeIcon(meta.color, meta.shape), { pixelRatio: 2 })
    }
  }
}

// =====================================================================
// ② WMS 栅格：数据量大、只需"看得见"的图层走服务端出图
// =====================================================================

const WMS_CONFIG = [
  // 人口栅格是 100m 像元：Z>13 时每格只剩 2–3 像素，会变成麻点噪声。
  // 所以在图层级限制 maxzoom，放大后交给设施点与分析面表达。
  { id: 'wms-population', layer: WMS_LAYERS.population, opacity: 0.6, maxzoom: 13 },
  { id: 'wms-districts', layer: WMS_LAYERS.districts, opacity: 0.9 },
  { id: 'wms-boundary', layer: WMS_LAYERS.boundary, opacity: 1 },
  { id: 'wms-roads', layer: WMS_LAYERS.roads, opacity: 0.9 },
]

function installWmsLayers(m) {
  for (const { id, layer: wmsLayer, opacity, maxzoom } of WMS_CONFIG) {
    if (m.getSource(id)) continue

    m.addSource(id, wmsSource(wmsLayer))

    const spec = {
      id,
      type: 'raster',
      source: id,
      paint: { 'raster-opacity': opacity },
    }
    // minzoom / maxzoom 是「图层」属性，不能写进 paint
    if (maxzoom) spec.maxzoom = maxzoom

    m.addLayer(spec)
  }
}

// =====================================================================
// ③ 矢量装饰：数据量小的图层走 GeoJSON，前端渲染，颜色受 tokens 控制
// =====================================================================

function installAdminLayers(m, { districts, boundary }) {
  if (!m.getSource('districts')) {
    m.addSource('districts', { type: 'geojson', data: districts })

    // 遮罩：平时完全透明，只在「只看某个区」时把其它区压暗
    m.addLayer({
      id: 'district-mask',
      type: 'fill',
      source: 'districts',
      paint: { 'fill-color': '#F0F2F5', 'fill-opacity': 0 },
    })

    m.addLayer({
      id: 'district-line',
      type: 'line',
      source: 'districts',
      paint: {
        'line-color': WARD_LINE_COLOR,
        'line-width': 0.8,
        'line-opacity': 0.55,
      },
    })
  }

  if (!m.getSource('boundary')) {
    m.addSource('boundary', { type: 'geojson', data: boundary })

    m.addLayer({
      id: 'boundary-line',
      type: 'line',
      source: 'boundary',
      paint: {
        'line-color': CITY_LINE_COLOR,
        'line-width': 1.6,
      },
    })
  }
}

// =====================================================================
// ④ 设施点：聚类气泡（低缩放）+ 三类单点（高缩放）
// =====================================================================

function installFacilityLayers(m, initialData = EMPTY_FC) {
  if (m.getSource('facilities')) return

  m.addSource('facilities', {
    type: 'geojson',
    data: initialData,
    cluster: true,
    clusterMaxZoom: 11,
    clusterRadius: 50,
  })

  // 聚合气泡用「空心环」，与实心单点靠形状区分（不只依赖颜色）
  m.addLayer({
    id: 'poi-cluster',
    type: 'circle',
    source: 'facilities',
    filter: ['has', 'point_count'],
    paint: {
      'circle-color': 'rgba(14, 90, 196, 0.10)',
      'circle-radius': ['step', ['get', 'point_count'], 14, 50, 18, 200, 24],
      'circle-stroke-width': 2,
      'circle-stroke-color': '#0e5ac4',
    },
  })

  // 数量文字。故意不指定 text-font：沿用底图默认字体，
  // 避免请求不存在的字体文件导致 404。
  m.addLayer({
    id: 'poi-cluster-count',
    type: 'symbol',
    source: 'facilities',
    filter: ['has', 'point_count'],
    layout: {
      'text-field': ['get', 'point_count_abbreviated'],
      'text-size': 12,
    },
    paint: { 'text-color': '#0e5ac4' },
  })

  for (const category of FACILITY_CATEGORIES) {
    m.addLayer({
      id: CATEGORY_LAYER[category],
      type: 'symbol',
      source: 'facilities',
      filter: [
        'all',
        ['!', ['has', 'point_count']],
        ['==', ['get', 'category'], category],
      ],
      layout: {
        'icon-image': `icon-${category}`,
        'icon-size': 0.5,
        'icon-allow-overlap': true,
      },
    })
  }
}

// =====================================================================
// ⑤ 分析结果：覆盖 / 可达性 / 等时圈
// =====================================================================

function installAnalysisLayers(m) {
  const layer = useLayerStore()

  if (!m.getSource('coverage')) {
    m.addSource('coverage', { type: 'geojson', data: layer.coverageData ?? EMPTY_FC })
    m.addLayer({
      id: 'coverage-fill',
      type: 'fill',
      source: 'coverage',
      paint: { 'fill-color': '#1668DC', 'fill-opacity': 0.22 },
    })
    m.addLayer({
      id: 'coverage-line',
      type: 'line',
      source: 'coverage',
      paint: { 'line-color': '#0E5AC4', 'line-width': 1 },
    })
  }

  if (!m.getSource('accessibility')) {
    m.addSource('accessibility', {
      type: 'geojson',
      data: layer.accessibilityData ?? EMPTY_FC,
    })
    m.addLayer({
      id: 'accessibility-fill',
      type: 'fill',
      source: 'accessibility',
      paint: {
        // 按等级分级设色；level 缺失时退回中性灰
        'fill-color': [
          'match',
          ['get', 'level'],
          '优', '#0050B3',
          '良', '#4E9BE8',
          '一般', '#FAAD14',
          '差', '#F5222D',
          '#C9CDD4',
        ],
        'fill-opacity': 0.55,
      },
    })
  }

  if (!m.getSource('isochrone')) {
    m.addSource('isochrone', { type: 'geojson', data: layer.isochroneData ?? EMPTY_FC })
    m.addLayer({
      id: 'isochrone-fill',
      type: 'fill',
      source: 'isochrone',
      paint: { 'fill-color': '#FF7D00', 'fill-opacity': 0.18 },
    })
    m.addLayer({
      id: 'isochrone-line',
      type: 'line',
      source: 'isochrone',
      paint: { 'line-color': '#FF7D00', 'line-width': 2 },
    })
  }
}

// =====================================================================
// ⑥ 浮层：选中高亮 + 点击标记（永远在最上）
// =====================================================================

function installOverlayLayers(m) {
  if (!m.getSource('district-highlight')) {
    m.addSource('district-highlight', { type: 'geojson', data: EMPTY_FC })
    m.addLayer({
      id: 'district-highlight-fill',
      type: 'fill',
      source: 'district-highlight',
      paint: { 'fill-color': '#FAAD14', 'fill-opacity': 0.12 },
    })
    m.addLayer({
      id: 'district-highlight-line',
      type: 'line',
      source: 'district-highlight',
      paint: { 'line-color': '#FAAD14', 'line-width': 2 },
    })
  }

  if (!m.getSource('click-point')) {
    m.addSource('click-point', { type: 'geojson', data: EMPTY_FC })
    m.addLayer({
      id: 'click-point',
      type: 'circle',
      source: 'click-point',
      paint: {
        'circle-radius': 9,
        'circle-color': 'rgba(22,104,220,0.15)',
        'circle-stroke-width': 2,
        'circle-stroke-color': '#1668DC',
      },
    })
  }
}

// =====================================================================
// ⑦ 显隐与聚焦
// =====================================================================

function setVisibility(m, ids, visible) {
  for (const id of ids) {
    if (m.getLayer(id)) {
      m.setLayoutProperty(id, 'visibility', visible ? 'visible' : 'none')
    }
  }
}

/**
 * 把 store 里的开关状态同步到地图。
 * 每次切换图层、换底图、载入分析结果后都要调一次。
 */
export function applyVisibility(m) {
  if (!m) return

  const layer = useLayerStore()

  setVisibility(m, ['wms-districts'], layer.geoserver.districts)
  setVisibility(m, ['wms-boundary'], layer.geoserver.boundary)
  setVisibility(m, ['wms-roads'], layer.geoserver.roads)
  setVisibility(m, ['wms-population'], layer.geoserver.population)

  for (const category of FACILITY_CATEGORIES) {
    setVisibility(m, [CATEGORY_LAYER[category]], layer.facilities[category].visible)
  }

  setVisibility(m, ['coverage-fill', 'coverage-line'], layer.analysis.coverage)
  setVisibility(m, ['accessibility-fill'], layer.analysis.accessibility)
  setVisibility(m, ['isochrone-fill', 'isochrone-line'], layer.analysis.isochrone)
}

/**
 * 高亮某个区县。
 * @param {mapboxgl.Map} m
 * @param {string|null} adcode
 * @param {object} districts 区县 FeatureCollection（取自 districtsFC）
 */
export function setHighlight(m, adcode, districts) {
  if (!m || !m.getSource('district-highlight')) return

  if (!adcode) {
    m.getSource('district-highlight').setData(EMPTY_FC)
    return
  }

  const feature = districts?.features?.find((f) => f.properties?.adcode === adcode)
  m.getSource('district-highlight').setData(
    feature ? { type: 'FeatureCollection', features: [feature] } : EMPTY_FC,
  )
}

/**
 * 「只看这个区」：其它区县用浅色遮罩压暗，同时高亮选中区。
 * @param {mapboxgl.Map} m
 * @param {object} districts 区县 FeatureCollection
 */
export function applyDistrictFocus(m, districts) {
  if (!m || !m.getLayer('district-mask')) return

  const filter = useFilterStore()
  const selected = filter.district?.adcode
  m.setPaintProperty(
    'district-mask',
    'fill-opacity',
    selected ? ['case', ['==', ['get', 'adcode'], selected], 0, 0.55] : 0,
  )

  setHighlight(m, selected, districts)
}

// =====================================================================
// 编排
// =====================================================================

/**
 * 安装全部图层并同步一次显隐状态。
 *
 * 调用时机：地图首次 load、以及每次 setStyle 之后（换底图会清空所有图层）。
 * 内部每个 install* 都是幂等的，重复调用安全。
 *
 * @param {mapboxgl.Map} m
 * @param {{districts: object, boundary: object, facilities: object}} data 各 source 的初始数据
 */
export function installLayers(m, { districts, boundary, facilities }) {
  addFacilityIcons(m)
  installWmsLayers(m)
  installAdminLayers(m, { districts, boundary })
  installFacilityLayers(m, facilities)
  installAnalysisLayers(m)
  installOverlayLayers(m)

  applyVisibility(m)
  applyDistrictFocus(m, districts)
}
