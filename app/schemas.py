"""Pydantic 数据模型。

对应学习大纲「阶段一·核心工具库」中的 pydantic v2：
声明请求/响应结构，运行时自动校验并生成 JSON Schema。
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
