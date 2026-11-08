// 空间分析相关接口

import http from '@/api/http'

/**
 * 最近设施。
 * @param {{lng:number, lat:number, type:string, exclude?:string}} params
 *   exclude 传 poi_id：查「某个设施的最近同类」时排除它自己
 */
export function fetchNearest({ lng, lat, type, exclude }) {
  return http.get('/analysis/nearest', { params: { lng, lat, type, exclude } })
}

/** 区县统计（设施数、人口、每万人设施数、平均最近距离） */
export function fetchDistrictStats(type) {
  return http.get('/analysis/district-stats', { params: { type } })
}

/** 服务区覆盖分析 */
export function fetchCoverage({ type, radius, district }) {
  return http.get('/analysis/coverage', {
    params: { type, radius, district },
  })
}

/** 2SFCA 可达性分级 */
export function fetchAccessibility(type) {
  return http.get('/analysis/accessibility', { params: { type } })
}

/** 路网等时圈 */
export function fetchIsochrone({ lng, lat, minutes = 10 }) {
  return http.get('/analysis/isochrone', {
    params: { lng, lat, minutes },
  })
}

/** 导出下载地址（交给浏览器直接下载，走 Content-Disposition） */
export function exportUrl({ kind, format = 'geojson', type = '小学' }) {
  const q = new URLSearchParams({ kind, format, type })
  return `/api/analysis/export?${q.toString()}`
}
