"""业务异常与全局异常处理器。

对应「docs/12-Python开发规范.md」8.3 节：业务侧抛自定义异常，
接入层用 exception_handler 统一转 HTTP 响应，路由内不散落 try/except 转码。

所有错误响应统一为 `ApiResponse` 结构（见 schemas/common.py）：
    {"code": <BizCode>, "message": <描述>, "data": null, "trace_id": ...}
"""

from fastapi import Request
from fastapi.responses import JSONResponse
from loguru import logger

from app.schemas.common import BizCode


class AppError(Exception):
    """业务异常基类：携带业务状态码与对外可展示的错误信息。"""

    biz_code: BizCode = BizCode.INTERNAL_ERROR
    http_status: int = 500

    def __init__(self, message: str | None = None) -> None:
        self.message = message or self.biz_code.message
        super().__init__(self.message)


class ToolCallFailed(AppError):
    """外部依赖失败（LLM / 存储 / 第三方 API）→ 502。"""

    biz_code = BizCode.TOOL_FAILED
    http_status = 502


class KnowledgeNotFound(AppError):
    """检索无结果 / 知识不存在 → 404。"""

    biz_code = BizCode.NOT_FOUND
    http_status = 404


class RateLimited(AppError):
    """请求过于频繁 / 熔断打开 → 429。"""

    biz_code = BizCode.RATE_LIMITED
    http_status = 429


class UnauthorizedError(AppError):
    """未授权 → 401。"""

    biz_code = BizCode.UNAUTHORIZED
    http_status = 401


class ForbiddenError(AppError):
    """无权限操作 → 403。"""

    biz_code = BizCode.FORBIDDEN
    http_status = 403


def register_exception_handlers(app) -> None:
    """注册全部业务异常处理器（在 main.py 组装阶段调用）。"""

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError):
        logger.error(
            "app error: code={} http={} message={}",
            exc.biz_code.value,
            exc.http_status,
            exc.message,
        )
        return JSONResponse(
            status_code=exc.http_status,
            content={
                "code": exc.biz_code.value,
                "message": exc.message,
                "data": None,
                "trace_id": request.headers.get("x-request-id"),
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception):
        logger.exception("unhandled error: {}", exc)
        return JSONResponse(
            status_code=500,
            content={
                "code": BizCode.INTERNAL_ERROR.value,
                "message": BizCode.INTERNAL_ERROR.message,
                "data": None,
                "trace_id": request.headers.get("x-request-id"),
            },
        )
