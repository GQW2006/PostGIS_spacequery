# 开发任务书（可直接交给 AI Agent 执行）

| 项 | 内容 |
| --- | --- |
| 文档版本 | v1.0 |
| 使用者 | AI 编码 Agent |
| 项目 | 成都市公共服务设施可达性 WebGIS 系统 |
| 目标岗位语境 | 个人求职作品集，**偏开发岗**，强调工程性与可讲解性 |

> **给 Agent 的指令**：本文档是唯一需求的权威来源。按 §4 的接口契约和 §7 的验收标准执行。
> 数据已经全部就绪（§2），**不要重新做数据工程**。不确定的地方查 §8 的禁止事项。

---

# 1. 项目目标

构建一个 B/S 架构的 WebGIS，展示成都市小学 / 中学 / 菜市场的空间分布，
并基于 **2SFCA 方法**给出可达性分级，支持服务区覆盖分析、路网等时圈、结果导出。

**一句话验收**：打开网页，能在地图上看到三类设施、点击查详情、切换到分析面板算出区县可达性并导出。

---

# 2. 现有资产（已就绪，直接用）

## 2.1 数据库

`postgresql://postgres:<DB_PASSWORD>@127.0.0.1:5432/gisdb`（PostgreSQL 17.11 + PostGIS 3.6.2 + pgRouting 4.0.1）

| 表 | 行数 | 关键列 | 说明 |
| --- | --- | --- | --- |
| `chengdu_boundary` | 1 | `geom` | 市域轮廓，EPSG:4326 |
| `chengdu_districts` | 20 | `adcode`, `name`, `area_km2`, `geom` | 区县面 |
| `chengdu_poi` | 3,036 | `poi_id`, `name`, `category`, `district`, `lon`, `lat`, `geom` | 设施点 |
| `chengdu_roads` | 202,077 | `id`, `name`, `road_class`, `length_m`, `geom` | 路网 |
| `chengdu_roads_routing` | 202,077 | `id`, `source`, `target`, `cost`, `reverse_cost`, `walkable`, `geom` | **pgRouting 路由边表** |
| `chengdu_roads_routing_vertices_pgr` | 168,677 | `id`, `the_geom` | 路由顶点 |
| `chengdu_pop_100m` | 1 幅 | `rast` | 人口栅格，2284×1615，值=该格人口，-1 为 nodata |

**`chengdu_poi.category` 取值固定三种**：`小学`、`中学`、`菜市场`。

## 2.2 GeoServer（已发布）

`http://localhost:8080/geoserver`，账号 `admin / geoserver`

| 图层 | 类型 |
| --- | --- |
| `chengdu:chengdu_boundary` | 面 |
| `chengdu:chengdu_districts` | 面 |
| `chengdu:chengdu_poi` | 点 |
| `chengdu:chengdu_roads` | 线 |
| `chengdu:population` | 栅格 |

## 2.3 已有代码

- `backend/`：Flask + flask-smorest，已有 `/api/cities`、`/api/areas`、`/api/areas/point` 三个接口。**沿用其目录风格扩展，不要推倒重来。**
- `PostGIS/`（前端）：Vue3 + Vite + Mapbox GL，已有地图组件与行政区图层。

---

# 3. 技术栈与约束

| 层 | 技术 | 约束 |
| --- | --- | --- |
| 后端 | Python 3.13 / Flask / flask-smorest / SQLAlchemy / psycopg2 | 接口必须自动生成 OpenAPI（flask-smorest） |
| 数据库 | PostgreSQL 17 + PostGIS 3.6 + pgRouting 4.0 | 空间查询必须走索引 |
| 前端 | Vue 3（`<script setup>`）/ Vite / Mapbox GL JS / axios / Pinia | 不要引入 Element Plus 等重型 UI 库，自写轻组件 |
| 通信 | REST + GeoJSON | 所有地理接口返回 `FeatureCollection` |

**硬性约束**

1. 坐标系一律 **EPSG:4326**；距离计算用 `geography` 类型（米），**禁止用度**。
2. 所有 SQL **参数化**，禁止字符串拼接。
3. 所有表名走白名单校验，禁止动态 SQL 拼接表名。
4. 前端只从 `/api` 和 GeoServer 取数，不直连数据库。

---

# 4. 接口契约（必须按此实现）

统一前缀 `/api`。所有地理接口返回：

```json
{ "type": "FeatureCollection", "features": [...], "meta": { "count": 342, "truncated": false } }
```

错误统一：

```json
{ "message": "bbox 格式错误，应为 minx,miny,maxx,maxy" }
```

## 4.1 设施查询

### `GET /api/facilities`

| 参数 | 类型 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- | --- |
| `bbox` | string | 是 | — | `minx,miny,maxx,maxy`，EPSG:4326 |
| `types` | string | 否 | 全部 | 逗号分隔：`小学,中学,菜市场` |
| `district` | string | 否 | — | 区县名或 adcode |
| `limit` | int | 否 | 3000 | 上限，超出抽稀并置 `truncated=true` |

**要求**：`ST_Intersects(geom, ST_MakeEnvelope(...))`，走 GiST 索引。

### `GET /api/facilities/{poi_id}`
返回单个设施属性 + 所属行政区。

### `GET /api/facilities/nearby`
| 参数 | 必填 | 说明 |
| --- | --- | --- |
| `lng` / `lat` | 是 | 中心点 |
| `radius` | 否 | 米，默认 1000 |
| `types` | 否 | 同 4.1 |

**要求**：`ST_DWithin(geom::geography, 点::geography, radius)`，按距离升序返回，含 `distance_m`。

### `GET /api/districts`
返回 20 个区县，含 `adcode`、`name`、`area_km2`，供下拉筛选。

## 4.2 分析接口

### `GET /api/analysis/nearest`
| 参数 | 必填 | 说明 |
| --- | --- | --- |
| `lng` / `lat` | 是 | 查询点 |
| `type` | 是 | `小学` / `中学` / `菜市场` |

**返回**：`{ "nearest": { "name": "...", "distance_m": 419.8, "district": "锦江区" } }`

**验收基准**：输入 `104.0658,30.6571` + `小学`，必须返回「成师附小」，`distance_m ≈ 419.8`（±1 米）。

### `GET /api/analysis/district-stats`
| 参数 | 必填 | 说明 |
| --- | --- | --- |
| `type` | 是 | 设施类型 |

**返回**：20 条记录，每条含 `adcode`、`name`、`count`、`pop2020`、`per_10k`（每万人设施数）、`avg_nearest_m`。

**要求**：用 `LEFT JOIN`，无设施的区县必须返回 `count=0`，不能消失。

### `GET /api/analysis/coverage`
| 参数 | 必填 | 说明 |
| --- | --- | --- |
| `type` | 是 | 设施类型 |
| `radius` | 是 | 米（小学建议 1000，中学 1500，菜市场 500） |
| `district` | 否 | 限定区县 |

**返回**：
```json
{ "type": "FeatureCollection", "features": [...缓冲区面...],
  "stats": { "covered_pop": 1286400, "total_pop": 14486400, "coverage_pct": 8.88 } }
```

### `GET /api/analysis/accessibility`
| 参数 | 必填 | 说明 |
| --- | --- | --- |
| `type` | 是 | 设施类型 |

**返回**：按区县或网格的可达性分级，含 `value`、`level`（`优/良/一般/差`）、`geom`。

**分级规则**：按 **分位数**（P75 / P50 / P25）分四档，**不要用固定阈值**（2SFCA 值无量纲）。

### `GET /api/analysis/isochrone`
| 参数 | 必填 | 说明 |
| --- | --- | --- |
| `lng` / `lat` | 是 | 起点 |
| `minutes` | 否 | 默认 10，可选 5/10/15 |

**实现**：起点吸附到最近路由顶点（>200 米报错「不在可达路网内」）→
`pgr_drivingDistance` 扩散 → 可达顶点做凹包（`ST_ConcaveHull`）→ 返回面。

**返回**：`{ "type": "FeatureCollection", "features": [面], "stats": { "area_km2": 3.2, "covered_pop": 45200 } }`

### `GET /api/analysis/export`
| 参数 | 说明 |
| --- | --- |
| `kind` | `district-stats` / `accessibility` |
| `format` | `geojson` / `csv` |

返回文件下载（`Content-Disposition: attachment`）。

---

# 5. 2SFCA 算法规格

**必须严格按此实现**，否则验收不过。

```
符号：
  j = 设施，i = 人口栅格单元
  S_j = 供给量，固定为 1
  P_i = 该格人口（chengdu_pop_100m 栅格值）
  d_0 = 服务半径（小学 1000m / 中学 1500m / 菜市场 500m）
  d_ij = 距离（米，geography）

第一步：R_j = S_j / Σ P_i        （对 d_ij ≤ d_0 的所有 i 求和）
第二步：A_i = Σ R_j              （对 d_ij ≤ d_0 的所有 j 求和）
```

**实现要求**

1. 距离一律用 `geography`，单位米。
2. 先在 SQL 里建"设施-格网"邻接表（只存 `d_ij ≤ d_0` 的对），两步都查它，不要算两遍。
3. **算一次存表**（`accessibility_2sfca`），接口只查表，不要每次请求重算。
4. `A_i = 0` 必须返回 0，**不能是 NULL**（远郊山区大量格网半径内无设施）。

**规模预估**：1,085 所学校 × 约 314 格 ≈ 34 万对，单机跑 10–60 秒。

---

# 6. 目录结构要求

```
backend/
  app/
    __init__.py          应用工厂
    config.py            读 .env
    extensions.py        db / ma 初始化
    schemas/
      geo.py             已有
      facility.py        新增：设施相关 marshmallow schema
      analysis.py        新增：分析相关
    services/
      city_registry.py   已有
      geo_queries.py     已有
      facility_queries.py   新增
      analysis_queries.py   新增（2SFCA、覆盖、等时圈）
    resources/
      geo.py             已有
      facility.py        新增
      analysis.py        新增
  run.py

PostGIS/src/
  api/
    http.js              已有
    geo.js               已有
    facility.js          新增
    analysis.js          新增
  stores/
    layer.js             图层状态（Pinia）
    filter.js            筛选状态
  components/
    MapView.vue          已有，扩展
    AppShell.vue         三栏布局
    LayerTree.vue        图层树
    SearchPanel.vue      搜索
    DetailDrawer.vue     右侧详情抽屉
    AnalysisPanel.vue    分析面板
    Legend.vue           图例
  composables/
    useAreaLayer.js      已有
    useFacilityLayer.js  新增
    useAnalysisLayer.js  新增
```

---

# 7. 验收标准（Agent 自测必须全部通过）

## 7.1 数据正确性

| # | 用例 | 预期 | 判定 |
| --- | --- | --- | --- |
| 1 | 天府广场 `104.0658,30.6571` 最近小学 | 成师附小，419.8 m | 名称一致，距离 ±1m |
| 2 | 同点最近中学 | 石室联合中学陕西街校区，399.1 m | 同上 |
| 3 | 同点最近菜市场 | 菜篮子向荣桥农贸市场，578.7 m | 同上 |
| 4 | 同点 1000m 内设施数 | 小学 9 / 中学 5 / 菜市场 2 | 完全一致 |
| 5 | 武侯区（510107）小学数 | 88 | 一致 |
| 6 | 设施总数 | 3,036 | 一致 |

## 7.2 接口

| # | 用例 | 预期 |
| --- | --- | --- |
| 7 | `bbox` 非法 | HTTP 400 + 说明具体错误 |
| 8 | 市域外 bbox | HTTP 200 + 空 `features`（不是 404/500） |
| 9 | 覆盖全市查询 | `features ≤ 3000` 且 `meta.truncated=true` |
| 10 | 不存在的 `poi_id` | HTTP 404 |
| 11 | `types=菜市场` | 结果 `category` 全为菜市场 |
| 12 | 同一请求连续 3 次 | 要素 ID 集合完全一致 |

## 7.3 性能

| # | 场景 | 目标 |
| --- | --- | --- |
| 13 | 视口查询 2000 点 | < 500 ms |
| 14 | 区县统计 | < 1000 ms |
| 15 | 单点 10 分钟等时圈 | < 3000 ms |
| 16 | 首屏可交互 | < 3000 ms |

## 7.4 前端

| # | 用例 | 预期 |
| --- | --- | --- |
| 17 | 连续拖动地图 10 次 | 接口请求 ≤ 2 次（300ms 防抖） |
| 18 | 点击天府广场 | 抽屉显示「锦江区」 |
| 19 | 缩放至 Z=8 | 点位聚合，不卡顿 |
| 20 | 无设施区域 | 显示「当前视口内没有设施」 |
| 21 | 后端停掉 | 轻提示 + 保留旧数据，不清空地图 |
| 22 | 关闭菜市场图层 | 点消失且图例同步移除 |

## 7.5 算法

| # | 用例 | 预期 |
| --- | --- | --- |
| 23 | 2SFCA 小样本手算对拍 | 与 SQL 相对误差 < 1% |
| 24 | 同参数跑两次 | 结果完全一致（可复现） |
| 25 | 半径内无设施的格网 | `A_i = 0`，非 NULL、非报错 |

---

# 8. 禁止事项（务必遵守）

1. **不要重做数据工程**。数据、拓扑、索引、GeoServer 发布都已完成，直接用。
2. **不要用度算距离**。必须 `geography` 或投影坐标系。
3. **不要 `ST_Distance < x` 做过滤**。会全表扫描，必须 `ST_DWithin`。
4. **不要在接口里实时算 2SFCA**。必须预计算存表。
5. **不要返回全部 3,036 条**。超 3000 抽稀并标记 `truncated`。
6. **不要用 WMS 1.3.0 + EPSG:4326 且 bbox 用经度在前**。轴序是纬度在前，会渲染空白。
7. **不要引入 Angular/React 或 Element Plus**。沿用现有 Vue3 + 自写组件。
8. **不要写死密钥/IP**。读 `.env`。
9. **不要删除已有接口** `/api/cities`、`/api/areas`、`/api/areas/point`。
10. **不要提交 `node_modules`、`venv`、`data/raw`**。

---

# 9. 交付物清单

- [ ] 后端新增 9 个接口，OpenAPI 文档可访问（`/docs`）
- [ ] 前端三个主界面：地图工作台、分析面板、详情抽屉
- [ ] 2SFCA 预计算表 + 生成脚本
- [ ] 接口自测记录（对照 §7 逐条）
- [ ] `README` 更新：启动步骤、接口清单、演示流程
- [ ] 一份 3 分钟演示脚本（讲什么、点哪里）

---

# 10. 建议实现顺序

```
第 1 步  设施查询三接口（facilities / {id} / nearby）—— 最基础，先跑通
第 2 步  区县列表 + 区县统计 —— 验证聚合 SQL
第 3 步  2SFCA 预计算（离线表）→ accessibility 接口 —— 核心算法
第 4 步  coverage 覆盖分析 —— 复用缓冲区
第 5 步  前端三栏布局 + 图层树 —— 界面骨架
第 6 步  前端设施查询 + 弹窗 + 搜索 —— 主流程
第 7 步  前端分析面板 + 图表 + 图例
第 8 步  isochrone 等时圈 —— 最后做，依赖最复杂
第 9 步  export 导出
第 10 步 性能优化 + 错误态 + 演示脚本
```

每步完成都要按 §7 跑对应验收项，不要攒到最后一起测。
