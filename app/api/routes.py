"""API 接入层路由。

对应学习大纲「阶段七·Agent 工程化最佳实践」的四层架构中的 API 接入层。
FastAPI 自动校验入参、自动生成 Swagger 文档，原生支持异步与 SSE 流式输出。
"""

from fastapi import APIRouter, Depends
from loguru import logger

from app.config import Settings
from app.dependencies import get_settings, get_trace_id
from app.schemas import ChatRequest, ChatResponse

router = APIRouter(prefix="/agent", tags=["agent"])


@router.post("/chat", response_model=ChatResponse, status_code=200)
async def chat(
    req: ChatRequest,
    settings: Settings = Depends(get_settings),
    trace_id: str = Depends(get_trace_id),
) -> ChatResponse:
    """Agent 对话入口（骨架实现）。

    真实项目中，这里会将请求交给 Agent 编排层（如 LangGraph）处理：
    检索 -> 规划 -> 调用工具 -> 生成回答。此处仅返回占位结果。
    """
    logger.info("chat start trace_id={} app={}", trace_id, settings.app_name)
    return ChatResponse(
        answer=f"收到问题：「{req.question}」。这里是 Agent 服务骨架，接入编排层后返回真实回答。",
        source="skeleton",
    )
