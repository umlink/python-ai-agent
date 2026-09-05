"""统一响应封装与业务状态码。

所有接口成功响应统一包装为 `ApiResponse`：
    {"code": 0, "message": "成功", "data": {...}}

业务状态码用 `BizCode` 枚举统一管理（code + 描述），新增业务错误
在枚举中追加一项，避免各处散落魔法数字。

设计约定：
    code  = 0            成功
    code  = 4xxxx        客户端侧错误（参数/鉴权/资源/限流）
    code  = 5xxxx        服务端侧错误（外部依赖/内部错误）
    message             对调用方可读的状态描述
    data                业务数据（成功时携带，失败可为 null）
"""

from enum import IntEnum
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class BizCode(IntEnum):
    """业务状态码 + 描述（统一错误语义，与 HTTP 状态码解耦）。"""

    SUCCESS = (0, "成功")
    PARAM_ERROR = (40001, "参数校验失败")
    UNAUTHORIZED = (40101, "未授权访问")
    FORBIDDEN = (40301, "无权限操作")
    NOT_FOUND = (40401, "资源不存在")
    RATE_LIMITED = (42901, "请求过于频繁")
    TOOL_FAILED = (50201, "外部依赖失败")
    INTERNAL_ERROR = (50000, "服务内部错误")

    def __new__(cls, value: int, message: str) -> "BizCode":
        obj = int.__new__(cls, value)
        obj._value_ = value
        obj.message = message
        return obj

    def __str__(self) -> str:  # 便于日志输出：code:message
        return f"{self.value}:{self.message}"


class ApiResponse(BaseModel, Generic[T]):
    """统一接口响应包装。"""

    code: int = Field(..., description="业务状态码（0 成功，4xxxx/5xxxx 失败）")
    message: str = Field(..., description="状态描述")
    data: T | None = Field(default=None, description="业务数据，失败时为 null")
    trace_id: str | None = Field(default=None, description="请求追踪 ID，贯穿日志与存储")

    @classmethod
    def ok(
        cls,
        data: T | None = None,
        *,
        message: str = "成功",
        trace_id: str | None = None,
    ) -> "ApiResponse[T]":
        """构造成功响应（code=0）。"""
        return cls(code=BizCode.SUCCESS, message=message, data=data, trace_id=trace_id)

    @classmethod
    def fail(
        cls,
        code: BizCode,
        *,
        message: str | None = None,
        trace_id: str | None = None,
    ) -> "ApiResponse[Any]":
        """构造失败响应（业务状态码 + 描述，data 为 null）。"""
        return cls(
            code=code.value,
            message=message or code.message,
            data=None,
            trace_id=trace_id,
        )
