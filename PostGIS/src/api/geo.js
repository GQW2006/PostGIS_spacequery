// 后端 Geo API 封装：基于 axios 实例，统一返回 GeoJSON FeatureCollection

import http from '@/api/http'

/** 查询配置中的城市列表 */
export function fetchCities() {
  return http.get('/cities')
}

/** 视口 BBOX 裁剪查询行政区面 */
export function fetchAreas({ bbox, cities }) {
  return http.get('/areas', {
    params: {
      bbox: bbox.join(','),
      cities: cities?.join(','),
    },
  })
}

/** 点查面：查询包含某点的行政区 */
export function fetchPointArea({ lng, lat, cities }) {
  return http.get('/areas/point', {
    params: { lng, lat, cities: cities?.join(',') },
  })
}
