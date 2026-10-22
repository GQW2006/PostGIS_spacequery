"""PostGIS 空间查询服务。

- query_areas_by_bbox : 视口 BBOX 裁剪（ST_MakeEnvelope + ST_Intersects）
- query_area_by_point : 点查面（ST_Contains）
- 两者均基于城市表配置自动拼接 UNION ALL，统一返回 GeoJSON。
"""

import json

from sqlalchemy import text

from app.extensions import get_session
from app.services import city_registry

# 多表共用的公共列（两张表列结构可能不同，UNION 时只取公共列）
_COMMON_COLUMNS = "name, gb, geom"


def _build_union(cities_arg: str | None) -> tuple[str, dict]:
    """根据配置拼接多城市 UNION ALL 子查询，返回 (sql, params)。

    表名来自配置白名单（不信任用户输入）；城市 key 通过绑定参数注入。
    """
    items = city_registry.resolve_cities(cities_arg)
    selects, params = [], {}
    for i, (key, cfg) in enumerate(items):
        selects.append(
            f"SELECT {_COMMON_COLUMNS}, :city_{i} AS city FROM {cfg['table']}"
        )
        params[f"city_{i}"] = key
    return " UNION ALL ".join(selects), params


def _to_feature(name, gb, city, geojson_text: str) -> dict:
    """将查询行转换为 GeoJSON Feature。"""
    return {
        "type": "Feature",
        "properties": {"name": name, "gb": gb, "city": city},
        "geometry": json.loads(geojson_text),
    }


def query_areas_by_bbox(
    bbox_str: str, cities_arg: str | None = None
) -> dict:
    """视口 BBOX 裁剪查询，返回 FeatureCollection。

    bbox_str 形如 "minx,miny,maxx,maxy"，坐标系 EPSG:4326。
    """
    try:
        minx, miny, maxx, maxy = (float(x) for x in bbox_str.split(","))
    except (ValueError, AttributeError):
        raise ValueError("bbox 格式应为 minx,miny,maxx,maxy 四个数字")
    if minx >= maxx or miny >= maxy:
        raise ValueError("bbox 参数无效：maxx/maxy 必须大于 minx/miny")

    union, params = _build_union(cities_arg)
    sql = text(
        f"""
        SELECT name, gb, city, ST_AsGeoJSON(geom) AS geojson
        FROM ( {union} ) AS all_areas
        WHERE ST_Intersects(
            geom,
            ST_MakeEnvelope(:minx, :miny, :maxx, :maxy, 4326)
        )
        """
    )
    params.update(minx=minx, miny=miny, maxx=maxx, maxy=maxy)

    with get_session() as session:
        rows = session.execute(sql, params).mappings().all()

    features = [
        _to_feature(r["name"], r["gb"], r["city"], r["geojson"]) for r in rows
    ]
    return {"type": "FeatureCollection", "features": features}


def query_area_by_point(
    lng: float, lat: float, cities_arg: str | None = None
) -> dict:
    """点查面：返回包含该点的行政区 FeatureCollection（至多一个）。"""
    union, params = _build_union(cities_arg)
    sql = text(
        f"""
        SELECT name, gb, city, ST_AsGeoJSON(geom) AS geojson
        FROM ( {union} ) AS all_areas
        WHERE ST_Contains(
            geom,
            ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)
        )
        LIMIT 1
        """
    )
    params.update(lng=float(lng), lat=float(lat))

    with get_session() as session:
        row = session.execute(sql, params).mappings().first()

    features = (
        [_to_feature(row["name"], row["gb"], row["city"], row["geojson"])]
        if row
        else []
    )
    return {"type": "FeatureCollection", "features": features}
