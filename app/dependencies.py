"""可复用 FastAPI 依赖（Depends）。

对应「docs/12-Python开发规范.md」4.6 节：凡跨端点复用的横切能力
（鉴权 / 会话 / 配置 / 追踪）一律用 Depends 注入，禁止在路由内手动 new 对象。

追踪链路的约定：请求 ID 由中间件（main.py 的 setup_request_id）统一生成并写入
`request.state.trace_id`。下游所有取 trace_id 的地方（路由 Depends、异常处理器、
使用 get_trace_id 注入的端点）都从 `request.state` 读取，保证正常与异常两条链路一致。
"""

from fastapi import Request

from app.config import Settings, get_settings_cached


async def get_settings() -> Settings:
    """注入全局配置单例（缓存于进程内）。"""
    return get_settings_cached()


async def get_trace_id(request: Request) -> str:
    """注入请求追踪 ID（由 RequestID 中间件在 request.state 预置）。"""
    return request.state.trace_id


async def get_client_ip(request: Request) -> str:
    """注入客户端 IP（限流 / 审计使用）。"""
    return request.client.host if request.client else "unknown"
