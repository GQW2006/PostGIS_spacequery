"""接口参数与响应 Schema（统一返回 GeoJSON）。"""

from marshmallow import Schema, ValidationError, fields, validates


class BBoxQueryArgs(Schema):
    bbox = fields.String(
        required=True,
        metadata={"description": "视口范围，形如 minx,miny,maxx,maxy（EPSG:4326）"},
    )
    cities = fields.String(
        required=False,
        metadata={"description": "逗号分隔的城市 key，缺省查询全部配置城市"},
    )

    @validates("bbox")
    def _check_bbox(self, value: str, **kwargs):
        parts = value.split(",")
        if len(parts) != 4:
            raise ValidationError("bbox 必须为 minx,miny,maxx,maxy 四个数值")
        try:
            nums = [float(p) for p in parts]
        except ValueError:
            raise ValidationError("bbox 必须是数字")
        if nums[0] >= nums[2] or nums[1] >= nums[3]:
            raise ValidationError("bbox 无效：max 必须大于 min")


class PointQueryArgs(Schema):
    lng = fields.Float(required=True, metadata={"description": "经度（EPSG:4326）"})
    lat = fields.Float(required=True, metadata={"description": "纬度（EPSG:4326）"})
    cities = fields.String(
        required=False,
        metadata={"description": "逗号分隔的城市 key，缺省查询全部配置城市"},
    )


class FeatureSchema(Schema):
    type = fields.String(dump_default="Feature")
    geometry = fields.Raw(allow_none=True)
    properties = fields.Dict()


class FeatureCollectionSchema(Schema):
    type = fields.String(dump_default="FeatureCollection")
    features = fields.List(fields.Nested(FeatureSchema))


class CitySchema(Schema):
    key = fields.String()
    table = fields.String()
    label = fields.String()
