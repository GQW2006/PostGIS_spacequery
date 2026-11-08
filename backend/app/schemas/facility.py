"""设施查询参数 Schema（marshmallow 4）。

注意：marshmallow 4 不再接受任意关键字参数作为元数据，
描述信息必须放在 metadata={} 中。
"""

from marshmallow import Schema, fields


class FacilityQueryArgs(Schema):
    bbox = fields.String(
        required=True,
        metadata={"description": "视口范围 minx,miny,maxx,maxy（EPSG:4326）"},
    )
    types = fields.String(
        required=False,
        metadata={"description": "逗号分隔的设施类型：小学,中学,菜市场"},
    )
    district = fields.String(
        required=False, metadata={"description": "区县名称或 adcode"}
    )
    name = fields.String(
        required=False, metadata={"description": "设施名称关键词（模糊匹配）"}
    )
    limit = fields.Integer(
        required=False,
        load_default=3000,
        metadata={"description": "返回上限，默认 3000，超出截断"},
    )


class NearbyQueryArgs(Schema):
    lng = fields.Float(required=True, metadata={"description": "中心点经度"})
    lat = fields.Float(required=True, metadata={"description": "中心点纬度"})
    radius = fields.Integer(
        required=False, load_default=1000, metadata={"description": "半径（米）"}
    )
    types = fields.String(
        required=False,
        metadata={"description": "逗号分隔的设施类型，缺省全部"},
    )


class DistrictSchema(Schema):
    adcode = fields.String()
    name = fields.String()
    level = fields.String()
    center_lon = fields.Float(allow_none=True)
    center_lat = fields.Float(allow_none=True)
    area_km2 = fields.Float(allow_none=True)


class CategoryCountSchema(Schema):
    category = fields.String()
    count = fields.Integer()


class NearestSchema(Schema):
    name = fields.String(allow_none=True)
    distance_m = fields.Float(allow_none=True)
    district = fields.String(allow_none=True)
    adcode = fields.String(allow_none=True)
    # 返回坐标是为了前端能"点击定位到该设施"
    lng = fields.Float(allow_none=True)
    lat = fields.Float(allow_none=True)


class NearestResponseSchema(Schema):
    nearest = fields.Nested(NearestSchema, allow_none=True)


class DistrictStatSchema(Schema):
    adcode = fields.String()
    name = fields.String()
    count = fields.Integer()
    pop2020 = fields.Integer()
    per_10k = fields.Float(allow_none=True)
    avg_nearest_m = fields.Float(allow_none=True)
