from flask import Flask, jsonify
from flask_smorest import Api
from werkzeug.exceptions import HTTPException

from app.config import Config
from app.extensions import init_engine


def create_app(config_class=Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_class)

    # 初始化数据库引擎（SQLAlchemy Core + psycopg2）
    init_engine(app.config["DATABASE_URL"])

    # 注册 flask-smorest API 与各业务 Blueprint
    api = Api(app)

    from app.resources.analysis import blp as analysis_blp
    from app.resources.facility import blp as facility_blp
    from app.resources.geo import blp as geo_blp

    api.register_blueprint(geo_blp)
    api.register_blueprint(facility_blp)
    api.register_blueprint(analysis_blp)

    # 统一错误结构：{"message": "..."}
    @app.errorhandler(HTTPException)
    def handle_http_exception(e):
        desc = e.description
        if isinstance(desc, dict):
            return jsonify({"message": "参数校验失败", "details": desc}), e.code
        return jsonify({"message": desc}), e.code

    return app
