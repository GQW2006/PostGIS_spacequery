<script setup>
import { computed, ref, watch } from 'vue'

import SkeletonBlock from '@/components/SkeletonBlock.vue'
import { exportUrl } from '@/api/analysis'
import { useAnalysisLayer } from '@/composables/useAnalysisLayer'
import { useFilterStore } from '@/stores/filter'
import { FACILITY_CATEGORIES, useLayerStore } from '@/stores/layer'
import { useUiStore } from '@/stores/ui'

const filter = useFilterStore()
const layer = useLayerStore()
const ui = useUiStore()

const { loading, error, runCoverage, runAccessibility, runIsochrone } =
  useAnalysisLayer()

const coverageStats = ref(null)
const isoStats = ref(null)
const isoMinutes = ref(10)
const lastAction = ref('coverage')

const exportHref = computed(() =>
  exportUrl({ kind: 'accessibility', format: 'geojson', type: filter.activeType }),
)
const coverageHref = computed(() =>
  exportUrl({ kind: 'district-stats', format: 'csv', type: filter.activeType }),
)

function selectType(type) {
  filter.setType(type)
}

async function applyCoverage() {
  lastAction.value = 'coverage'
  coverageStats.value = await runCoverage({
    type: filter.activeType,
    radius: filter.radius,
    district: filter.district?.name,
  })
}

async function applyAccessibility() {
  lastAction.value = 'accessibility'
  await runAccessibility(filter.activeType)
}

async function applyIsochrone() {
  lastAction.value = 'isochrone'
  isoStats.value = await runIsochrone({
    lng: ui.center.lng,
    lat: ui.center.lat,
    minutes: isoMinutes.value,
  })
}

function retry() {
  if (lastAction.value === 'coverage') applyCoverage()
  else if (lastAction.value === 'accessibility') applyAccessibility()
  else applyIsochrone()
}

// 切换类型后清空旧统计，避免数字与当前类型不一致
watch(
  () => filter.activeType,
  () => {
    coverageStats.value = null
    isoStats.value = null
  },
)
</script>

<template>
  <div class="analysis">
    <!-- 设施类型 -->
    <section>
      <p class="label">设施类型</p>
      <div class="radios">
        <label v-for="c in FACILITY_CATEGORIES" :key="c" class="radio">
          <input
            type="radio"
            name="facility-type"
            :value="c"
            :checked="filter.activeType === c"
            @change="selectType(c)"
          />
          {{ c }}
        </label>
      </div>
    </section>

    <!-- 服务半径 -->
    <section class="block">
      <div class="row-between">
        <span class="label">服务半径</span>
        <span class="value num">{{ filter.radius }}<span class="unit">m</span></span>
      </div>
      <input
        v-model.number="filter.radius"
        class="slider"
        type="range"
        min="500"
        max="2000"
        step="100"
        @change="applyCoverage"
      />
      <div class="ticks"><span>500</span><span>1000</span><span>2000</span></div>
    </section>

    <!-- 统计卡片：加载中显示骨架屏 -->
    <section class="card">
      <SkeletonBlock v-if="loading" :rows="2" />
      <template v-else>
        <div class="stat">
          <span class="label">覆盖人口</span>
          <span v-if="coverageStats" class="value num">
            {{ coverageStats.covered_pop.toLocaleString() }}<span class="unit">人</span>
          </span>
          <span v-else class="num-empty">尚未计算</span>
        </div>
        <div class="stat">
          <span class="label">覆盖率</span>
          <span v-if="coverageStats" class="value num">
            {{ coverageStats.coverage_pct.toFixed(1) }}<span class="unit">%</span>
          </span>
          <span v-else class="num-empty">尚未计算</span>
        </div>
      </template>
    </section>

    <p v-if="error" class="error">
      {{ error }}
      <button class="retry" @click="retry">重试</button>
    </p>

    <button class="btn-primary wide" :disabled="loading" @click="applyCoverage">
      在地图上显示覆盖范围
    </button>

    <button
      class="text-toggle"
      :disabled="!layer.coverageData"
      @click="layer.toggleAnalysis('coverage')"
    >
      {{ layer.analysis.coverage ? '隐藏覆盖图层' : '显示覆盖图层' }}
    </button>

    <!-- 2SFCA 可达性 -->
    <section class="block divider">
      <div class="row-between">
        <span class="label">可达性分级（2SFCA）</span>
        <span class="caption">按分位数分级</span>
      </div>
      <button class="btn-primary wide" :disabled="loading" @click="applyAccessibility">
        计算区县可达性
      </button>
      <div class="links">
        <a :href="exportHref" download>导出可达性 GeoJSON</a>
        <a :href="coverageHref" download>导出区县统计 CSV</a>
      </div>
    </section>

    <!-- 等时圈 -->
    <section class="block divider">
      <div class="row-between">
        <span class="label">路网等时圈</span>
        <select v-model.number="isoMinutes" class="select">
          <option :value="5">5 分钟</option>
          <option :value="10">10 分钟</option>
          <option :value="15">15 分钟</option>
        </select>
      </div>
      <p class="caption">起点取当前地图中心</p>
      <button class="btn-primary wide" :disabled="loading" @click="applyIsochrone">
        计算等时圈
      </button>
      <p v-if="isoStats" class="iso num">
        覆盖面积 {{ isoStats.area_km2 }} km² · 覆盖人口
        {{ isoStats.covered_pop.toLocaleString() }} 人
      </p>
    </section>
  </div>
</template>

<style scoped>
.analysis {
  display: flex;
  flex-direction: column;
  gap: 16px;
  font-size: var(--fs-body);
}
.label {
  margin: 0;
  font-size: var(--fs-caption);
  color: var(--c-text-2);
}
.caption {
  font-size: var(--fs-caption);
  color: var(--c-text-2);
}
.radios {
  display: flex;
  gap: 12px;
  margin-top: 8px;
}
.radio {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  cursor: pointer;
}
.block {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.row-between {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
}
.value {
  font-size: var(--fs-number);
  font-weight: 600;
  color: var(--c-text);
}
.unit {
  margin-left: 4px;
  font-size: var(--fs-ui);
  font-weight: 400;
  color: var(--c-text-2);
}
.num-empty {
  font-size: var(--fs-body);
  font-weight: 400;
  color: var(--c-text-2);
}
.slider {
  width: 100%;
  accent-color: var(--c-action);
}
.ticks {
  display: flex;
  justify-content: space-between;
  font-size: var(--fs-caption);
  color: var(--c-text-2);
}
.card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 16px;
  background: var(--c-card);
  border-radius: var(--radius-panel);
}
.stat {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
}
.stat .value {
  font-size: var(--fs-number);
}
.wide {
  width: 100%;
  height: 36px;
}
.text-toggle {
  align-self: flex-start;
  height: auto;
  padding: 0;
  border: none;
  background: none;
  color: var(--c-action);
  font-size: var(--fs-ui);
}
.text-toggle:disabled {
  color: var(--c-text-disabled);
}
.divider {
  border-top: 1px solid var(--c-line);
  padding-top: 16px;
}
.links {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.links a {
  font-size: var(--fs-caption);
  color: var(--c-action);
  text-decoration: none;
}
.error {
  margin: 0;
  font-size: var(--fs-caption);
  color: var(--c-error);
}
.retry {
  height: auto;
  padding: 0;
  margin-left: 8px;
  border: none;
  background: none;
  color: var(--c-action);
  font-size: var(--fs-ui);
  text-decoration: underline;
  text-underline-offset: 2px;
}
.select {
  height: 36px;
  border: 1px solid var(--c-line);
  border-radius: var(--radius-btn);
  font-size: var(--fs-caption);
}
.iso {
  margin: 0;
  font-size: var(--fs-caption);
  color: var(--c-text-2);
}
</style>
