// 分析结果图层组合式函数：覆盖分析 / 2SFCA 可达性 / 等时圈

import { ref } from 'vue'

import { fetchAccessibility, fetchCoverage, fetchIsochrone } from '@/api/analysis'
import { useLayerStore } from '@/stores/layer'

export function useAnalysisLayer() {
  const layer = useLayerStore()
  const loading = ref(false)
  const error = ref('')

  async function runCoverage({ type, radius, district }) {
    loading.value = true
    try {
      const fc = await fetchCoverage({ type, radius, district })
      layer.coverageData = fc
      layer.analysis.coverage = true
      error.value = ''
      return fc.stats
    } catch (e) {
      error.value = e.message
      // 错误态：保留旧数据，不清空地图
      return null
    } finally {
      loading.value = false
    }
  }

  async function runAccessibility(type) {
    loading.value = true
    try {
      const fc = await fetchAccessibility(type)
      layer.accessibilityData = fc
      layer.analysis.accessibility = true
      error.value = ''
      return fc
    } catch (e) {
      error.value = e.message
      return null
    } finally {
      loading.value = false
    }
  }

  async function runIsochrone({ lng, lat, minutes }) {
    loading.value = true
    try {
      const fc = await fetchIsochrone({ lng, lat, minutes })
      layer.isochroneData = fc
      layer.analysis.isochrone = true
      error.value = ''
      return fc.stats
    } catch (e) {
      error.value = e.message
      return null
    } finally {
      loading.value = false
    }
  }

  return { loading, error, runCoverage, runAccessibility, runIsochrone }
}
