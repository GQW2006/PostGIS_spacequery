# PostGIS 多城市行政区视口查询

基于 **Flask + PostgreSQL/PostGIS** 与 **Vue3 + Mapbox GL** 的前后端分离项目。
后端按城市表配置自动拼接多城市 `UNION ALL` 查询，提供视口 BBOX 裁剪与点查面接口；
前端地图随视口（缩放/平移）联动刷新行政区面，点击面弹出所属行政区信息。

## 功能特性

- **多城市查询**：后端通过 `CITY_TABLES` 注册表按表名自动拼接多城市 `UNION ALL` 查询，新增城市只需增加一条配置
- **视口 BBOX 裁剪**：基于 `ST_MakeEnvelope` + `ST_Intersects`，按当前视口范围裁剪行政区面，统一返回 GeoJSON FeatureCollection
- **点查面接口**：基于 `ST_Contains`，查询某经纬度点所属行政区
- **视口联动**：前端监听地图 `moveend`，300ms 防抖后按当前视口请求并刷新行政区面；点击地图弹窗显示所属行政区
- **多城市选择**：前端顶部面板可勾选参与查询的城市
- **API 文档**：flask-smorest 自动生成 OpenAPI 文档（`/docs`）

## 技术栈

| 端 | 技术 |
| --- | --- |
| 后端 | Python 3 · Flask · flask-smorest · SQLAlchemy · PostgreSQL/PostGIS |
| 前端 | Vue 3 · Vite · Mapbox GL JS · axios |

## 目录结构

```
PostGIS/
├── backend/                # 后端（Flask + PostGIS）
│   ├── app/
│   │   ├── __init__.py     # 应用工厂
│   │   ├── config.py       # 配置（读取 .env 的 DATABASE_URL）
│   │   ├── extensions.py   # SQLAlchemy 引擎初始化
│   │   ├── schemas/        # marshmallow 参数/响应 Schema
│   │   ├── services/
│   │   │   ├── city_registry.py   # 多城市表配置注册表（新增城市在此配置）
│   │   │   └── geo_queries.py     # UNION 查询 / BBOX 裁剪 / 点查面
│   │   └── resources/geo.py       # flask-smorest 接口
│   ├── run.py              # 启动入口（默认 5005 端口）
│   └── requirements.txt
└── PostGIS/                # 前端（Vue3 + Vite + Mapbox GL）
    ├── src/
    │   ├── api/
    │   │   ├── http.js     # axios 实例 + 请求/响应拦截器
    │   │   └── geo.js      # 地理查询 API 封装
    │   ├── composables/useAreaLayer.js   # 视口联动图层组合式函数
    │   ├── components/MapView.vue        # 地图组件（moveend 防抖、点击弹窗）
    │   └── utils/debounce.js
    ├── .env                # Mapbox token（VITE_TOKEN）
    └── vite.config.js      # /api 代理到后端
```

## 快速开始

### 1. 数据库准备

- PostgreSQL 安装 PostGIS 扩展，创建数据库（默认 `gisdb`）
- 建表并写入行政区面数据（字段需包含 `name`、`gb`、`geom`，几何为 EPSG:4326）：

```sql
CREATE TABLE chengdu_city (
  id  SERIAL PRIMARY KEY,
  name VARCHAR(100),
  gb   VARCHAR(20),
  geom geometry(MULTIPOLYGON, 4326)
);
```

### 2. 后端

```bash
cd backend
pip install -r requirements.txt
# 按需修改 .env（DATABASE_URL）
python run.py          # 默认 http://127.0.0.1:5005
```

接口文档：<http://127.0.0.1:5005/docs>

### 3. 前端

```bash
cd PostGIS
npm install
# 复制 .env.example 为 .env 并填入 Mapbox token
npm run dev            # 默认 http://localhost:5173，/api 自动代理到后端
```

## 多城市配置（新增城市）

后端 [city_registry.py](backend/app/services/city_registry.py) 中维护 `CITY_TABLES`，
**新增城市只需在此增加一项**，接口会自动将该表并入 UNION 查询：

```python
CITY_TABLES = {
    "chengdu": {"table": "chengdu_city", "label": "成都"},
    "kunming": {"table": "kunming_city", "label": "昆明"},
    # "newcity": {"table": "newcity_table", "label": "新城市"},
}
```

前端无需改动，加载时会通过 `/api/cities` 自动获取城市列表并生成勾选控件。

## API 接口

统一返回 GeoJSON `FeatureCollection`：

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/cities` | 城市配置列表 |
| GET | `/api/areas?bbox=minx,miny,maxx,maxy&cities=chengdu,kunming` | 视口 BBOX 裁剪查询行政区面 |
| GET | `/api/areas/point?lng=&lat=&cities=` | 点查面：返回包含该点的行政区 |

参数说明：

- `bbox`：视口范围 `minx,miny,maxx,maxy`（EPSG:4326），基于 `ST_MakeEnvelope` + `ST_Intersects`
- `cities`：逗号分隔的城市 key，缺省查询全部配置城市
- `lng` / `lat`：点查询经纬度（EPSG:4326），基于 `ST_Contains`

示例：

```bash
# 查询覆盖两城的行政区
curl "http://127.0.0.1:5005/api/areas?bbox=102,24,106,32"
# 查询成都市中心的所属行政区
curl "http://127.0.0.1:5005/api/areas/point?lng=104.06&lat=30.67"
```

## 环境变量

| 文件 | 变量 | 说明 |
| --- | --- | --- |
| `backend/.env` | `DATABASE_URL` | SQLAlchemy 数据库连接串，如 `postgresql+psycopg2://user:pass@127.0.0.1:5432/gisdb` |
| `PostGIS/.env` | `VITE_TOKEN` | Mapbox GL access token |
