<script setup>
import { ref } from 'vue'

import SearchPanel from '@/components/SearchPanel.vue'
import { fetchFacilities } from '@/api/facility'
import { useFilterStore } from '@/stores/filter'
import { useUiStore } from '@/stores/ui'
import { debounce } from '@/utils/debounce'

// 成都市域范围（搜索时用它作为全局 bbox）
const CHENGDU_BBOX = [102.99, 30.09, 104.9, 31.44]

const ui = useUiStore()
const filter = useFilterStore()

const results = ref([])
const searching = ref(false)
const showResults = ref(false)
const searchOpen = ref(false)

const doSearch = debounce(async () => {
  const kw = filter.keyword.trim()
  if (!kw) {
    results.value = []
    showResults.value = false
    return
  }
  searching.value = true
  try {
    const fc = await fetchFacilities({ bbox: CHENGDU_BBOX, name: kw, limit: 10 })
    results.value = fc.features.map((f) => ({
      ...f.properties,
      lon: f.properties.lon,
      lat: f.properties.lat,
    }))
    showResults.value = true
  } catch (e) {
    ui.showToast(e.message)
  } finally {
    searching.value = false
  }
}, 300)

function onInput() {
  doSearch()
}

function onSelect(item) {
  showResults.value = false
  searchOpen.value = false
  ui.fly(item.lon, item.lat, 15)
  ui.openDrawer('facility', item)
}

function onBlur() {
  // 延迟关闭，保证点击结果项时不会先触发 blur
  setTimeout(() => (showResults.value = false), 150)
}

function onEsc() {
  showResults.value = false
  searchOpen.value = false
}
</script>

<template>
  <header class="topbar">
    <button
      class="icon-btn"
      :title="ui.sideCollapsed ? '展开面板' : '收起面板'"
      aria-label="切换左侧面板"
      @click="ui.sideCollapsed = !ui.sideCollapsed"
    >
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M4 6h16M4 12h16M4 18h16" />
      </svg>
    </button>

    <h1 class="title">成都市公共服务设施可达性平台</h1>

    <button
      class="icon-btn search-toggle"
      aria-label="展开搜索"
      title="搜索"
      @click="searchOpen = !searchOpen"
    >
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="11" cy="11" r="7" />
        <path d="M20 20l-3.5-3.5" />
      </svg>
    </button>

    <div class="search-wrap" :class="{ open: searchOpen }">
      <input
        v-model="filter.keyword"
        class="search"
        type="text"
        placeholder="搜索学校 / 菜市场…"
        @input="onInput"
        @focus="showResults = results.length > 0"
        @blur="onBlur"
        @keyup.esc="onEsc"
      />
      <SearchPanel
        :items="results"
        :visible="showResults"
        :loading="searching"
        @select="onSelect"
      />
    </div>

    <select v-model="ui.baseMap" class="basemap" aria-label="底图切换">
      <option value="light">浅色</option>
      <option value="dark">深色</option>
      <option value="satellite">卫星</option>
    </select>

    <button
      v-if="!ui.isLoggedIn"
      class="login"
      title="登录功能待接入 JWT"
      @click="ui.showToast('登录功能待接入（演示环境）')"
    >
      登录
    </button>
    <span v-else class="avatar" title="已登录"></span>
  </header>
</template>

<style scoped>
.topbar {
  height: var(--h-topbar);
  flex: 0 0 var(--h-topbar);
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 0 16px;
  background: var(--c-panel);
  border-bottom: 1px solid var(--c-line);
  position: relative;
  z-index: 20;
}
.title {
  font-size: 18px;
  font-weight: 600;
  margin: 0;
  white-space: nowrap;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
}
.icon-btn {
  width: 32px;
  height: 32px;
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: none;
  background: transparent;
  color: var(--c-text-2);
}
.search-toggle {
  display: none;
}
.search-wrap {
  flex: 1;
  min-width: 0;
  max-width: 420px;
  position: relative;
}
.search {
  width: 100%;
  height: 36px;
  padding: 0 12px;
  border: 1px solid var(--c-line);
  border-radius: var(--radius-btn);
  font-size: var(--fs-body);
  outline: none;
}
.search:focus {
  border-color: var(--c-action);
}
.basemap {
  height: 36px;
  padding: 0 8px;
  border: 1px solid var(--c-line);
  border-radius: var(--radius-btn);
  background: var(--c-panel);
  font-size: var(--fs-body);
}
.login {
  height: 36px;
  padding: 0 16px;
  flex: 0 0 auto;
  white-space: nowrap;
  color: var(--c-action);
  border-color: var(--c-action);
}
.avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: var(--c-action);
}

/* 窄屏：搜索收进图标入口，展开后浮在顶栏下方一层 */
@media (max-width: 767px) {
  .topbar {
    gap: 6px;
  }
  .title {
    max-width: 34vw;
  }
  .basemap {
    padding: 0 4px;
  }
  .login {
    padding: 0 10px;
  }
  .search-wrap {
    display: none;
  }
  .search-wrap.open {
    display: block;
    position: absolute;
    left: 16px;
    right: 16px;
    top: calc(100% + 8px);
    max-width: none;
    z-index: 30;
  }
  .search-toggle {
    display: inline-flex;
  }
}
</style>
