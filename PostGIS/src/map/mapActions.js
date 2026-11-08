/**
 * 地图运行时行为：拉数据、响应点击、跟随容器尺寸。
 *
 * layers.js 管"画什么"（静态定义），这里管"动起来会发生什么"。
 * 两者分开是因为修改频率不同：调样式只动 layers.js，
 * 改请求逻辑或交互只动这个文件。
 *
 * 用工厂函数是为了显式注入依赖（map、各 store、局部 ref），
 * 而不是在模块里 import 一堆单例——这样这堆函数可以单独测试。
 */

import { fetchBoundaryGeoJSON, fetchDistrictGeoJSON } from '@/api/geo'
import { fetchFacilities, fetchFacilityStats } from '@/api/facility'
import { EMPTY_FC, POI_LAYERS } from '@/map/constants'
import { debounce } from '@/utils/debounce'
import { findDistrict } from '@/utils/geo'

/**
 * @param {object} deps
 * @param {import('vue').Ref} deps.map        地图实例
 * @param {import('vue').Ref} deps.mapEl      地图容器 DOM
 * @param {import('vue').Ref} deps.districtsFC 区县 FeatureCollection
 * @param {import('vue').Ref} deps.boundaryFC  市界 FeatureCollection
 * @param {import('vue').Ref} deps.lastFacilityFC 最近一次设施 FeatureCollection
 * @param {object} deps.layer  useLayerStore()
 * @param {object} deps.filter useFilterStore()
 * @param {object} deps.ui     useUiStore()
 */
export function createMapActions({
  map,
  mapEl,
  districtsFC,
  boundaryFC,
  lastFacilityFC,
  layer,
  filter,
  ui,
}) {
  /**
   * Mapbox 在容器尺寸为 0 时会产生 NaN 变换矩阵，
   * 拿到的 bounds 就是 NaN，此时任何请求都没有意义。
   */
  function hasValidBounds(m) {
    const b = m.getBounds()
    const values = [b.getWest(), b.getSouth(), b.getEast(), b.getNorth()]
    return (
      values.every(Number.isFinite) &&
      b.getWest() < b.getEast() &&
      b.getSouth() < b.getNorth()
    )
  }

  /** 按当前视口拉取设施点 */
  async function loadFacilities() {
    const m = map.value
    if (!m || !hasValidBounds(m)) return

    // 一类设施都没勾选时不必请求，直接清空
    if (layer.visibleTypes.length === 0) {
      lastFacilityFC.value = EMPTY_FC
      m.getSource('facilities')?.setData(EMPTY_FC)
      filter.stats.count = 0
      filter.stats.loaded = true
      return
    }

    filter.stats.loading = true
    try {
      const b = m.getBounds()
      const fc = await fetchFacilities({
        bbox: [b.getWest(), b.getSouth(), b.getEast(), b.getNorth()],
        types: layer.visibleTypes,
        district: filter.district?.adcode,
        limit: 3000,
      })
      lastFacilityFC.value = fc
      m.getSource('facilities')?.setData(fc)
      filter.stats.count = fc.meta.count
      filter.stats.truncated = fc.meta.truncated
      filter.stats.error = ''
    } catch (e) {
      // 错误态：保留旧数据，只记录错误，不清空地图
      filter.stats.error = e.message
    } finally {
      filter.stats.loading = false
      filter.stats.loaded = true
    }
  }

  /** 视口联动用：300ms 防抖，连续拖动只发最后一次 */
  const refresh = debounce(loadFacilities, 300)

  /** 加载行政区与市界（数据量小，一次性取回常驻内存） */
  async function loadReferenceLayers() {
    const [districts, boundary] = await Promise.all([
      fetchDistrictGeoJSON(),
      fetchBoundaryGeoJSON(),
    ])
    districtsFC.value = districts
    boundaryFC.value = boundary

    const m = map.value
    if (!m) return
    m.getSource('districts')?.setData(districts)
    m.getSource('boundary')?.setData(boundary)
  }

  /** 三类设施的全省数量（左侧图层树显示） */
  async function loadCounts() {
    try {
      const counts = await fetchFacilityStats()
      layer.setCounts(counts)
    } catch {
      // 数量加载失败不影响主流程，静默忽略
    }
  }

  /** 在地图上标出点击位置 */
  function updateClickPoint(lng, lat) {
    map.value?.getSource('click-point')?.setData({
      type: 'FeatureCollection',
      features: [
        {
          type: 'Feature',
          geometry: { type: 'Point', coordinates: [lng, lat] },
          properties: {},
        },
      ],
    })
  }

  /**
   * 点击地图：三级优先——设施 > 聚合气泡 > 空白处。
   */
  async function onClick(e) {
    const m = map.value
    if (!m) return

    // ① 点到设施点
    const poi = m.queryRenderedFeatures(e.point, { layers: POI_LAYERS })
    if (poi.length > 0) {
      ui.openDrawer('facility', { ...poi[0].properties })
      return
    }

    // ② 点到聚合气泡：放大到能展开的级别
    const cluster = m.queryRenderedFeatures(e.point, { layers: ['poi-cluster'] })
    if (cluster.length > 0) {
      const src = m.getSource('facilities')
      // 注意：getClusterExpansionZoom 是回调式 API，不是 Promise。
      // 直接 await 会拿到 source 本身，并在内部抛 "is not a function"。
      const zoom = await new Promise((resolve, reject) => {
        src.getClusterExpansionZoom(cluster[0].properties.cluster_id, (err, value) => {
          if (err) reject(err)
          else resolve(value)
        })
      }).catch(() => null)

      if (Number.isFinite(zoom)) {
        m.easeTo({ center: cluster[0].geometry.coordinates, zoom })
      }
      return
    }

    // ③ 空白处：WMS 栅格无法 queryRenderedFeatures，
    //    所以用区县 GeoJSON 在客户端做点面判定（射线法）
    const { lng, lat } = e.lngLat
    updateClickPoint(lng, lat)

    const district = findDistrict(districtsFC.value, lng, lat)
    if (district) {
      ui.openDrawer('district', { ...district, lng, lat })
    } else {
      ui.openDrawer('point', { lng, lat, district: null })
    }
  }

  /** 取消「只看某个区」 */
  function clearDistrict() {
    filter.setDistrict(null)
  }

  /** 容器尺寸变化后让地图重新布局（面板收起、窗口缩放都要调） */
  function resizeMap() {
    const m = map.value
    if (!m) return
    const el = mapEl.value
    if (el && el.clientWidth > 0 && el.clientHeight > 0) m.resize()
  }

  return {
    hasValidBounds,
    loadFacilities,
    refresh,
    loadReferenceLayers,
    loadCounts,
    updateClickPoint,
    onClick,
    clearDistrict,
    resizeMap,
  }
}
