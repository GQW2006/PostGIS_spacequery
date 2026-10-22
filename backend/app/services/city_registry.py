"""多城市行政区表配置注册表。

新增城市只需在此字典增加一项：
  key   -> 前端请求使用的城市标识
  table -> 数据库中的行政区面表名
  label -> 显示名称
"""

CITY_TABLES = {
    "chengdu": {"table": "chengdu_city", "label": "成都"},
    "kunming": {"table": "kunming_city", "label": "昆明"},
}


def resolve_cities(cities_arg: str | None) -> list[tuple[str, dict]]:
    """把接口参数（逗号分隔的城市 key）解析为 (key, config) 列表。

    cities_arg 为空时返回全部配置城市；只允许白名单内的 key。
    """
    if not cities_arg:
        return list(CITY_TABLES.items())
    keys = [k.strip() for k in cities_arg.split(",") if k.strip()]
    unknown = [k for k in keys if k not in CITY_TABLES]
    if unknown:
        raise ValueError(f"未知城市: {', '.join(unknown)}")
    return [(k, CITY_TABLES[k]) for k in keys]


def list_cities() -> list[dict]:
    """返回配置中的全部城市信息，供前端渲染多城市选择控件。"""
    return [
        {"key": key, "table": cfg["table"], "label": cfg["label"]}
        for key, cfg in CITY_TABLES.items()
    ]
