"""设施查询接口（flask-smorest Blueprint）。"""

from flask import abort
from flask.views import MethodView
from flask_smorest import Blueprint

from app.schemas.facility import (
    CategoryCountSchema,
    FacilityQueryArgs,
    NearbyQueryArgs,
)
from app.schemas.geo import FeatureCollectionSchema
from app.services import facility_queries
from app.utils.errors import api_errors
from app.utils.geojson import feature_collection

blp = Blueprint(
    "facility", __name__, url_prefix="/api", description="设施（POI）查询"
)


@blp.route("/facilities")
class FacilityList(MethodView):
    """视口内设施查询。"""

    @blp.arguments(FacilityQueryArgs, location="query")
    @blp.response(200, FeatureCollectionSchema)
    @api_errors
    def get(self, args):
        return facility_queries.query_facilities(
            bbox=args["bbox"],
            types=args.get("types"),
            district=args.get("district"),
            name=args.get("name"),
            limit=args.get("limit", 3000),
        )


@blp.route("/facilities/stats")
class FacilityStats(MethodView):
    """三类设施全量数量（供图层树显示真实数量）。"""

    @blp.response(200, CategoryCountSchema(many=True))
    @api_errors
    def get(self):
        return facility_queries.category_counts()


@blp.route("/facilities/nearby")
class FacilityNearby(MethodView):
    """附近设施查询（ST_DWithin）。"""

    @blp.arguments(NearbyQueryArgs, location="query")
    @blp.response(200, FeatureCollectionSchema)
    @api_errors
    def get(self, args):
        return facility_queries.query_nearby(
            lng=args["lng"],
            lat=args["lat"],
            radius=args.get("radius", 1000),
            types=args.get("types"),
        )


@blp.route("/facilities/<string:poi_id>")
class FacilityDetail(MethodView):
    """单个设施详情（附带所属区县）。"""

    @blp.response(200, FeatureCollectionSchema)
    @api_errors
    def get(self, poi_id):
        item = facility_queries.get_facility(poi_id)
        if item is None:
            abort(404, description=f"设施不存在：{poi_id}")
        return feature_collection([item])
