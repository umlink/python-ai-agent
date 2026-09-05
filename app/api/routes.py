"""API 接入层路由。

对应学习大纲「阶段七·Agent 工程化最佳实践」的四层架构中的 API 接入层。
FastAPI 自动校验入参、自动生成 Swagger 文档，原生支持异步与 SSE 流式输出。

普通接口统一用 `ApiResponse` 包装：{"code": 0, "message", "data", "trace_id"}。
流式接口（POST /agent/chat/stream）改用 SSE 帧：事件类型、帧格式、负载模型
统一定义在 app/schemas/sse.py，帧构造一律走 `format_sse()`。
"""

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from loguru import logger

from app.config import Settings
from app.dependencies import get_settings, get_trace_id
from app.schemas import (
    ApiResponse,
    BizCode,
    ChatRequest,
    ChatResponse,
    SSEDeltaPayload,
    SSEDonePayload,
    SSEErrorPayload,
    SSEEventType,
    SSEMetaPayload,
    format_sse,
)

router = APIRouter(prefix="/agent", tags=["agent"])

# 骨架阶段占位模型标识；接入编排层后改为真实模型名（如 deepseek-chat）。
_STREAM_MODEL = "skeleton"


@router.post("/chat", response_model=ApiResponse[ChatResponse], status_code=200)
async def chat(
    req: ChatRequest,
    settings: Settings = Depends(get_settings),
    trace_id: str = Depends(get_trace_id),
) -> ApiResponse[ChatResponse]:
    """Agent 对话入口（骨架实现）。

    真实项目中，这里会将请求交给 Agent 编排层（如 LangGraph）处理：
    检索 -> 规划 -> 调用工具 -> 生成回答。此处仅返回占位结果。
    """
    logger.info("chat start trace_id={} app={}", trace_id, settings.app_name)
    data = ChatResponse(
        answer=f"收到问题：「{req.question}」。这里是 Agent 服务骨架，接入编排层后返回真实回答。",
        source="skeleton",
    )
    return ApiResponse.ok(data, trace_id=trace_id)


def _chunk_text(text: str, size: int = 12) -> list[str]:
    """把完整回答切成固定长度的增量块，模拟逐 token 输出。"""
    return [text[i : i + size] for i in range(0, len(text), size)] or [""]


async def _chat_stream(
    req: ChatRequest,
    settings: Settings,
    trace_id: str,
):
    """SSE 事件生成器。

    事件流转：meta -> message_start -> (delta)* -> done；
    任一步出错 -> error（data 内复用 BizCode）-> done(finish_reason=error) 兜底。
    """
    try:
        yield format_sse(
            SSEEventType.META,
            SSEMetaPayload(
                session_id=req.session_id or "default",
                model=_STREAM_MODEL,
                trace_id=trace_id,
            ),
        )
        yield format_sse(SSEEventType.MESSAGE_START)

        answer = f"收到问题：「{req.question}」。这里是 Agent 服务骨架，接入编排层后返回真实回答。"
        for chunk in _chunk_text(answer):
            yield format_sse(SSEEventType.DELTA, SSEDeltaPayload(content=chunk))

        yield format_sse(SSEEventType.DONE, SSEDonePayload(finish_reason="stop"))
    except Exception as exc:  # noqa: BLE001 - 流内任何异常都要落到 error -> done 兜底
        logger.exception("chat stream failed trace_id={}", trace_id)
        yield format_sse(
            SSEEventType.ERROR,
            SSEErrorPayload(code=BizCode.INTERNAL_ERROR.value, message=str(exc)),
        )
        yield format_sse(SSEEventType.DONE, SSEDonePayload(finish_reason="error"))


@router.post("/chat/stream")
async def chat_stream(
    req: ChatRequest,
    settings: Settings = Depends(get_settings),
    trace_id: str = Depends(get_trace_id),
) -> StreamingResponse:
    """Agent 对话流式接口（SSE）。

    响应 Content-Type 固定为 text/event-stream，前端用 EventSource / fetch 逐帧读取。
    事件类型与帧格式见 app/schemas/sse.py；接入编排层后，生成器替换为真实逐 token 输出。
    """
    logger.info("chat stream start trace_id={}", trace_id)
    return StreamingResponse(
        _chat_stream(req, settings, trace_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
