<script setup>
import { useLayerStore } from '@/stores/layer'

const layer = useLayerStore()

function shapeStyle(item) {
  if (item.shape === 'square') {
    return { background: item.color, borderRadius: '1px', transform: 'rotate(45deg)' }
  }
  if (item.shape === 'ring') {
    return { background: 'transparent', border: `2px solid ${item.color}`, borderRadius: '2px' }
  }
  if (item.shape === 'line') {
    return { background: item.color, height: '3px', borderRadius: '1px', boxShadow: 'none' }
  }
  return { background: item.color, borderRadius: '50%' }
}
</script>

<template>
  <div class="legend">
    <template v-for="item in layer.legendItems" :key="item.key">
      <!-- 分档色带：多档栅格 / 分级设色 -->
      <div v-if="item.shape === 'ramp'" class="item item-ramp">
        <p class="ramp-title">{{ item.label }}</p>
        <ul class="ramp-list">
          <li v-for="stop in item.stops ?? []" :key="stop.label">
            <span class="ramp-swatch" :style="{ background: stop.color }"></span>
            <span class="num">{{ stop.label }}</span>
          </li>
        </ul>
        <p v-if="item.note" class="ramp-note">{{ item.note }}</p>
      </div>

      <!-- 单一符号 -->
      <div v-else class="item">
        <span class="symbol" :style="shapeStyle(item)"></span>
        <span>{{ item.label }}</span>
      </div>
    </template>
  </div>
</template>

<style scoped>
.legend {
  position: absolute;
  top: 16px;
  right: 16px;
  z-index: 5;
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 8px 12px;
  background: rgba(255, 255, 255, 0.94);
  border: 1px solid var(--c-line);
  border-radius: var(--radius-panel);
  font-size: var(--fs-caption);
  color: var(--c-text);
}
.item {
  display: flex;
  align-items: center;
  gap: 8px;
}
.item-ramp {
  display: block;
  min-width: 156px;
}
.ramp-title {
  margin: 0 0 6px;
  font-size: var(--fs-caption);
  color: var(--c-text-2);
}
.ramp-list {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.ramp-list li {
  display: flex;
  align-items: center;
  gap: 8px;
}
.ramp-swatch {
  width: 14px;
  height: 10px;
  display: inline-block;
  border: 1px solid rgba(0, 0, 0, 0.14);
}
.ramp-note {
  margin: 6px 0 0;
  font-size: 10px;
  line-height: 1.4;
  color: var(--c-text-2);
}
.symbol {
  width: 10px;
  height: 10px;
  display: inline-block;
  box-shadow: 0 0 0 1.5px #fff, 0 0 0 2.5px rgba(0, 0, 0, 0.16);
}
</style>
