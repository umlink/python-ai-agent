"""Pydantic 数据模型包（按域拆分）。

对应学习大纲「阶段一·核心工具库」中的 pydantic v2：
声明请求/响应结构，运行时自动校验并生成 JSON Schema。

结构约定：
    schemas/__init__.py   统一导出（保持 from app.schemas import X 用法）
    schemas/common.py     统一响应封装 ApiResponse + 业务状态码 BizCode
    schemas/chat.py       对话域模型
    schemas/sse.py        SSE 流式协议（事件类型 + 帧构造 + 负载模型）
    schemas/rag.py        RAG 域模型（阶段八新增）
    schemas/task.py       长任务域模型（阶段七新增）

新增域模型：在 schemas/ 下新建 <域>.py，并在本文件 __init__.py 追加导出。
"""

from app.schemas.chat import ChatRequest, ChatResponse
from app.schemas.common import ApiResponse, BizCode
from app.schemas.sse import (
    SSEDeltaPayload,
    SSEDonePayload,
    SSEErrorPayload,
    SSEEventType,
    SSEMetaPayload,
    SSEToolCallPayload,
    SSEToolResultPayload,
    format_sse,
)

__all__ = [
    "ApiResponse",
    "BizCode",
    "ChatRequest",
    "ChatResponse",
    "SSEEventType",
    "SSEMetaPayload",
    "SSEDeltaPayload",
    "SSEToolCallPayload",
    "SSEToolResultPayload",
    "SSEDonePayload",
    "SSEErrorPayload",
    "format_sse",
]
