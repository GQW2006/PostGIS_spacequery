"""空间分析查询服务：最近设施、区县统计、服务区覆盖、2SFCA 可达性、等时圈。

设计要点：
1. 2SFCA 与区县人口等重计算全部**离线预计算**（scripts/build_analysis.py），接口只查表；
2. 距离一律用 geography（米），禁止用度；
3. 过滤一律 ST_DWithin，不用 ST_Distance < x（避免全表扫描）。
"""

from sqlalchemy import text

from app.extensions import get_session
from app.services.facility_queries import CATEGORIES
from app.utils.geojson import feature, feature_collection

# 2SFCA 服务半径（米）
SERVICE_RADIUS = {"小学": 1000, "中学": 1500, "菜市场": 500}

# 覆盖分析结果缓存：key=(type, radius, district) -> feature collection
_COVERAGE_CACHE: dict = {}


def _validate_type(facility_type: str) -> str:
    if facility_type not in CATEGORIES:
        raise ValueError(f"type 必须是 {'/'.join(CATEGORIES)} 之一")
    return facility_type


def _validate_lnglat(lng: float, lat: float):
    if not (-180 <= lng <= 180 and -90 <= lat <= 90):
        raise ValueError("经纬度超出有效范围")


def nearest_facility(
    lng: float, lat: float, facility_type: str, exclude: str | None = None
) -> dict:
    """最近设施：KNN 排序 + geography 精确距离。

    返回坐标（lng/lat）是为了前端能一键定位到该设施。
    exclude 用于「查某个设施的最近同类」时排掉它自己，
    否则 KNN 会把自己（距离 0）排在第一。
    """
    _validate_lnglat(lng, lat)
    _validate_type(facility_type)
    sql = text(
        """
        SELECT name, district, adcode, lon, lat,
               ST_Distance(geom::geography,
                           ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography) AS distance_m
        FROM chengdu_poi
        WHERE category = :type
          AND (:exclude IS NULL OR poi_id <> :exclude)
        ORDER BY geom <-> ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)
        LIMIT 1
        """
    )
    with get_session() as session:
        row = session.execute(
            sql,
            {"lng": lng, "lat": lat, "type": facility_type, "exclude": exclude},
        ).mappings().first()

    if row is None:
        return {"nearest": None}
    return {
        "nearest": {
            "name": row["name"],
            "distance_m": round(float(row["distance_m"]), 1),
            "district": row["district"],
            "adcode": row["adcode"],
            "lng": float(row["lon"]),
            "lat": float(row["lat"]),
        }
    }


def district_stats(facility_type: str) -> list[dict]:
    """区县统计：设施数、人口、每万人设施数、平均最近距离。

    LEFT JOIN 保证无设施的区县也返回 count=0。
    """
    _validate_type(facility_type)
    sql = text(
        """
        SELECT d.adcode,
               d.name,
               COUNT(p.poi_id) AS count,
               COALESCE(dp.pop2020, 0)::bigint AS pop2020,
               ROUND((COUNT(p.poi_id) * 10000.0) /
                     NULLIF(dp.pop2020, 0), 2) AS per_10k,
               ROUND(AVG(fn.nearest_m)::numeric, 1) AS avg_nearest_m
        FROM chengdu_districts d
        LEFT JOIN district_pop dp ON dp.adcode = d.adcode
        LEFT JOIN chengdu_poi p
               ON p.adcode = d.adcode AND p.category = :type
        LEFT JOIN facility_nearest fn ON fn.poi_id = p.poi_id
        GROUP BY d.adcode, d.name, dp.pop2020
        ORDER BY d.adcode
        """
    )
    with get_session() as session:
        rows = session.execute(sql, {"type": facility_type}).mappings().all()
    return [
        {
            "adcode": r["adcode"],
            "name": r["name"],
            "count": int(r["count"]),
            "pop2020": int(r["pop2020"]),
            "per_10k": float(r["per_10k"]) if r["per_10k"] is not None else None,
            "avg_nearest_m": float(r["avg_nearest_m"])
            if r["avg_nearest_m"] is not None
            else None,
        }
        for r in rows
    ]


def coverage(facility_type: str, radius: int, district: str | None = None) -> dict:
    """服务区覆盖：缓冲区面 + 覆盖人口/覆盖率。

    覆盖人口通过「设施 → 半径内人口格网」反查后汇总，
    避免对 90 万格网逐条做 EXISTS 判断。
    """
    _validate_type(facility_type)
    if radius < 100 or radius > 5000:
        raise ValueError("radius 需在 100–5000 米之间")

    cache_key = (facility_type, radius, district)
    if cache_key in _COVERAGE_CACHE:
        return _COVERAGE_CACHE[cache_key]

    params = {"type": facility_type, "radius": radius, "district": district}

    covered_sql = text(
        """
        SELECT COALESCE(SUM(g.pop), 0) AS covered_pop
        FROM pop_grid_100m g
        WHERE g.cell_id IN (
            SELECT DISTINCT g2.cell_id
            FROM chengdu_poi p
            JOIN pop_grid_100m g2
              ON ST_DWithin(g2.geog, p.geom::geography, :radius)
            WHERE p.category = :type
              AND (:district IS NULL OR p.adcode = :district OR p.district = :district)
        )
          AND (
            :district IS NULL OR EXISTS (
                SELECT 1 FROM chengdu_districts d
                WHERE (d.adcode = :district OR d.name = :district)
                  AND ST_Intersects(d.geom, g.geom)
            )
          )
        """
    )
    total_sql = text(
        """
        SELECT COALESCE(SUM(g.pop), 0) AS total_pop
        FROM pop_grid_100m g
        WHERE (
            :district IS NULL OR EXISTS (
                SELECT 1 FROM chengdu_districts d
                WHERE (d.adcode = :district OR d.name = :district)
                  AND ST_Intersects(d.geom, g.geom)
            )
        )
        """
    )
    buffer_sql = text(
        """
        SELECT ST_AsGeoJSON(
                   ST_SimplifyPreserveTopology(
                       ST_Union(ST_Buffer(geom::geography, :radius)::geometry),
                       0.0002)
               ) AS geojson
        FROM chengdu_poi
        WHERE category = :type
          AND (:district IS NULL OR adcode = :district OR district = :district)
        """
    )

    with get_session() as session:
        covered_pop = float(session.execute(covered_sql, params).scalar() or 0)
        total_pop = float(session.execute(total_sql, params).scalar() or 0)
        geojson = session.execute(buffer_sql, params).scalar()

    pct = round(covered_pop / total_pop * 100, 2) if total_pop else 0.0
    features = (
        [feature({"kind": "coverage", "radius": radius}, geojson)] if geojson else []
    )
    result = feature_collection(features, radius=radius, type=facility_type)
    result["stats"] = {
        "covered_pop": round(covered_pop),
        "total_pop": round(total_pop),
        "coverage_pct": pct,
    }
    _COVERAGE_CACHE[cache_key] = result
    return result


def accessibility(facility_type: str) -> dict:
    """区县尺度 2SFCA 可达性分级（读取预计算表）。"""
    _validate_type(facility_type)
    sql = text(
        """
        SELECT a.adcode, a.name, a.value, a.level,
               ST_AsGeoJSON(ST_SimplifyPreserveTopology(d.geom, 0.0005)) AS geojson
        FROM accessibility_district a
        JOIN chengdu_districts d ON d.adcode = a.adcode
        WHERE a.category = :type
        ORDER BY a.adcode
        """
    )
    threshold_sql = text(
        """
        SELECT category, p25, p50, p75 FROM accessibility_thresholds WHERE category = :type
        """
    )
    try:
        with get_session() as session:
            rows = session.execute(sql, {"type": facility_type}).mappings().all()
            th = session.execute(
                threshold_sql, {"type": facility_type}
            ).mappings().first()
    except Exception as e:  # 表不存在时给出可执行的提示
        raise RuntimeError(
            "可达性预计算表不存在，请先执行 python backend/scripts/build_analysis.py"
        ) from e

    features = [
        feature(
            {
                "adcode": r["adcode"],
                "name": r["name"],
                "value": float(r["value"]),
                "level": r["level"],
            },
            r["geojson"],
            fid=r["adcode"],
        )
        for r in rows
    ]
    thresholds = (
        {
            "p25": float(th["p25"]),
            "p50": float(th["p50"]),
            "p75": float(th["p75"]),
        }
        if th
        else None
    )
    return feature_collection(
        features, method="2SFCA", thresholds=thresholds, type=facility_type
    )


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
    #        先 ST_DWithin 粗筛（走 GiST），再按 geography 真实距离排序
    snap_sql = text(
        """
        WITH pt AS (
            SELECT ST_SetSRID(ST_MakePoint(:lng, :lat), 4326) AS g
        )
        SELECT r.id                      AS edge_id,
               r.source,
               r.target,
               r.cost,
               ST_LineLocatePoint(r.geom, pt.g)                AS frac,
               ST_Distance(r.geom::geography, pt.g::geography) AS snap_m
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
            SELECT CAST(:source AS bigint) AS vid,
                   :seconds - :frac * :cost AS budget
            UNION ALL
            SELECT CAST(:target AS bigint),
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


def text_geom_to_geojson(wkt: str) -> str:
    """把 WKT 转成 GeoJSON 文本（复用数据库转换，保证精度一致）。"""
    sql = text("SELECT ST_AsGeoJSON(ST_GeomFromText(:wkt, 4326)) AS geojson")
    with get_session() as session:
        return session.execute(sql, {"wkt": wkt}).scalar()


def export_district_stats(facility_type: str) -> list[dict]:
    """导出用：区县统计明细。"""
    return district_stats(facility_type)


def export_accessibility(facility_type: str) -> dict:
    """导出用：可达性分级 FeatureCollection。"""
    return accessibility(facility_type)
