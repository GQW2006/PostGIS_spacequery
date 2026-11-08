"""设施（POI）与区县查询服务。

表名、字段名全部硬编码在白名单内，参数一律绑定，不拼接 SQL。
"""

from sqlalchemy import text

from app.extensions import get_session
from app.utils.geojson import feature, feature_collection

# 允许的设施类型白名单
CATEGORIES = ("小学", "中学", "菜市场")


def parse_bbox(bbox: str) -> tuple[float, float, float, float]:
    """解析并校验 bbox=minx,miny,maxx,maxy（EPSG:4326）。"""
    if not bbox:
        raise ValueError("缺少参数 bbox，格式为 minx,miny,maxx,maxy")
    parts = bbox.split(",")
    if len(parts) != 4:
        raise ValueError("bbox 格式错误，应为 minx,miny,maxx,maxy")
    try:
        minx, miny, maxx, maxy = (float(p) for p in parts)
    except ValueError:
        raise ValueError("bbox 必须是 4 个数字")
    if not (-180 <= minx < maxx <= 180 and -90 <= miny < maxy <= 90):
        raise ValueError("bbox 范围非法：需满足 minx<maxx、miny<maxy 且经纬度在有效区间")
    return minx, miny, maxx, maxy


def parse_types(types: str | None) -> list[str] | None:
    """解析 types=小学,中学；未传返回 None 表示全部。"""
    if not types:
        return None
    items = [t.strip() for t in types.split(",") if t.strip()]
    unknown = [t for t in items if t not in CATEGORIES]
    if unknown:
        raise ValueError(f"未知设施类型：{','.join(unknown)}；可选：{','.join(CATEGORIES)}")
    return items


def _poi_properties(row) -> dict:
    return {
        "poi_id": row["poi_id"],
        "name": row["name"],
        "category": row["category"],
        "type": row["type"],
        "address": row["address"],
        "district": row["district"],
        "adcode": row["adcode"],
        "tel": row["tel"],
        "lon": row["lon"],
        "lat": row["lat"],
    }


def query_facilities(
    bbox: str,
    types: str | None = None,
    district: str | None = None,
    name: str | None = None,
    limit: int = 3000,
) -> dict:
    """视口 BBOX 查询设施点（ST_Intersects，走 GiST 索引）。

    name 用于关键词搜索（ILIKE 模糊匹配）。
    """
    minx, miny, maxx, maxy = parse_bbox(bbox)
    cats = parse_types(types)
    limit = max(1, min(int(limit), 3000))

    sql = text(
        """
        SELECT poi_id, name, category, type, address, district, adcode, tel, lon, lat,
               ST_AsGeoJSON(geom) AS geojson
        FROM chengdu_poi
        WHERE geom && ST_MakeEnvelope(:minx, :miny, :maxx, :maxy, 4326)
          AND ST_Intersects(geom, ST_MakeEnvelope(:minx, :miny, :maxx, :maxy, 4326))
          AND (:types IS NULL OR category = ANY(:types))
          AND (:district IS NULL OR adcode = :district OR district = :district)
          AND (:name IS NULL OR name ILIKE :name_pattern)
        ORDER BY poi_id
        LIMIT :limit
        """
    )
    with get_session() as session:
        rows = session.execute(
            sql,
            {
                "minx": minx,
                "miny": miny,
                "maxx": maxx,
                "maxy": maxy,
                "types": cats,
                "district": district,
                "name": name,
                "name_pattern": f"%{name}%" if name else None,
                # 多取 1 条用于判断是否被截断
                "limit": limit + 1,
            },
        ).mappings().all()

    truncated = len(rows) > limit
    rows = rows[:limit]
    features = [
        feature(_poi_properties(r), r["geojson"], fid=r["poi_id"]) for r in rows
    ]
    return feature_collection(features, truncated=truncated, limit=limit)


def get_facility(poi_id: str) -> dict | None:
    """按 poi_id 查询单个设施，附带所属区县信息。"""
    sql = text(
        """
        SELECT p.poi_id, p.name, p.category, p.type, p.address, p.district, p.adcode,
               p.tel, p.lon, p.lat,
               d.name AS district_name, d.area_km2,
               ST_AsGeoJSON(p.geom) AS geojson
        FROM chengdu_poi p
        LEFT JOIN chengdu_districts d ON d.adcode = p.adcode
        WHERE p.poi_id = :poi_id
        """
    )
    with get_session() as session:
        row = session.execute(sql, {"poi_id": poi_id}).mappings().first()

    if row is None:
        return None

    props = _poi_properties(row)
    props["district_name"] = row["district_name"]
    props["area_km2"] = row["area_km2"]
    return feature(props, row["geojson"], fid=row["poi_id"])


def query_nearby(
    lng: float,
    lat: float,
    radius: int = 1000,
    types: str | None = None,
    limit: int = 200,
) -> dict:
    """附近设施：ST_DWithin + geography（米制），按距离升序。"""
    if not (-180 <= lng <= 180 and -90 <= lat <= 90):
        raise ValueError("经纬度超出有效范围")
    if radius <= 0 or radius > 50000:
        raise ValueError("radius 需在 1–50000 米之间")
    cats = parse_types(types)

    sql = text(
        """
        SELECT poi_id, name, category, type, address, district, adcode, tel, lon, lat,
               ST_Distance(geom::geography,
                           ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography) AS distance_m,
               ST_AsGeoJSON(geom) AS geojson
        FROM chengdu_poi
        WHERE ST_DWithin(geom::geography,
                         ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography, :radius)
          AND (:types IS NULL OR category = ANY(:types))
        ORDER BY distance_m
        LIMIT :limit
        """
    )
    with get_session() as session:
        rows = session.execute(
            sql,
            {
                "lng": lng,
                "lat": lat,
                "radius": radius,
                "types": cats,
                "limit": limit,
            },
        ).mappings().all()

    features = []
    for r in rows:
        props = _poi_properties(r)
        props["distance_m"] = round(float(r["distance_m"]), 1)
        features.append(feature(props, r["geojson"], fid=r["poi_id"]))
    return feature_collection(features, radius=radius)


def category_counts() -> list[dict]:
    """三类设施的全量数量，供前端图层树显示真实数量。"""
    sql = text("SELECT category, COUNT(*) AS n FROM chengdu_poi GROUP BY category")
    with get_session() as session:
        rows = session.execute(sql).mappings().all()
    counts = {r["category"]: int(r["n"]) for r in rows}
    return [
        {"category": c, "count": counts.get(c, 0)} for c in CATEGORIES
    ]


def query_districts() -> list[dict]:
    """区县列表（供筛选下拉）。"""
    sql = text(
        """
        SELECT d.adcode, d.name, d.level, d.center_lon, d.center_lat, d.area_km2
        FROM chengdu_districts d
        ORDER BY d.adcode
        """
    )
    with get_session() as session:
        rows = session.execute(sql).mappings().all()
    return [dict(r) for r in rows]


def query_district_geojson() -> dict:
    """20 个区县面（简化后返回），用于地图面图层与点击识别。"""
    sql = text(
        """
        SELECT adcode, name, area_km2,
               ST_AsGeoJSON(ST_SimplifyPreserveTopology(geom, 0.0005)) AS geojson
        FROM chengdu_districts
        ORDER BY adcode
        """
    )
    with get_session() as session:
        rows = session.execute(sql).mappings().all()
    features = [
        feature(
            {"adcode": r["adcode"], "name": r["name"], "area_km2": r["area_km2"]},
            r["geojson"],
            fid=r["adcode"],
        )
        for r in rows
    ]
    return feature_collection(features)


def query_boundary_geojson() -> dict:
    """成都市域轮廓。"""
    sql = text(
        """
        SELECT name, adcode,
               ST_AsGeoJSON(ST_SimplifyPreserveTopology(geom, 0.0005)) AS geojson
        FROM chengdu_boundary
        """
    )
    with get_session() as session:
        rows = session.execute(sql).mappings().all()
    features = [
        feature({"name": r["name"], "adcode": r["adcode"]}, r["geojson"])
        for r in rows
    ]
    return feature_collection(features)
