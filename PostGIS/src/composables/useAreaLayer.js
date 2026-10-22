// 行政区图层组合式函数：视口联动刷新（moveend 防抖）+ 点查面

import { ref } from 'vue'

import { fetchAreas, fetchPointArea } from '@/api/geo'
import { debounce } from '@/utils/debounce'

const SOURCE_ID = 'city-areas'
const FILL_ID = 'city-areas-fill'
const LINE_ID = 'city-areas-line'

export function useAreaLayer(mapRef, getCities) {
  const loading = ref(false)
  const error = ref('')

  /** 更新 GeoJSON 数据源；首次时创建 Source + Fill/Line 图层 */
  function ensureLayers(map, featureCollection) {
    if (map.getSource(SOURCE_ID)) {
      map.getSource(SOURCE_ID).setData(featureCollection)
      return
    }
    map.addSource(SOURCE_ID, { type: 'geojson', data: featureCollection })
    map.addLayer({
      id: FILL_ID,
      type: 'fill',
      source: SOURCE_ID,
      paint: { 'fill-color': '#3b82f6', 'fill-opacity': 0.35 },
    })
    map.addLayer({
      id: LINE_ID,
      type: 'line',
      source: SOURCE_ID,
      paint: { 'line-color': '#1d4ed8', 'line-width': 2 },
    })
  }

  /** 按当前视口 BBOX 请求并刷新行政区面（内部已防抖） */
  const refresh = debounce(async () => {
    const map = mapRef.value
    if (!map || !map.isStyleLoaded()) return
    const b = map.getBounds()
    loading.value = true
    try {
      const featureCollection = await fetchAreas({
        bbox: [b.getWest(), b.getSouth(), b.getEast(), b.getNorth()],
        cities: getCities(),
      })
      ensureLayers(map, featureCollection)
      error.value = ''
    } catch (e) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }, 300)

  /** 点查面：返回包含该点的行政区（统一 FeatureCollection） */
  async function queryPoint(lngLat) {
    return fetchPointArea({
      lng: lngLat.lng,
      lat: lngLat.lat,
      cities: getCities(),
    })
  }

  return { loading, error, refresh, queryPoint }
}
