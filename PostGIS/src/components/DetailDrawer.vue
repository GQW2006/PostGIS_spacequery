<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import { DEFAULT_RADIUS, useFilterStore } from '@/stores/filter'
import { CATEGORY_META } from '@/stores/layer'
import { useUiStore } from '@/stores/ui'
import { useAnalysisLayer } from '@/composables/useAnalysisLayer'
import { fetchNearby } from '@/api/facility'
import { fetchNearest } from '@/api/analysis'

const ui = useUiStore()
const filter = useFilterStore()
const { runCoverage } = useAnalysisLayer()

const districtStat = ref(null)
const nearbyCounts = ref(null)
const nearbyLoading = ref(false)
const nearestFacility = ref(null)
const nearestLoading = ref(false)

const item = computed(() => ui.drawer.data ?? {})
const isFacility = computed(() => ui.drawer.kind === 'facility')
const isDistrict = computed(() => ui.drawer.kind === 'district')
const isPoint = computed(() => ui.drawer.kind === 'point')

const categoryColor = computed(
  () => CATEGORY_META[item.value.category]?.color ?? 'var(--c-primary)',
)

const adcode = computed(() =>
  isFacility.value ? item.value.adcode : isDistrict.value ? item.value.adcode : null,
)

// 打开抽屉或切换到另一个要素时，重新加载对应区县统计 / 周边设施
watch(
  () =>
    JSON.stringify([
      ui.drawer.open,
      ui.drawer.kind,
      ui.drawer.data?.adcode,
      ui.drawer.data?.poi_id,
      ui.drawer.data?.lng,
      ui.drawer.data?.lat,
    ]),
  async () => {
    districtStat.value = null
    nearbyCounts.value = null
    nearestFacility.value = null
    if (!ui.drawer.open) return

    // 设施详情：多查一项「最近的同类设施」，用于回答"这所学校附近还有别的吗"
    if (isFacility.value) {
      await loadNearest()
    }

    // 任意点与区县点击都会带经纬度，一次点击同时给出「归属 + 周边」
    if (isPoint.value || (isDistrict.value && item.value.lng)) {
      await loadNearby()
    }
    if (isPoint.value) return
    if (!adcode.value) return
    try {
      const rows = await filter.loadDistrictStats(filter.activeType)
      districtStat.value = rows.find((r) => r.adcode === adcode.value) ?? null
    } catch {
      districtStat.value = null
    }
  },
  { immediate: true },
)

async function loadNearby() {
  nearbyLoading.value = true
  try {
    const fc = await fetchNearby({ lng: item.value.lng, lat: item.value.lat, radius: 500 })
    const counts = { 小学: 0, 中学: 0, 菜市场: 0 }
    for (const f of fc.features) counts[f.properties.category] += 1
    nearbyCounts.value = counts
  } catch {
    nearbyCounts.value = null
  } finally {
    nearbyLoading.value = false
  }
}

/**
 * 查当前设施的「最近同类」。
 * 必须把 poi_id 作为 exclude 传过去，否则 KNN 会返回它自己（距离 0）。
 */
async function loadNearest() {
  const { lon, lat, category, poi_id: poiId } = item.value
  if (!Number.isFinite(Number(lon)) || !Number.isFinite(Number(lat)) || !category) return

  nearestLoading.value = true
  try {
    const { nearest } = await fetchNearest({
      lng: Number(lon),
      lat: Number(lat),
      type: category,
      exclude: poiId,
    })
    nearestFacility.value = nearest ?? null
  } catch {
    nearestFacility.value = null
  } finally {
    nearestLoading.value = false
  }
}

/** 距离显示：1000 米以内用米，超过换成公里 */
function formatDistance(m) {
  if (!Number.isFinite(m)) return '—'
  return m < 1000 ? `${m.toFixed(1)} m` : `${(m / 1000).toFixed(2)} km`
}

/** 点击「最近同类设施」→ 飞到该设施 */
function gotoNearest() {
  const n = nearestFacility.value
  if (!n || !Number.isFinite(n.lng) || !Number.isFinite(n.lat)) return
  ui.fly(n.lng, n.lat, 16)
}

function goToMap() {
  if (isFacility.value) ui.fly(item.value.lon, item.value.lat, 15)
  else if (isPoint.value) ui.fly(item.value.lng, item.value.lat, 15)
}

async function showServiceArea() {
  const type = isFacility.value ? item.value.category : filter.activeType
  filter.setType(type)
  filter.tab = 'analysis'
  await runCoverage({ type, radius: DEFAULT_RADIUS[type], district: null })
}

function onlyThisDistrict() {
  filter.setDistrict({ adcode: item.value.adcode, name: item.value.name })
  ui.closeDrawer()
}

function onKeydown(e) {
  if (e.key === 'Escape') ui.closeDrawer()
}

onMounted(() => window.addEventListener('keydown', onKeydown))
onBeforeUnmount(() => window.removeEventListener('keydown', onKeydown))
</script>

<template>
  <transition name="slide">
    <aside v-if="ui.drawer.open" class="drawer">
      <header class="head">
        <h2 class="title">{{ item.name || '周边设施' }}</h2>
        <button class="close" aria-label="关闭" title="关闭（Esc）" @click="ui.closeDrawer()">
          ✕
        </button>
      </header>

      <div class="body">
        <!-- 设施详情 -->
        <template v-if="isFacility">
          <span class="badge">
            <i class="badge-dot" :style="{ background: categoryColor }"></i>
            {{ item.category }}
          </span>

          <dl class="fields">
            <dt>地址</dt><dd>{{ item.address || '—' }}</dd>
            <dt>区县</dt><dd>{{ item.district || '—' }}</dd>
            <dt>坐标</dt>
            <dd class="num">{{ Number(item.lon).toFixed(4) }}, {{ Number(item.lat).toFixed(4) }}</dd>
            <dt>电话</dt><dd>{{ item.tel || '—' }}</dd>
          </dl>

          <p class="section-title">最近同类设施</p>
          <p v-if="nearestLoading" class="caption">查询中…</p>
          <button v-else-if="nearestFacility" class="nearest-row" @click="gotoNearest">
            <i class="badge-dot" :style="{ background: categoryColor }"></i>
            <span class="nearest-name">{{ nearestFacility.name }}</span>
            <span class="num nearest-dist">{{ formatDistance(nearestFacility.distance_m) }}</span>
          </button>
          <p v-else class="caption">周边没有其它同类设施</p>

          <p class="section-title">所属行政区</p>
          <div class="district-card">
            <p class="district-name">{{ districtStat?.name || item.district }}</p>
            <p class="caption num">
              <template v-if="districtStat">
                {{ filter.activeType }} {{ districtStat.count }} 所 ·
                每万人 {{ districtStat.per_10k ?? '—' }} 所
              </template>
              <template v-else>统计加载中…</template>
            </p>
          </div>
        </template>

        <!-- 区县详情（含点击位置周边） -->
        <template v-else-if="isDistrict">
          <dl class="fields">
            <dt>区县码</dt><dd class="num">{{ item.adcode }}</dd>
            <dt>面积</dt><dd class="num">{{ item.area_km2 }} km²</dd>
            <dt>{{ filter.activeType }}数</dt>
            <dd class="num">{{ districtStat?.count ?? '—' }}</dd>
            <dt>每万人</dt>
            <dd class="num">{{ districtStat?.per_10k ?? '—' }} 所</dd>
            <dt>平均最近距离</dt>
            <dd class="num">{{ districtStat?.avg_nearest_m ?? '—' }} m</dd>
          </dl>

          <p class="section-title">点击位置 500 米内设施</p>
          <p v-if="nearbyLoading" class="caption">查询中…</p>
          <ul v-else-if="nearbyCounts" class="nearby">
            <li v-for="(n, c) in nearbyCounts" :key="c">
              <i class="badge-dot" :style="{ background: CATEGORY_META[c].color }"></i>
              {{ c }} <span class="num">{{ n }}</span> 个
            </li>
          </ul>
          <p v-else class="caption">附近无设施</p>

          <button class="btn-primary wide" @click="onlyThisDistrict">只看这个区</button>
        </template>

        <!-- 任意点：归属 + 周边 -->
        <template v-else-if="isPoint">
          <p class="section-title">所属行政区</p>
          <div class="district-card">
            <p class="district-name">{{ item.district?.name || '未命中行政区' }}</p>
            <p class="caption num">
              {{ Number(item.lng).toFixed(6) }}, {{ Number(item.lat).toFixed(6) }}
            </p>
          </div>

          <p class="section-title">500 米内设施</p>
          <p v-if="nearbyLoading" class="caption">查询中…</p>
          <ul v-else-if="nearbyCounts" class="nearby">
            <li v-for="(n, c) in nearbyCounts" :key="c">
              <i class="badge-dot" :style="{ background: CATEGORY_META[c].color }"></i>
              {{ c }} <span class="num">{{ n }}</span> 个
            </li>
          </ul>
          <p v-else class="caption">附近无设施</p>
        </template>
      </div>

      <footer v-if="isFacility" class="foot">
        <button class="ghost" @click="goToMap">定位到地图</button>
        <button class="btn-primary" @click="showServiceArea">查看服务范围</button>
        <button class="ghost full" disabled title="登录后可用">收藏</button>
      </footer>
    </aside>
  </transition>
</template>

<style scoped>
.drawer {
  position: absolute;
  top: 0;
  right: 0;
  width: var(--w-drawer);
  height: 100%;
  background: var(--c-panel);
  border-left: 1px solid var(--c-line);
  display: flex;
  flex-direction: column;
  z-index: 15;
  box-shadow: -4px 0 16px rgba(0, 0, 0, 0.08);
}
.slide-enter-active,
.slide-leave-active {
  transition: transform 0.2s ease-out;
}
.slide-enter-from,
.slide-leave-to {
  transform: translateX(100%);
}
.head {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 16px;
  border-bottom: 1px solid var(--c-line);
}
.title {
  flex: 1;
  margin: 0;
  font-size: var(--fs-h2);
  font-weight: 600;
}
.close {
  width: 32px;
  height: 32px;
  border: none;
  background: transparent;
  font-size: 16px;
  color: var(--c-text-2);
}
.body {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: var(--fs-caption);
  color: var(--c-text-2);
}
.badge-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
}
.fields {
  display: grid;
  grid-template-columns: 64px 1fr;
  gap: 8px 12px;
  margin: 0;
}
.fields dt {
  font-size: var(--fs-caption);
  color: var(--c-text-2);
}
.fields dd {
  margin: 0;
  font-size: var(--fs-body);
}
.section-title {
  margin: 8px 0 0;
  padding-top: 12px;
  border-top: 1px solid var(--c-line);
  font-size: var(--fs-caption);
  color: var(--c-text-2);
}
.district-card {
  padding: 12px;
  background: var(--c-card);
  border-radius: var(--radius-panel);
}
.district-name {
  margin: 0 0 4px;
  font-size: var(--fs-body);
  font-weight: 600;
}
.caption {
  margin: 0;
  font-size: var(--fs-caption);
  color: var(--c-text-2);
}
.nearby {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.nearby li {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: var(--fs-body);
}

/* 「最近同类设施」一行：整行可点，点击飞到该设施 */
.nearest-row {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 8px 12px;
  background: var(--c-card);
  border: 1px solid var(--c-line);
  border-radius: var(--radius-panel);
  font-size: var(--fs-body);
  color: var(--c-text);
  text-align: left;
}
.nearest-row:hover {
  border-color: var(--c-action);
  color: var(--c-action);
}
.nearest-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.nearest-dist {
  font-size: var(--fs-caption);
  color: var(--c-text-2);
}
.foot {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 16px;
  border-top: 1px solid var(--c-line);
}
.foot button {
  flex: 1;
  height: 36px;
}
.foot .full {
  flex-basis: 100%;
}
.ghost {
  background: var(--c-panel);
  color: var(--c-action);
  border-color: var(--c-action);
}
.wide {
  width: 100%;
  height: 36px;
}

/* <768px：抽屉占满宽度（单栏模式） */
@media (max-width: 768px) {
  .drawer {
    width: 100%;
  }
}
</style>
