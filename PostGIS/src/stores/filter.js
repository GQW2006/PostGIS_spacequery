// 筛选与请求状态（Pinia）：设施类型、半径、区县、关键词、加载/错误状态

import { reactive, ref } from 'vue'
import { defineStore } from 'pinia'

import { fetchDistrictStats } from '@/api/analysis'

/** 各类型的默认服务半径（米），与后端 2SFCA 口径一致 */
export const DEFAULT_RADIUS = { 小学: 1000, 中学: 1500, 菜市场: 500 }

export const useFilterStore = defineStore('filter', () => {
  const activeType = ref('小学') // 分析面板当前类型
  const radius = ref(1000) // 覆盖分析半径
  const district = ref(null) // 只看某个区：{ adcode, name }
  const keyword = ref('') // 顶栏搜索词
  const tab = ref('layers') // 左面板 Tab：layers | analysis

  // 视口请求状态（六个状态里的 加载中/空数据/错误 都读这里）
  const stats = reactive({
    loading: false,
    loaded: false,
    error: '',
    count: 0,
    truncated: false,
  })

  // 区县统计缓存：type -> rows
  const districtStats = ref([])
  const _cache = new Map()

  async function loadDistrictStats(type) {
    if (_cache.has(type)) {
      districtStats.value = _cache.get(type)
      return _cache.get(type)
    }
    const rows = await fetchDistrictStats(type)
    _cache.set(type, rows)
    districtStats.value = rows
    return rows
  }

  function setType(type) {
    activeType.value = type
    radius.value = DEFAULT_RADIUS[type] ?? 1000
  }

  function setDistrict(d) {
    district.value = d
  }

  function resetViewportState() {
    stats.count = 0
    stats.truncated = false
    stats.error = ''
  }

  return {
    activeType,
    radius,
    district,
    keyword,
    tab,
    stats,
    districtStats,
    loadDistrictStats,
    setType,
    setDistrict,
    resetViewportState,
  }
})
