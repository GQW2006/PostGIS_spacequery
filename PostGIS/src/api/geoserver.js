// GeoServer WMS 接入
//
// 前端通过 Vite 代理 /geoserver 访问本地 GeoServer（localhost:8080），
// 用 Mapbox 的 raster source + 256×256 瓦片模板请求 GetMap，
// 由 GeoServer 负责渲染，前端不再传输这些图层的矢量数据。

const WMS_ENDPOINT = '/geoserver/wms'

/** 已发布的 GeoServer 图层（工作区内真实存在的名字） */
export const WMS_LAYERS = {
  districts: 'chengdu:chengdu_districts',
  boundary: 'chengdu:chengdu_boundary',
  roads: 'chengdu:chengdu_roads',
  population: 'chengdu:population',
}

/**
 * 生成 Mapbox raster source 可用的 WMS 瓦片 URL。
 *
 * 为什么用 EPSG:3857 而不是 4326：
 *   WMS 1.3.0 + EPSG:4326 的轴序是「纬度在前」，若按经度在前拼 bbox 会渲染空白；
 *   3857 轴序固定为 x,y，且与 Mapbox 瓦片坐标系一致，最稳妥。
 *
 * {bbox-epsg-3857} 是 Mapbox 的瓦片占位符，每张瓦片会被替换成实际范围。
 */
export function wmsTileUrl(layerName, { format = 'image/png', styles = '' } = {}) {
  const params = new URLSearchParams({
    service: 'WMS',
    version: '1.1.1',
    request: 'GetMap',
    layers: layerName,
    styles,
    format,
    transparent: 'true',
    srs: 'EPSG:3857',
    width: '256',
    height: '256',
    bbox: '{bbox-epsg-3857}',
  })
  // URLSearchParams 会把 {} 编码成 %7B%7D，Mapbox 无法识别，这里还原占位符
  return `${WMS_ENDPOINT}?${params.toString().replace('%7Bbbox-epsg-3857%7D', '{bbox-epsg-3857}')}`
}

/** 构造 Mapbox raster source 配置 */
export function wmsSource(layerName) {
  return {
    type: 'raster',
    tiles: [wmsTileUrl(layerName)],
    tileSize: 256,
    attribution: '© GeoServer',
  }
}

/** 探测 GeoServer 是否可用（用于图层树给出提示） */
export async function pingGeoServer(timeoutMs = 4000) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)
  try {
    const res = await fetch(
      `${WMS_ENDPOINT}?service=WMS&version=1.1.1&request=GetCapabilities`,
      { signal: controller.signal },
    )
    return res.ok
  } catch {
    return false
  } finally {
    clearTimeout(timer)
  }
}
