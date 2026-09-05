"""可复用 FastAPI 依赖（Depends）。

对应「docs/12-Python开发规范.md」4.5 节：凡跨端点复用的横切能力
（鉴权 / 会话 / 配置 / 追踪）一律用 Depends 注入，禁止在路由内手动 new 对象。

新增横切能力（如限流、多租户解析）统一放这里。
"""

from uuid import uuid4

from fastapi import Header, Request

from app.config import Settings, get_settings_cached


async def get_settings() -> Settings:
    """注入全局配置单例（缓存于进程内）。"""
    return get_settings_cached()


async def get_trace_id(
    x_request_id: str | None = Header(default=None),
) -> str:
    """注入请求追踪 ID：优先沿用上游传入，否则生成，贯穿日志与存储。"""
    return x_request_id or uuid4().hex[:12]


async def get_client_ip(request: Request) -> str:
    """注入客户端 IP（限流 / 审计使用）。"""
    return request.client.host if request.client else "unknown"
