<script setup>
defineProps({
  rows: { type: Number, default: 3 },
})
</script>

<template>
  <div class="skeleton">
    <div v-for="i in rows" :key="i" class="bar" :style="{ width: `${100 - i * 8}%` }"></div>
  </div>
</template>

<style scoped>
.skeleton {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 8px 0;
}
.bar {
  height: 12px;
  border-radius: 4px;
  background: linear-gradient(90deg, #eef0f3 25%, #f7f8fa 37%, #eef0f3 63%);
  background-size: 400% 100%;
  animation: shimmer 1.4s ease infinite;
}
@keyframes shimmer {
  0% {
    background-position: 100% 0;
  }
  100% {
    background-position: 0 0;
  }
}
</style>
