"""SSE（Server-Sent Events）流式协议标准定义。

对应「docs/12-Python开发规范.md」4.5 节：流式输出用 `StreamingResponse`，
逐 token 由编排层以生成器传入，接入层封装为 SSE 帧。

协议约定（与普通 `ApiResponse` 不同：SSE 用 `event` 字段表达消息语义，
负载直接放业务数据，不再重复套 {code, message, data} 包装）：

    每帧格式（两行，空行结尾）：
        event: <事件类型>\n
        data: <JSON 负载>\n
        \n

    事件流转约定：
        meta → message_start → (delta | tool_call | tool_result)* → done
        任一步出错 → error（data 内复用 BizCode 的 code/message）→ done 兜底
        心跳保活用 ping，避免代理/客户端断流

    帧构造统一用 `format_sse()`；负载模型见下方各事件类。
"""

import json
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class SSEEventType(str, Enum):
    """SSE 事件类型（一次流式响应的所有消息类型）。"""

    META = "meta"  # 流开始：会话/模型/追踪信息
    MESSAGE_START = "message_start"  # 开始生成回答
    DELTA = "delta"  # token 增量
    TOOL_CALL = "tool_call"  # 调用工具
    TOOL_RESULT = "tool_result"  # 工具返回结果
    DONE = "done"  # 正常结束
    ERROR = "error"  # 中途失败（data 内复用 BizCode）
    PING = "ping"  # 心跳保活


# ---------- 事件负载模型 ----------


class SSEMetaPayload(BaseModel):
    """流开始元信息。"""

    session_id: str = Field(..., description="会话 ID")
    model: str = Field(..., description="模型标识")
    trace_id: str = Field(..., description="请求追踪 ID")


class SSEDeltaPayload(BaseModel):
    """token 增量。"""

    content: str = Field(..., description="增量文本")


class SSEToolCallPayload(BaseModel):
    """工具调用。"""

    tool: str = Field(..., description="工具名")
    args: dict[str, Any] = Field(default_factory=dict, description="调用参数")


class SSEToolResultPayload(BaseModel):
    """工具返回。"""

    tool: str = Field(..., description="工具名")
    result: Any = Field(default=None, description="工具返回内容")


class SSEDonePayload(BaseModel):
    """正常结束。"""

    finish_reason: str = Field(default="stop", description="结束原因：stop / tool / error")
    usage: dict[str, int] | None = Field(default=None, description="Token 用量，可选")


class SSEErrorPayload(BaseModel):
    """中途失败（复用 BizCode 的 code/message 语义）。"""

    code: int = Field(..., description="业务状态码（见 BizCode）")
    message: str = Field(..., description="错误描述")


# ---------- 帧构造 ----------


def format_sse(event: SSEEventType, data: BaseModel | dict | None = None) -> str:
    """把事件序列化为标准 SSE 帧（event + data 两行 + 空行）。

    用法：
        yield format_sse(SSEEventType.DELTA, SSEDeltaPayload(content="你"))
        yield format_sse(SSEEventType.PING)
    """
    if isinstance(data, BaseModel):
        payload = data.model_dump_json()
    elif data is not None:
        payload = json.dumps(data, ensure_ascii=False)
    else:
        payload = "{}"
    return f"event: {event.value}\ndata: {payload}\n\n"
