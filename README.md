# 成都市公共服务设施空间分布与可达性 WebGIS

基于 **Flask + PostgreSQL/PostGIS + pgRouting** 与 **Vue3 + Vite + Pinia + Mapbox GL** 的前后端分离 WebGIS。
在地图上展示成都市小学 / 中学 / 菜市场的空间分布，支持视口联动查询、点查所属行政区、服务区覆盖分析、
**2SFCA 可达性分级**、路网等时圈与结果导出。

## 功能

- **地图工作台**：三栏布局（顶栏 / 左面板 / 地图 + 右侧抽屉 / 状态栏），浅色、深色、卫星三种底图
- **设施查询**：视口 BBOX 查询（`ST_Intersects`）、关键词搜索、附近设施（`ST_DWithin`）、三级缩放下自动点聚合
- **视口联动**：`moveend` + 300ms 防抖，缩放/平移时设施点与行政区面动态刷新
- **点查归属**：点击任意位置或设施，展示所属区县 / 街道统计（`ST_Contains`、客户端射线法）
- **图层管理**：区县界、市界、三类设施、分析结果图层显隐，图例随图层同步
- **空间分析**：
  - 服务区覆盖（缓冲区 + 覆盖人口/覆盖率）
  - 2SFCA 可达性分级（按 P25/P50/P75 分位数分为优/良/一般/差）
  - 路网等时圈（pgRouting `pgr_drivingDistance` + 凹包）
  - 导出 GeoJSON / CSV
- **OpenAPI 文档**：flask-smorest 自动生成，访问 `/docs`

## 技术栈

| 层 | 技术 |
| --- | --- |
| 前端 | Vue 3（`<script setup>`）· Vite · Pinia · Mapbox GL JS · axios |
| 后端 | Python 3.13 · Flask · flask-smorest · SQLAlchemy Core · psycopg2 |
| 数据库 | PostgreSQL 17 · PostGIS 3.6 · pgRouting 4.0 |
| 地图服务 | GeoServer（WMS 渲染区县、市界、路网、人口栅格） |
| 数据处理 | 原生 SQL 离线预计算（2SFCA、区县人口、最近设施距离） |

## 目录结构

```
PostGIS/
├── backend/
│   ├── app/
│   │   ├── __init__.py            # 应用工厂、错误格式、蓝图注册
│   │   ├── config.py              # 读 .env
│   │   ├── extensions.py          # SQLAlchemy 引擎
│   │   ├── schemas/               # geo / facility / analysis 参数与响应
│   │   ├── services/              # city_registry / geo_queries / facility_queries / analysis_queries
│   │   ├── resources/             # geo / facility / analysis 路由
│   │   └── utils/                 # GeoJSON 组装、异常转换
│   ├── scripts/build_analysis.py  # 2SFCA 等预计算脚本
│   └── run.py                     # 启动入口（5005）
├── PostGIS/
│   ├── src/
│   │   ├── api/                   # http / geo / facility / analysis / geoserver
│   │   ├── stores/                # layer / filter / ui（Pinia）
│   │   ├── composables/           # useAreaLayer / useAnalysisLayer
│   │   ├── components/            # AppShell、MapView、LayerTree、AnalysisPanel…
│   │   └── styles/tokens.css      # 设计令牌
│   └── vite.config.js             # /api → 5005，/geoserver → 8080
└── docs/                          # 需求、技术选型、开发与 UI 任务书、实现说明
```

## 快速开始

### 1. 环境

- PostgreSQL 17 + PostGIS 3.6 + pgRouting 4.0
- 数据库 `gisdb`（已在 `backend/.env` 配置）
- GeoServer（`http://localhost:8080/geoserver`，账号密码见本地配置），已发布以下图层：

| 图层 | 类型 | 用途 |
| --- | --- | --- |
| `chengdu:chengdu_districts` | 面 | 区县界（WMS） |
| `chengdu:chengdu_boundary` | 面 | 市界（WMS） |
| `chengdu:chengdu_roads` | 线 | 路网（WMS，默认关闭） |
| `chengdu:population` | 栅格 | 人口栅格（WMS，默认关闭） |
| `chengdu:chengdu_poi` | 点 | 设施点位（前端改用 `/api/facilities` 以便交互与聚合） |

### 2. 后端

```bash
cd backend
pip install -r requirements.txt

# 首次运行：生成分析预计算表（约 2 分钟，可重复执行）
python scripts/build_analysis.py

python run.py          # http://127.0.0.1:5005
```

接口文档：<http://127.0.0.1:5005/docs>

### 3. 前端

```bash
cd PostGIS
npm install            # 依赖含 pinia / mapbox-gl / axios
# 在 .env 中配置 VITE_TOKEN（Mapbox token）
npm run dev            # http://localhost:5173
```

## 接口

所有地理接口返回：

```json
{ "type": "FeatureCollection", "features": [], "meta": { "count": 0, "truncated": false } }
```

错误统一：

```json
{ "message": "bbox 格式错误，应为 minx,miny,maxx,maxy" }
```

### 设施与区县

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/facilities` | 视口查询。参数 `bbox`（必填）、`types`、`district`、`name`、`limit` |
| GET | `/api/facilities/{poi_id}` | 设施详情 + 所属区县 |
| GET | `/api/facilities/nearby` | 附近设施。参数 `lng`、`lat`、`radius`、`types` |
| GET | `/api/facilities/stats` | 三类设施全量数量 |
| GET | `/api/districts` | 20 个区县列表 |
| GET | `/api/districts/geojson` | 区县面 GeoJSON |
| GET | `/api/boundary` | 市域轮廓 GeoJSON |

### 空间分析

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/analysis/nearest` | 最近设施（`lng`、`lat`、`type`） |
| GET | `/api/analysis/district-stats` | 区县统计（`type`） |
| GET | `/api/analysis/coverage` | 服务区覆盖（`type`、`radius`、`district`） |
| GET | `/api/analysis/accessibility` | 2SFCA 可达性分级（`type`） |
| GET | `/api/analysis/isochrone` | 路网等时圈（`lng`、`lat`、`minutes`） |
| GET | `/api/analysis/export` | 导出（`kind`、`format`、`type`） |

保留的旧接口：`/api/cities`、`/api/areas`、`/api/areas/point`。

## 演示流程（约 3 分钟）

1. 打开页面，说明整体分布与左侧图层数量；
2. 搜索设施 → 地图飞行定位 → 右侧抽屉查看详情与所属区县；
3. 拖动/缩放地图，观察视口联动与聚合气泡；
4. 切到「分析」Tab：选类型、拖半径 → 覆盖人口/覆盖率 → 2SFCA 可达性分级 → 导出；
5. 计算 10 分钟等时圈，展示路网可达范围；
6. 打开 `/docs` 展示 OpenAPI 与接口分层。

## 文档

- [文档索引](docs/README.md)
- [需求规格说明书](docs/01-需求规格说明书.md)
- [技术选型文档](docs/02-技术选型文档.md)
- [开发任务书](docs/07-开发任务书（给Agent）.md)
- [UI 设计任务书](docs/08-UI设计任务书（给Agent）.md)
- [开发实现说明（含文件增删改与代码讲解）](docs/09-开发实现说明.md)

## 数据说明

- 设施数据：高德 POI（2026-11），共 3,036 条（小学 1,085 / 中学 771 / 菜市场 1,180）
- 坐标系：EPSG:4326；距离计算统一使用 `geography`（米）
- 人口：100m 栅格，值 = 该格人口，-1 为 nodata
- **仓库不包含原始数据与本地资产**：`data/`（原始 GeoJSON，约 460MB）、`_osm/`、`data_pipeline/`、`.screenshots/` 仅本地保留；数据库连接串与 Mapbox token 通过 `.env` 配置，不提交到仓库
