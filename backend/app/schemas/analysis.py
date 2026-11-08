"""分析接口参数 Schema。"""

from marshmallow import Schema, fields, validate

from app.services.facility_queries import CATEGORIES

_CATEGORY_ONE_OF = validate.OneOf(list(CATEGORIES))


class NearestArgs(Schema):
    lng = fields.Float(required=True, metadata={"description": "查询点经度"})
    lat = fields.Float(required=True, metadata={"description": "查询点纬度"})
    type = fields.String(
        required=True, validate=_CATEGORY_ONE_OF, metadata={"description": "设施类型"}
    )
    exclude = fields.String(
        required=False,
        metadata={
            "description": "排除的设施 poi_id。查某个设施的「最近同类」时传入它自己，避免返回自身"
        },
    )


class TypeArgs(Schema):
    type = fields.String(
        required=True, validate=_CATEGORY_ONE_OF, metadata={"description": "设施类型"}
    )


class CoverageArgs(Schema):
    type = fields.String(
        required=True, validate=_CATEGORY_ONE_OF, metadata={"description": "设施类型"}
    )
    radius = fields.Integer(
        required=True,
        validate=validate.Range(min=100, max=5000),
        metadata={"description": "服务半径（米），小学建议 1000、中学 1500、菜市场 500"},
    )
    district = fields.String(
        required=False, metadata={"description": "限定区县（名称或 adcode）"}
    )


class IsochroneArgs(Schema):
    lng = fields.Float(required=True, metadata={"description": "起点经度"})
    lat = fields.Float(required=True, metadata={"description": "起点纬度"})
    minutes = fields.Integer(
        required=False,
        load_default=10,
        validate=validate.OneOf([5, 10, 15]),
        metadata={"description": "步行时间（分钟），可选 5/10/15"},
    )


class ExportArgs(Schema):
    kind = fields.String(
        required=True,
        validate=validate.OneOf(["district-stats", "accessibility"]),
        metadata={"description": "导出内容类型"},
    )
    format = fields.String(
        required=False,
        load_default="geojson",
        validate=validate.OneOf(["geojson", "csv"]),
        metadata={"description": "文件格式"},
    )
    type = fields.String(
        required=False,
        load_default="小学",
        validate=_CATEGORY_ONE_OF,
        metadata={"description": "设施类型，默认小学"},
    )
