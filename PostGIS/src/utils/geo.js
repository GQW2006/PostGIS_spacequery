// 轻量几何工具：点是否落在多边形内（射线法）
// 地图已加载 20 个区县面，客户端判定比再发一次请求更快。

/** 判断点是否在环内（[lng, lat] 数组） */
function inRing(point, ring) {
  const [x, y] = point
  let inside = false
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [xi, yi] = ring[i]
    const [xj, yj] = ring[j]
    const intersect = yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi
    if (intersect) inside = !inside
  }
  return inside
}

/** 判断点是否在 Polygon / MultiPolygon 内 */
export function pointInPolygon(point, geometry) {
  if (!geometry) return false
  const { type, coordinates } = geometry
  if (type === 'Polygon') {
    if (!inRing(point, coordinates[0])) return false
    return !coordinates.slice(1).some((hole) => inRing(point, hole))
  }
  if (type === 'MultiPolygon') {
    return coordinates.some((polygon) => {
      if (!inRing(point, polygon[0])) return false
      return !polygon.slice(1).some((hole) => inRing(point, hole))
    })
  }
  return false
}

/** 在区县 FeatureCollection 中找到包含该点的区县 */
export function findDistrict(featureCollection, lng, lat) {
  const hit = featureCollection?.features?.find((f) =>
    pointInPolygon([lng, lat], f.geometry),
  )
  return hit?.properties ?? null
}
