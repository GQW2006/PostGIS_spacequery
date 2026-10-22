"""地理查询接口（flask-smorest Blueprint）。"""

from flask import abort
from flask.views import MethodView
from flask_smorest import Blueprint

from app.schemas.geo import (
    BBoxQueryArgs,
    CitySchema,
    FeatureCollectionSchema,
    PointQueryArgs,
)
from app.services import city_registry
from app.services import geo_queries

blp = Blueprint(
    "geo",
    __name__,
    url_prefix="/api",
    description="PostGIS 多城市行政区查询",
)


@blp.route("/cities")
class CityList(MethodView):
    """返回配置中的全部城市，前端据此渲染多城市选择控件。"""

    @blp.response(200, CitySchema(many=True))
    def get(self):
        return city_registry.list_cities()


@blp.route("/areas")
class AreaBBox(MethodView):
    """视口 BBOX 裁剪查询（ST_MakeEnvelope + ST_Intersects）。"""

    @blp.arguments(BBoxQueryArgs, location="query")
    @blp.response(200, FeatureCollectionSchema)
    def get(self, args):
        try:
            return geo_queries.query_areas_by_bbox(
                args["bbox"], args.get("cities")
            )
        except ValueError as e:
            abort(400, message=str(e))


@blp.route("/areas/point")
class AreaPoint(MethodView):
    """点查面（ST_Contains），返回包含该点的行政区 Feature。"""

    @blp.arguments(PointQueryArgs, location="query")
    @blp.response(200, FeatureCollectionSchema)
    def get(self, args):
        try:
            return geo_queries.query_area_by_point(
                args["lng"], args["lat"], args.get("cities")
            )
        except ValueError as e:
            abort(400, message=str(e))
