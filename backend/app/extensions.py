"""数据库引擎初始化。

行政区数据由城市表配置动态驱动，不引入 ORM 模型，
统一使用 SQLAlchemy Core 的 text() 执行原生 PostGIS SQL。
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

_engine = None
_session_factory = None


def init_engine(database_url: str) -> None:
    """根据 DATABASE_URL 创建引擎与会话工厂。"""
    global _engine, _session_factory
    _engine = create_engine(database_url, pool_pre_ping=True, future=True)
    _session_factory = sessionmaker(bind=_engine, expire_on_commit=False)


def get_session():
    """返回一个 SQLAlchemy 会话（上下文管理器，自动关闭）。"""
    if _session_factory is None:
        raise RuntimeError("数据库引擎未初始化，请先调用 init_engine")
    return _session_factory()
