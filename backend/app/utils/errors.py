"""统一的接口异常转换。

业务层只抛 ValueError / RuntimeError，资源层用装饰器统一转成 HTTP 状态码，
避免每个视图函数重复写 try/except。
"""

from functools import wraps

from flask import abort


def api_errors(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except ValueError as e:
            abort(400, description=str(e))
        except RuntimeError as e:
            abort(503, description=str(e))

    return wrapper
