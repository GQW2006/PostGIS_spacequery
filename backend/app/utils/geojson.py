"""GeoJSON 响应构造工具。

所有地理接口统一返回：
    {"type": "FeatureCollection", "features": [...], "meta": {"count": n, "truncated": bool}}
"""

import json


def feature(properties: dict, geometry_text: str, fid=None) -> dict:
    """把数据库返回的 ST_AsGeoJSON 文本组装成标准 Feature。"""
    f = {
        "type": "Feature",
        "properties": properties,
        "geometry": json.loads(geometry_text),
    }
    if fid is not None:
        f["id"] = fid
    return f


def feature_collection(features: list, truncated: bool = False, **extra_meta) -> dict:
    """组装 FeatureCollection 并附带 meta 统计信息。"""
    meta = {"count": len(features), "truncated": truncated}
    meta.update(extra_meta)
    return {"type": "FeatureCollection", "features": features, "meta": meta}
