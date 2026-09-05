"""FastAPI 服务入口。

一个 Python 3 的 FastAPI Agent 服务骨架，对应学习大纲「阶段一/阶段七」的
分层设计：API 接入层 -> Agent 编排层 -> 工具服务层 -> 存储层。

运行方式：
    uvicorn app.main:app --reload --port 8000

健康检查：
    GET /health
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from loguru import logger

from app.api.routes import router
from app.config import Settings, get_settings_cached
from app.errors import register_exception_handlers


@asynccontextmanager
async def lifespan(app: FastAPI):
    """生命周期：启动/关闭时的资源管理。

    启动：初始化存储层连接池、加载模型、预热配置（阶段七扩展）。
    关闭：释放连接、落盘状态。
    """
    logger.info("app startup: {}", app.title)
    yield
    logger.info("app shutdown: {}", app.title)


def create_app() -> FastAPI:
    """应用工厂：组装中间件、路由、异常处理器与静态资源。"""
    settings: Settings = get_settings_cached()


    app = FastAPI(
        title=settings.app_name,
        description="基于 FastAPI 的 Agent 服务骨架（学习大纲配套项目）",
        version=settings.app_version,
        lifespan=lifespan,
    )

    # CORS：允许本地前端调试台（web/index.html）及浏览器跨源调用接口
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 业务异常处理器（全局统一转码）
    register_exception_handlers(app)

    # 挂载路由（API 接入层）
    app.include_router(router)

    # 健康检查（须在静态挂载之前注册，否则被 "/" 拦截）
    @app.get("/health", tags=["system"])
    async def health() -> dict:
        """健康检查：K8s readiness / liveness probe 使用。"""
        return {"status": "ok", "service": "python-ai-agent-learning"}

    # 静态托管前端调试台：访问根路径即可打开 web/index.html，与后端同源
    app.mount("/", StaticFiles(directory="web", html=True), name="web")

    return app


app = create_app()
