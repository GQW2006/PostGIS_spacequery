/**
 * 地图相关常量。
 *
 * 只放"不变的配置"，不放逻辑。
 * 凡是 Mapbox paint 用到的颜色，都必须在注释里标明它对应的
 * tokens.css 变量——因为 Mapbox 的 paint 读不到 CSS 变量。
 */

// Mapbox 访问令牌（来自 .env 的 VITE_TOKEN）
export const MAPBOX_TOKEN = import.meta.env.VITE_TOKEN

/** 三种底图 */
export const MAP_STYLES = {
  light: 'mapbox://styles/mapbox/light-v11',
  dark: 'mapbox://styles/mapbox/dark-v11',
  satellite: 'mapbox://styles/mapbox/satellite-streets-v12',
}

/** 成都市域范围（首屏定位） */
export const CHENGDU_BOUNDS = [
  [102.99, 30.09],
  [104.9, 31.44],
]

/** 设施类型 → Mapbox 图层 id */
export const CATEGORY_LAYER = {
  小学: 'poi-school',
  中学: 'poi-middle',
  菜市场: 'poi-market',
}

/** 设施图层 id 列表（用于 queryRenderedFeatures 与光标样式） */
export const POI_LAYERS = Object.values(CATEGORY_LAYER)

/** 空的 FeatureCollection，用作各 GeoJSON source 的初始数据 */
export const EMPTY_FC = { type: 'FeatureCollection', features: [] }

// ---- 地图描边颜色 ----
// Mapbox 的 paint 不读 CSS 变量，这里与 tokens.css 的
// --c-ward-line / --c-city-line 保持同值；改令牌时两处都要改。
export const WARD_LINE_COLOR = '#8a8f99'
export const CITY_LINE_COLOR = '#1f2329'
