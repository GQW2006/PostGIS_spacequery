// 设施（POI）相关接口

import http from '@/api/http'

/** 视口内设施 */
export function fetchFacilities({ bbox, types, district, name, limit = 3000 }) {
  return http.get('/facilities', {
    params: {
      bbox: bbox?.join(','),
      types: types?.join(','),
      district,
      name,
      limit,
    },
  })
}

/** 单个设施详情 */
export function fetchFacilityDetail(poiId) {
  return http.get(`/facilities/${poiId}`)
}

/** 附近设施（米制半径） */
export function fetchNearby({ lng, lat, radius = 1000, types }) {
  return http.get('/facilities/nearby', {
    params: { lng, lat, radius, types: types?.join(',') },
  })
}

/** 三类设施全量数量 */
export function fetchFacilityStats() {
  return http.get('/facilities/stats')
}
