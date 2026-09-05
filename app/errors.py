"""业务异常与全局异常处理器。

对应「docs/12-Python开发规范.md」8.3 节：业务侧抛自定义异常，
接入层用 exception_handler 统一转 HTTP 响应，路由内不散落 try/except 转码。
"""

from fastapi import Request
from fastapi.responses import JSONResponse
from loguru import logger


class AppError(Exception):
    """业务异常基类：携带对外可展示的错误信息。"""

    status_code = 500
    message = "服务内部错误"

    def __init__(self, message: str | None = None) -> None:
        if message:
            self.message = message
        super().__init__(self.message)


class ToolCallFailed(AppError):
    """外部依赖失败（LLM / 存储 / 第三方 API）→ 502。"""

    status_code = 502
    message = "外部依赖失败"


class KnowledgeNotFound(AppError):
    """检索无结果 / 知识不存在 → 404。"""

    status_code = 404
    message = "未找到相关内容"


class RateLimited(AppError):
    """请求过于频繁 / 熔断打开 → 429。"""

    status_code = 429
    message = "请求过于频繁，请稍后再试"


class UnauthorizedError(AppError):
    """未授权 → 401。"""

    status_code = 401
    message = "未授权访问"


def register_exception_handlers(app) -> None:
    """注册全部业务异常处理器（在 main.py 组装阶段调用）。"""

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError):
        logger.error("app error: status={} message={}", exc.status_code, exc.message)
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.message},
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception):
        logger.exception("unhandled error: {}", exc)
        return JSONResponse(
            status_code=500,
            content={"detail": "服务内部错误"},
        )
