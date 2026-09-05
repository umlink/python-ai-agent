"""业务异常与全局异常处理器。

对应「docs/12-Python开发规范.md」8.3 节：业务侧抛自定义异常，
接入层用 exception_handler 统一转 HTTP 响应，路由内不散落 try/except 转码。

所有错误响应统一为 `ApiResponse` 结构（见 schemas/common.py）：
    {"code": <BizCode>, "message": <描述>, "data": null, "trace_id": ...}
"""

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from loguru import logger

from app.schemas.common import BizCode


def _trace_of(request: Request) -> str | None:
    """从 request.state 取追踪 ID（由 RequestID 中间件预置）。"""
    return getattr(request.state, "trace_id", None)


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
                "trace_id": _trace_of(request),
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        """参数校验错误（默认 422 原生结构）→ 统一转成 ApiResponse，code=40001。"""
        first = exc.errors()[0] if exc.errors() else {}
        loc = ".".join(str(x) for x in first.get("loc", []))
        detail = first.get("msg", "")
        message = f"参数校验失败：{loc} {detail}" if loc else f"参数校验失败：{detail}"
        return JSONResponse(
            status_code=422,
            content={
                "code": BizCode.PARAM_ERROR.value,
                "message": message,
                "data": None,
                "trace_id": _trace_of(request),
            },
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        """FastAPI 原生 HTTPException（如星号路由 404）→ 统一 ApiResponse。"""
        status_code = exc.status_code
        code = {
            401: BizCode.UNAUTHORIZED.value,
            403: BizCode.FORBIDDEN.value,
            404: BizCode.NOT_FOUND.value,
        }.get(status_code, BizCode.INTERNAL_ERROR.value)
        return JSONResponse(
            status_code=status_code,
            content={
                "code": code,
                "message": str(exc.detail),
                "data": None,
                "trace_id": _trace_of(request),
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
                "trace_id": _trace_of(request),
            },
        )
