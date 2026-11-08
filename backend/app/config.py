import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


class Config:
    """应用配置，数据库连接等敏感信息从 .env 读取。"""

    API_TITLE = "PostGIS Geo API"
    API_VERSION = "1.0.0"
    OPENAPI_VERSION = "3.0.2"
    OPENAPI_URL_PREFIX = "/"
    OPENAPI_SWAGGER_UI_PATH = "/docs"
    OPENAPI_REDOC_PATH = "/redoc"

    # 数据库连接串必须由 backend/.env 提供，不在代码中保留任何凭据
    DATABASE_URL = os.getenv("DATABASE_URL")
    if not DATABASE_URL:
        raise RuntimeError(
            "缺少 DATABASE_URL：请复制 backend/.env.example 为 backend/.env 并填写连接串"
        )
