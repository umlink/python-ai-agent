"""FastAPI 服务入口。

一个 Python 3 的 FastAPI Agent 服务骨架，对应学习大纲「阶段一/阶段七」的
分层设计：API 接入层 -> Agent 编排层 -> 工具服务层 -> 存储层。

运行方式：
    uvicorn app.main:app --reload --port 8000

健康检查：
    GET /health
"""

from fastapi import FastAPI

from app.api.routes import router

app = FastAPI(
    title="Python AI Agent 学习项目",
    description="基于 FastAPI 的 Agent 服务骨架（学习大纲配套项目）",
    version="0.1.0",
)

# 挂载路由（API 接入层）
app.include_router(router)


@app.get("/health", tags=["system"])
async def health() -> dict:
    """健康检查：K8s readiness / liveness probe 使用。"""
    return {"status": "ok", "service": "python-ai-agent-learning"}
