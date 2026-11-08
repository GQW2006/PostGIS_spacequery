"""空间分析接口。"""

import csv
import io
import json

from flask import Response
from flask.views import MethodView
from flask_smorest import Blueprint
from werkzeug.exceptions import UnprocessableEntity

from app.schemas.analysis import (
    CoverageArgs,
    ExportArgs,
    IsochroneArgs,
    NearestArgs,
    TypeArgs,
)
from app.schemas.facility import DistrictStatSchema, NearestResponseSchema
from app.schemas.geo import FeatureCollectionSchema
from app.services import analysis_queries, facility_queries
from app.utils.errors import api_errors

blp = Blueprint(
    "analysis", __name__, url_prefix="/api/analysis", description="空间分析"
)


@blp.errorhandler(UnprocessableEntity)
def handle_validation_error(e):
    """参数校验失败统一返回 400，与业务错误的 400 保持一致。"""
    return {"message": "参数校验失败", "details": e.description}, 400


@blp.route("/nearest")
class Nearest(MethodView):
    """最近设施。"""

    @blp.arguments(NearestArgs, location="query")
    @blp.response(200, NearestResponseSchema)
    @api_errors
    def get(self, args):
        return analysis_queries.nearest_facility(
            args["lng"], args["lat"], args["type"], args.get("exclude")
        )


@blp.route("/district-stats")
class DistrictStats(MethodView):
    """区县统计（LEFT JOIN，保证无设施区县不消失）。"""

    @blp.arguments(TypeArgs, location="query")
    @blp.response(200, DistrictStatSchema(many=True))
    @api_errors
    def get(self, args):
        return analysis_queries.district_stats(args["type"])


@blp.route("/coverage")
class Coverage(MethodView):
    """服务区覆盖分析。"""

    @blp.arguments(CoverageArgs, location="query")
    @blp.response(200, FeatureCollectionSchema)
    @api_errors
    def get(self, args):
        return analysis_queries.coverage(
            args["type"], args["radius"], args.get("district")
        )


@blp.route("/accessibility")
class Accessibility(MethodView):
    """2SFCA 可达性分级（读预计算表）。"""

    @blp.arguments(TypeArgs, location="query")
    @blp.response(200, FeatureCollectionSchema)
    @api_errors
    def get(self, args):
        return analysis_queries.accessibility(args["type"])


@blp.route("/isochrone")
class Isochrone(MethodView):
    """路网等时圈。"""

    @blp.arguments(IsochroneArgs, location="query")
    @blp.response(200, FeatureCollectionSchema)
    @api_errors
    def get(self, args):
        return analysis_queries.isochrone(
            args["lng"], args["lat"], args.get("minutes", 10)
        )


@blp.route("/export")
class Export(MethodView):
    """导出区县统计 / 可达性结果（geojson 或 csv）。"""

    @blp.arguments(ExportArgs, location="query")
    @api_errors
    def get(self, args):
        kind = args["kind"]
        fmt = args.get("format", "geojson")
        facility_type = args.get("type", "小学")

        if kind == "district-stats":
            stats = analysis_queries.export_district_stats(facility_type)
            if fmt == "csv":
                return _csv_response(
                    stats,
                    ["adcode", "name", "count", "pop2020", "per_10k", "avg_nearest_m"],
                    f"district_stats_{facility_type}.csv",
                )
            payload = _stats_geojson(stats)
            return _json_response(payload, f"district_stats_{facility_type}.geojson")

        # accessibility
        fc = analysis_queries.export_accessibility(facility_type)
        if fmt == "csv":
            rows = [
                {
                    "adcode": f["properties"]["adcode"],
                    "name": f["properties"]["name"],
                    "value": f["properties"]["value"],
                    "level": f["properties"]["level"],
                }
                for f in fc["features"]
            ]
            return _csv_response(
                rows,
                ["adcode", "name", "value", "level"],
                f"accessibility_{facility_type}.csv",
            )
        return _json_response(fc, f"accessibility_{facility_type}.geojson")


def _stats_geojson(stats: list[dict]) -> dict:
    """把统计表与区县面按 adcode 合并成带属性的 FeatureCollection。"""
    geo = facility_queries.query_district_geojson()
    lookup = {f["properties"]["adcode"]: f for f in geo["features"]}
    features = []
    for row in stats:
        base = lookup.get(row["adcode"])
        if base is None:
            continue
        base["properties"].update(row)
        features.append(base)
    return {"type": "FeatureCollection", "features": features}


def _json_response(payload: dict, filename: str) -> Response:
    body = json.dumps(payload, ensure_ascii=False)
    return Response(
        body,
        mimetype="application/geo+json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _csv_response(rows: list[dict], columns: list[str], filename: str) -> Response:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    # utf-8-sig 让 Excel 正确识别中文
    return Response(
        buf.getvalue().encode("utf-8-sig"),
        mimetype="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
