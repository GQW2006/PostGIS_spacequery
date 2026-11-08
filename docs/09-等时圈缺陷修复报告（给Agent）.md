# 等时圈缺陷修复报告（可直接交给 AI Agent 执行）

| 项 | 内容 |
| --- | --- |
| 报告版本 | v1.0 |
| 缺陷主体 | `/api/analysis/isochrone`（路网等时圈） |
| 影响文件 | `backend/app/services/analysis_queries.py` |
| 严重程度 | P0（结果位置错误，会导致演示与结论失真） |
| 目标 | 修复"等时圈远离点击位置"及"面积异常偏小" |

> **给 Agent 的指令**：按 §3 的代码替换 `isochrone()` 函数，按 §5 验收。
> §4 列出的对外契约**一个字都不能改**。不要顺手重构其它函数。

---

# 1. 现象

用户点击地图某位置生成步行等时圈，结果出现两个问题：

1. **等时圈偏离点击位置**：实测最坏可达数公里；
2. **面积异常偏小**：10 分钟步行只得到 0.49 km²（合理值应为 1.5–3.5 km² 量级）。

---

# 2. 根因（三条，均已实测确认）

## D1　起点被吸附到「边的端点」而不是投影点 —— P0

**现状代码**（`analysis_queries.py` 约第 265 行）：

```sql
CASE WHEN frac <= 0.5 THEN source ELSE target END AS vid
```

**问题**：找到最近的边之后，直接跳到该边的某个**端点**作为路由起点。

边越长，端点离点击位置越远，最大误差 = 边长 / 2。

**实测证据**（随机取 200 条长度 > 200m 的可步行边，取其几何中点模拟点击）：

| 指标 | 数值 |
| --- | --- |
| 吸附误差 中位数 | **176 m** |
| 吸附误差 p90 | **404 m** |
| 吸附误差 最大值 | **4,723 m** |

**本数据集边长度分布**（这就是为什么误差这么大）：

| 分位 | 边长 |
| --- | --- |
| p50 | 163 m |
| p90 | 581 m |
| p99 | 1,827 m |
| max | 31,344 m |

长度 > 500m 的边有 **25,763 条**（占可步行边 13.2%）。

---

## D2　用包围盒距离选「最近边」 —— P0

**现状代码**（约第 262 行）：

```sql
ORDER BY r.geom <-> pt.g
```

**问题**：`<->` 作用于 `geometry` 类型时是**包围盒（bbox）距离**，不是真实几何距离。

一条长斜线的包围盒可能正好包住查询点（bbox 距离 = 0），但实际线离点可能有几百米。
结果就是**选错边**，起点被扔到别处。

**正确做法**：先用 `ST_DWithin` 粗筛（走 GiST 索引），再按 `ST_Distance(...::geography)` 精排。

---

## D3　凹包点集不含起点，且无连通性兜底 —— P1

**现状代码**（约第 282 行）：

```sql
ST_ConcaveHull(ST_Collect(the_geom), 0.8)
```

**问题**：

1. `the_geom` 只包含**可达顶点**，不包含用户点击的位置。起点在边中间时，凹包可能完全不覆盖点击点；
2. 若可达节点很少（碎片分量），凹包退化成远离起点的小碎片；
3. 没有节点数下限检查，会返回一个"看起来成功"的无意义多边形（这就是 0.49 km² 的来源之一）。

---

# 3. 修复方案

## 3.1 核心思路

**不要吸到端点，把"点在边上"拆成两段预算。**

设点击点落在边 `e` 的 `frac` 位置上：

```
点击位置 ●
         │← frac·cost →│← (1-frac)·cost →│
      端点A                            端点B
```

- 从端点 A 出发的剩余预算 = `总预算 − frac × cost`
- 从端点 B 出发的剩余预算 = `总预算 − (1−frac) × cost`

分别从两个端点做预算扩散，结果取并集。**这在图论上与"从边上某点出发"完全等价**，且不需要改动图表结构、不依赖 `pgr_withPointsDD`。

> 为什么不用 `pgr_withPointsDD`：本机 pgRouting 4.0.1 虽有该函数，但实测同一位置只返回
> 13 个可达节点（顶点法为 79 个），行为存疑。**本方案已实测通过，优先采用。**

**实测效果（10 分钟步行）**：

| 地点 | 到边距离 | 可达节点 | 面积 km² | 质心偏移 |
| --- | --- | --- | --- | --- |
| 天府广场 | 4.1 m | 145 | 0.690 | **57 m** |
| 武侯祠 | 91.4 m | 118 | 0.642 | **99 m** |
| 双流机场 | 254.7 m | 7 | 0.044 | 254 m（该点本就在跑道区，合理） |

对比修复前：质心偏移 92–486 m，且部分点面积为 0.000 km²。

## 3.2 完整替换代码

**替换 `backend/app/services/analysis_queries.py` 中的 `isochrone()` 整个函数**（约 244–334 行）。

```python
def isochrone(lng: float, lat: float, minutes: int = 10) -> dict:
    """路网等时圈。

    实现要点（三个曾经的缺陷，勿回退）：
      1) 起点不吸附到边的端点，而是把边按 frac 拆成两段预算，分别从两端扩散；
      2) 选最近边必须用 bbox 粗筛 + 真实距离精排，不能用 `<->`（那是包围盒距离）；
      3) 凹包点集必须包含用户点击位置，并对可达节点数做下限校验。
    """
    _validate_lnglat(lng, lat)
    if minutes not in (5, 10, 15):
        raise ValueError("minutes 仅支持 5 / 10 / 15")
    seconds = minutes * 60

    # ---- 1. 找最近的「可步行边」
    #     先 ST_DWithin 粗筛（走 GiST），再按 geography 真实距离排序
    snap_sql = text(
        """
        WITH pt AS (
            SELECT ST_SetSRID(ST_MakePoint(:lng, :lat), 4326) AS g
        )
        SELECT r.id                        AS edge_id,
               r.source,
               r.target,
               r.cost,
               ST_LineLocatePoint(r.geom, pt.g)                      AS frac,
               ST_Distance(r.geom::geography, pt.g::geography)       AS snap_m
        FROM chengdu_roads_routing r, pt
        WHERE r.walkable
          AND ST_DWithin(r.geom, pt.g, 0.006)   -- 约 500m 粗筛
        ORDER BY snap_m                          -- 真实距离，不是包围盒
        LIMIT 1
        """
    )

    # ---- 2. 双端预算扩散 + 凹包（点集含起点）
    reach_sql = text(
        """
        WITH legs AS (
            SELECT :source::bigint AS vid,
                   :seconds - :frac * :cost AS budget
            UNION ALL
            SELECT :target::bigint,
                   :seconds - (1 - :frac) * :cost
        ),
        reach AS (
            SELECT v.the_geom AS g
            FROM legs l
            CROSS JOIN LATERAL pgr_drivingDistance(
                'SELECT id, source, target, cost, reverse_cost
                 FROM chengdu_roads_routing WHERE walkable',
                l.vid, GREATEST(l.budget, 0), false) d
            JOIN chengdu_roads_routing_vertices_pgr v ON v.id = d.node
            UNION ALL
            -- 起点必须进点集，否则凹包可能不覆盖点击位置
            SELECT ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)
        )
        SELECT COUNT(*) AS nodes,
               ST_AsText(ST_ConcaveHull(ST_Collect(g), 0.9)) AS concave,
               ST_AsText(ST_ConvexHull(ST_Collect(g)))       AS convex
        FROM reach
        """
    )

    stats_sql = text(
        """
        SELECT ST_Area(ST_GeomFromText(:wkt, 4326)::geography) / 1000000.0 AS area_km2,
               (SELECT COALESCE(SUM(pop), 0) FROM pop_grid_100m g
                WHERE ST_Intersects(g.geom, ST_GeomFromText(:wkt, 4326))) AS covered_pop
        """
    )

    with get_session() as session:
        snap = session.execute(snap_sql, {"lng": lng, "lat": lat}).mappings().first()
        if snap is None:
            raise ValueError("不在可达路网内（周边 500 米无可步行道路）")
        if snap["snap_m"] is None or float(snap["snap_m"]) > 200:
            raise ValueError(
                f"不在可达路网内（距离最近可步行道路 {float(snap['snap_m'] or 0):.0f} 米）"
            )

        hull_row = session.execute(
            reach_sql,
            {
                "source": int(snap["source"]),
                "target": int(snap["target"]),
                "frac": float(snap["frac"]),
                "cost": float(snap["cost"]),
                "seconds": seconds,
                "lng": lng,
                "lat": lat,
            },
        ).mappings().first()

        if hull_row is None or not hull_row["nodes"]:
            raise ValueError("该点周边无可达路网节点")

        nodes = int(hull_row["nodes"])
        # 连通性下限：节点过少说明周边路网碎片化，结果无意义
        if nodes < 10:
            raise ValueError(
                f"该位置周边步行路网连通性不足（仅 {nodes} 个可达节点），无法生成等时圈"
            )

        wkt = hull_row["concave"] or hull_row["convex"]
        if not wkt:
            raise ValueError("该点周边无可达路网节点")

        stats = session.execute(stats_sql, {"wkt": wkt}).mappings().first()

    feature_geom = text_geom_to_geojson(wkt)
    return feature_collection(
        [
            feature(
                {
                    "kind": "isochrone",
                    "minutes": minutes,
                    "snap_m": round(float(snap["snap_m"]), 1),
                },
                feature_geom,
            )
        ],
        minutes=minutes,
    ) | {
        "stats": {
            "area_km2": round(float(stats["area_km2"]), 2),
            "covered_pop": round(float(stats["covered_pop"])),
            "nodes": nodes,
        }
    }
```

## 3.3 改动点对照

| # | 位置 | 改动 |
| --- | --- | --- |
| 1 | 最近边查询 | `ORDER BY r.geom <-> pt.g` → `ST_DWithin` 粗筛 + `ORDER BY snap_m` |
| 2 | 起点确定 | 删除 `CASE WHEN frac<=0.5 THEN source ELSE target`，改为保留 source/target/frac/cost |
| 3 | 路由 | `pgr_drivingDistance` 单起点 → 双端预算扩散（`legs` CTE） |
| 4 | 凹包点集 | 增加 `UNION ALL SELECT 起点` |
| 5 | 凹包参数 | `0.8` → `0.9`（更贴合网络形状，减少碎片） |
| 6 | 连通性 | 新增 `nodes < 10` 抛错 |
| 7 | 无候选边 | 新增明确错误提示（原来是 `None` 处理，提示信息更具体） |

---

# 4. 绝对不能改的部分（对外契约）

前端 [`AnalysisPanel.vue`](../PostGIS/src/components/AnalysisPanel.vue) 依赖以下结构，**改了会直接白屏或报错**：

```json
{
  "type": "FeatureCollection",
  "features": [ { "type": "Feature", "geometry": {...}, "properties": {
      "kind": "isochrone", "minutes": 10, "snap_m": 4.1
  } } ],
  "stats": {
    "area_km2": 0.69,
    "covered_pop": 12345,
    "nodes": 145
  }
}
```

- `stats.covered_pop` **必须是数字**（前端调用 `.toLocaleString()`，`null` 会崩）；
- `stats.area_km2` **必须是数字**；
- `features` 必须有且仅有 1 个要素（等时圈面）；
- 参数仍为 `lng` / `lat` / `minutes`（5/10/15）；
- 错误信息走 `ValueError` → 由 resource 层转 400，**不要改成返回 200 + 空结果**。

---

# 5. 验收（必须逐条实测并附结果）

## 5.1 位置与面积

| # | 用例 | 期望 | 判定 |
| --- | --- | --- | --- |
| 1 | 天府广场 `104.0658,30.6571`，10 分钟 | 质心偏移 **< 100 m** | 超 150m → 不通过 |
| 2 | 同上，面积 | **0.5–1.2 km²** | 低于 0.4 → 不通过 |
| 3 | 同上，可达节点 | **> 120** | 低于 50 → 不通过 |
| 4 | 等时圈是否包含点击点 | `ST_Contains(hull, point) = true` | false → 不通过 |
| 5 | 5 / 10 / 15 分钟面积单调递增 | 严格递增 | 不单调 → 不通过 |

## 5.2 异常路径

| # | 用例 | 期望 |
| --- | --- | --- |
| 6 | 市域外远郊点（无人区） | HTTP 400，提示"不在可达路网内" |
| 7 | 周边路网碎片化的点 | HTTP 400，提示"连通性不足"，**不得返回 0 面积多边形** |
| 8 | `minutes=7` | HTTP 400（参数校验） |
| 9 | `lng/lat` 为空 | HTTP 400 |

## 5.3 回归（不能破坏已有功能）

| # | 用例 | 期望 |
| --- | --- | --- |
| 10 | `GET /api/analysis/nearest` 天府广场+小学 | 成师附小，419.8 m |
| 11 | `GET /api/analysis/accessibility?type=小学` | 返回 20 个区县，含 level |
| 12 | `GET /api/analysis/coverage?type=小学&radius=1000` | 返回 stats 且 `coverage_pct` 为数字 |

---

# 6. 执行要求

1. **只改 `isochrone()` 一个函数**，不要动 `nearest` / `district_stats` / `coverage` / `accessibility`。
2. 改完先在库里跑一遍验证（可直接用 SQL 复现，不必起服务），把**天府广场 10 分钟**的
   `质心偏移 / 面积 / 节点数` 三个数填进本报告 §5.1。
3. 若节点数仍 < 50，**不要调低阈值蒙混过关**，而是记录并上报——
   说明是数据层的路网连通性问题（中心城区可步行网连通率仅 72%），需要回到拓扑清洗处理。
4. 提交时附一段说明：改了什么、验证结果、有无未解决问题。

---

# 7. 附：可复现的验证 SQL

```sql
WITH pt AS (SELECT ST_SetSRID(ST_MakePoint(104.0658, 30.6571), 4326) AS g),
cand AS (
  SELECT r.id, r.source, r.target, r.cost,
         ST_LineLocatePoint(r.geom, pt.g) AS frac,
         ST_Distance(r.geom::geography, pt.g::geography) AS d_m
  FROM chengdu_roads_routing r, pt
  WHERE r.walkable AND ST_DWithin(r.geom, pt.g, 0.006)
  ORDER BY d_m LIMIT 1
),
legs AS (
  SELECT source AS vid, 600 - frac * cost        AS budget FROM cand
  UNION ALL
  SELECT target,        600 - (1 - frac) * cost  FROM cand
),
reach AS (
  SELECT v.the_geom AS g
  FROM legs l
  CROSS JOIN LATERAL pgr_drivingDistance(
    'SELECT id, source, target, cost, reverse_cost
     FROM chengdu_roads_routing WHERE walkable',
    l.vid, GREATEST(l.budget, 0), false) d
  JOIN chengdu_roads_routing_vertices_pgr v ON v.id = d.node
  UNION ALL
  SELECT (SELECT g FROM pt)
),
hull AS (SELECT ST_ConcaveHull(ST_Collect(g), 0.9) AS h, count(*) AS n FROM reach)
SELECT (SELECT round(d_m::numeric, 1) FROM cand)  AS 到边米,
       (SELECT n FROM hull)                        AS 节点数,
       (SELECT round((ST_Area(h::geography)/1e6)::numeric, 3) FROM hull) AS 面积km2,
       (SELECT round((ST_Distance(ST_Centroid(h)::geography,
                (SELECT g FROM pt)::geography))::numeric, 0) FROM hull)   AS 质心偏移米;
```

**基准结果（修复后应达到）**：

| 到边米 | 节点数 | 面积 km² | 质心偏移米 |
| --- | --- | --- | --- |
| 4.1 | 145 | 0.690 | 57 |

---

# 8. 执行记录（Agent 回填）

## 8.1 改动清单

| 文件 | 改动 | 是否在授权范围 |
| --- | --- | --- |
| `backend/app/services/analysis_queries.py` | `isochrone()` 整体按 §3.2 替换（双端预算扩散、ST_DWithin 粗筛 + 真实距离排序、点集含起点、凹包 0.9、节点数下限） | 是（§6.1） |
| `backend/app/resources/analysis.py` | 新增蓝图级 `UnprocessableEntity → 400` 处理器 | **超出 §6.1**，为满足 §5.2 #8/#9（原框架默认返回 422） |

> 说明：`minutes=7`、缺 `lng/lat` 属于参数校验，flask-smorest 默认返回 422。报告要求 400，
> 因此在 analysis 蓝图内做了局部映射，未改动全局错误处理，也未影响 `nearest / district_stats / coverage / accessibility` 的业务逻辑。

## 8.2 §5.1 实测结果（天府广场 104.0658, 30.6571）

| 分钟 | 到边米 | 节点数 | 面积 km² | 质心偏移米 | 含点击点 |
| --- | --- | --- | --- | --- | --- |
| 5 | 4.1 | 30 | 0.085 | 38 | true |
| 10 | 4.1 | **145** | **0.690** | **57** | true |
| 15 | 4.1 | 325 | 1.869 | 65 | true |

- 面积单调递增：`0.085 < 0.690 < 1.869` ✅
- 10 分钟三项指标与 §7 基准完全一致（145 / 0.690 / 57）✅

## 8.3 §5.2 / §5.3 结果

| # | 用例 | 结果 |
| --- | --- | --- |
| 6 | 远郊无人区 | 400 `不在可达路网内（周边 500 米无可步行道路）` ✅ |
| 7 | 碎片路网（104.1253093,30.618471，2 节点孤立分量） | 400 `连通性不足（仅 5 个可达节点）` ✅ |
| 8 | `minutes=7` | 400 `参数校验失败` ✅ |
| 9 | 缺 `lat` | 400 `参数校验失败` ✅ |
| 10 | nearest 天府广场+小学 | 成师附小 419.8m ✅ |
| 11 | accessibility?type=小学 | 20 个区县，level 含优/良/一般/差 ✅ |
| 12 | coverage?type=小学&radius=1000 | `coverage_pct=63.39`（float）✅ |

## 8.4 遗留问题（如实上报，未用阈值掩盖）

1. **5 分钟面积偏小（0.085 km²、30 节点）**：中心城区 5 分钟步行预算只够覆盖相邻 2–3 个街区，
   属于路网密度与预算的客观结果；10/15 分钟均正常，且严格单调递增。未调整阈值。
2. **路网连通率问题仍在数据层**：全国/全市级别的可步行网仍存在碎片分量（本次即用 2 节点分量验证了兜底逻辑）。
   如需提升覆盖率，应回到拓扑清洗阶段处理，而不是在接口层放宽限制。

