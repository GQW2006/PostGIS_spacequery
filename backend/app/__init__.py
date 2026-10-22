from flask import Flask
from flask_smorest import Api
from werkzeug.exceptions import HTTPException

from app.config import Config
from app.extensions import init_engine


def create_app(config_class=Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_class)

    # 初始化数据库引擎
    init_engine(app.config["DATABASE_URL"])

    # 所有 HTTP 异常统一返回 JSON，便于前端处理
    @app.errorhandler(HTTPException)
    def handle_http_exception(e):
        return {"error": {"code": e.code, "message": e.description}}, e.code

    # 注册 flask-smorest API 与 Blueprint
    api = Api(app)
    from app.resources.geo import blp

    api.register_blueprint(blp)

    return app
