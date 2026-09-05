"""对话域请求/响应模型。

Agent 对话接口（POST /agent/chat）的 Pydantic 模型。
"""

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Agent 对话请求。"""

    question: str = Field(..., min_length=1, max_length=2000, description="用户问题")
    session_id: str | None = Field(default=None, description="会话 ID，用于多轮记忆")


class ChatResponse(BaseModel):
    """Agent 对话响应。"""

    answer: str = Field(..., description="回答内容")
    source: str = Field(..., description="来源标识（skeleton / rag / tool ...）")
