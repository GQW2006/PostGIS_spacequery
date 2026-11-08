<script setup>
import { reactive } from 'vue'

import SkeletonBlock from '@/components/SkeletonBlock.vue'
import { CATEGORY_META, FACILITY_CATEGORIES, useLayerStore } from '@/stores/layer'
import { useFilterStore } from '@/stores/filter'

const layer = useLayerStore()
const filter = useFilterStore()

const expanded = reactive({ base: true, wms: true, facility: true, analysis: true })

function symbolStyle(category) {
  const { color, shape } = CATEGORY_META[category]
  return shape === 'square'
    ? { background: color, borderRadius: '1px', transform: 'rotate(45deg)' }
    : { background: color, borderRadius: '50%' }
}
</script>

<template>
  <div class="tree">
    <!-- 行政区 -->
    <div class="group">
      <button class="group-title" @click="expanded.base = !expanded.base">
        <span class="arrow" :class="{ open: expanded.base }">▸</span>行政区
      </button>
      <div v-if="expanded.base">
        <label class="row">
          <input
            type="checkbox"
            :checked="layer.geoserver.districts"
            @change="layer.toggleGeo('districts')"
          />
          <span class="dot district"></span>
          <span class="label">区县栅格</span>
          <span class="count">WMS</span>
        </label>
        <label class="row">
          <input
            type="checkbox"
            :checked="layer.geoserver.boundary"
            @change="layer.toggleGeo('boundary')"
          />
          <span class="dot boundary"></span>
          <span class="label">市界栅格</span>
          <span class="count">WMS</span>
        </label>
      </div>
    </div>

    <!-- GeoServer 服务图层 -->
    <div class="group">
      <button class="group-title" @click="expanded.wms = !expanded.wms">
        <span class="arrow" :class="{ open: expanded.wms }">▸</span>底图服务
      </button>
      <div v-if="expanded.wms">
        <label class="row">
          <input
            type="checkbox"
            :checked="layer.geoserver.roads"
            @change="layer.toggleGeo('roads')"
          />
          <span class="dot roads"></span>
          <span class="label">路网</span>
          <span class="count">WMS</span>
        </label>
        <label class="row" title="100m 人口栅格，仅在缩放级别 ≤13 时显示">
          <input
            type="checkbox"
            :checked="layer.geoserver.population"
            @change="layer.toggleGeo('population')"
          />
          <span class="dot population"></span>
          <span class="label">人口栅格</span>
          <span class="count">WMS ≤13</span>
        </label>
      </div>
    </div>

    <!-- 设施 -->
    <div class="group">
      <button class="group-title" @click="expanded.facility = !expanded.facility">
        <span class="arrow" :class="{ open: expanded.facility }">▸</span>设施
      </button>
      <div v-if="expanded.facility">
        <SkeletonBlock v-if="!filter.stats.loaded && filter.stats.loading" :rows="3" />
        <label v-for="c in FACILITY_CATEGORIES" :key="c" class="row">
          <input
            type="checkbox"
            :checked="layer.facilities[c].visible"
            @change="layer.toggleFacility(c)"
          />
          <span class="dot" :style="symbolStyle(c)"></span>
          <span class="label">{{ c }}</span>
          <span class="count num">{{ layer.facilities[c].count || '' }}</span>
        </label>
      </div>
    </div>

    <!-- 分析结果 -->
    <div class="group">
      <button class="group-title" @click="expanded.analysis = !expanded.analysis">
        <span class="arrow" :class="{ open: expanded.analysis }">▸</span>分析结果
      </button>
      <div v-if="expanded.analysis">
        <label class="row">
          <input
            type="checkbox"
            :checked="layer.analysis.coverage"
            :disabled="!layer.coverageData"
            @change="layer.toggleAnalysis('coverage')"
          />
          <span class="swatch coverage"></span>
          <span class="label">服务区</span>
        </label>
        <label class="row">
          <input
            type="checkbox"
            :checked="layer.analysis.accessibility"
            :disabled="!layer.accessibilityData"
            @change="layer.toggleAnalysis('accessibility')"
          />
          <span class="swatch accessibility"></span>
          <span class="label">可达性分级</span>
        </label>
        <label class="row">
          <input
            type="checkbox"
            :checked="layer.analysis.isochrone"
            :disabled="!layer.isochroneData"
            @change="layer.toggleAnalysis('isochrone')"
          />
          <span class="swatch isochrone"></span>
          <span class="label">等时圈</span>
        </label>
      </div>
    </div>
  </div>
</template>

<style scoped>
.tree {
  font-size: var(--fs-body);
}
.group + .group {
  margin-top: 8px;
}
.group-title {
  display: flex;
  align-items: center;
  gap: 4px;
  width: 100%;
  height: 32px;
  padding: 0;
  border: none;
  background: transparent;
  font-weight: 600;
  color: var(--c-text);
}
.arrow {
  display: inline-block;
  transition: transform 0.15s;
  color: var(--c-text-2);
  font-size: 10px;
}
.arrow.open {
  transform: rotate(90deg);
}
.row {
  display: flex;
  align-items: center;
  gap: 8px;
  height: 40px;
  padding-left: 20px;
  cursor: pointer;
}
.row:hover {
  background: var(--c-card);
}
.label {
  flex: 1;
}
.count {
  font-size: var(--fs-caption);
  color: var(--c-text-2);
  padding-right: 4px;
}
.dot {
  width: 10px;
  height: 10px;
  display: inline-block;
  box-shadow: 0 0 0 1.5px #fff, 0 0 0 2.5px rgba(0, 0, 0, 0.18);
}
.dot.district {
  background: transparent;
  border: 1.5px solid var(--c-ward-line);
  border-radius: 2px;
}
.dot.boundary {
  background: transparent;
  border: 1.5px dashed var(--c-city-line);
  border-radius: 2px;
}
.dot.roads {
  width: 12px;
  height: 3px;
  background: #8c8c8c;
  border-radius: 1px;
}
.dot.population {
  background: linear-gradient(
    90deg,
    #f6fafd 0%,
    #dee9f3 20%,
    #8fb4df 40%,
    #f6dd84 60%,
    #eb8553 80%,
    #a4285e 100%
  );
  border-radius: 2px;
}
.swatch {
  width: 10px;
  height: 10px;
  display: inline-block;
  border-radius: 2px;
}
.swatch.coverage {
  background: rgba(22, 104, 220, 0.35);
  border: 1px solid var(--c-primary);
}
.swatch.accessibility {
  background: linear-gradient(90deg, var(--c-level-d), var(--c-level-c), var(--c-level-b), var(--c-level-a));
}
.swatch.isochrone {
  background: rgba(255, 125, 0, 0.3);
  border: 1px solid var(--c-warning);
}
</style>
