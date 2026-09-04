#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
阶段三 · 综合实战：用 LangGraph + LangChain 搭一个完整 Agent（无需 API Key）
=============================================================================

运行方式：
    python3 react_langgraph_agent.py

本文件把阶段三的核心概念全部落到可运行代码上：
    Part 1  用 LangChain @tool 定义工具（对比阶段三第1讲）
    Part 2  用一个"假模型" FakeListChatModel 离线驱动整个 Agent
    Part 3  用 LangGraph StateGraph 手搭 ReAct 循环（对比阶段三第2讲 + 阶段二手写版）
    Part 4  熔断 + 结构化日志（对比生产工程要点）
    Part 5  换个真实模型怎么接（OpenAI / 本地 Ollama）

前置依赖：
    pip install langgraph langchain-openai langchain-community

阅读建议：先直接 python3 跑一次看输出，再对照阶段三第1、2讲的代码逐个看懂。
"""

from typing import TypedDict, Annotated, ClassVar
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langchain_core.language_models.fake_chat_models import FakeListChatModel


# ============================================================
# Part 1  用 @tool 定义工具集（LangChain 工具体系）
# ============================================================

@tool
def get_weather(city: str) -> str:
    """查询指定城市的实时天气。当用户问天气时调用。"""
    table = {"北京": "晴 26°C", "上海": "小雨 24°C", "广州": "多云 30°C"}
    return table.get(city, f"暂无{city}天气数据")


@tool
def calculator(expression: str) -> str:
    """计算数学表达式，支持 + - * / 和括号。当用户需要计算时调用。"""
    from re import fullmatch
    if not fullmatch(r"[\d+\-*/().\s]+", expression):
        return f"表达式不合法: {expression}（只允许数字和四则运算）"
    try:
        return str(eval(expression, {"__builtins__": {}}, {}))
    except ZeroDivisionError:
        return "错误: 除数不能为 0"          # 错误封装成消息回传, 让模型自救
    except Exception as e:
        return f"计算失败: {e}"


TOOLS = [get_weather, calculator]

# 注意: LangChain 的 @tool 已自动为每个工具生成好 args_schema,
# 后面 build_agent 里直接 bind_tools(TOOLS) 即可, 无需手写 JSON Schema。


# ============================================================
# Part 2  离线"假模型"驱动整个 Agent
# ============================================================

class ScriptedAgentModel(FakeListChatModel):
    """
    用 LangChain 官方的 FakeListChatModel 做"剧本模型"：
    按预设顺序返回每一条回复，让整个 ReAct 循环不依赖真实 API 也能跑。
    脚本设计得很好：它完整演示了"思考→调工具→看结果→再调→总结"的循环。
    """
    SCRIPT: ClassVar[list] = [
        # 第1次: 决定调 get_weather("北京")
        '{"tool_calls": [{"name": "get_weather", "args": {"city": "北京"}, "id": "c1"}]}',
        # 第2次: 拿到天气后, 再算一个表达式 (演示两个工具的转换)
        '{"tool_calls": [{"name": "calculator", "args": {"expression": "26 + 4"}, "id": "c2"}]}',
        # 第3次: 总结返回最终答案
        '北京今天晴，气温26°C，高温加4后是30。',
    ]

    def __init__(self):
        # inputs: 循环取剧本; 不够了重复最后一个
        super().__init__(responses=self.SCRIPT)


# 注意: 上面用字典模拟了 tool_call 结构, 但 FakeListChatModel 会把整串文本当
# 答案返回, 不会生成真正的 AIMessage.tool_calls。为了让离线 Demo 也能演示
# "条件边路由 + ToolNode 执行", 我们需要一个能返回真实 tool_calls 的封装,
# 见 auto_tool_call_llm() 函数 —— 它在每次 chat 后探测"模型说想调工具".


# ============================================================
# Part 2b  把"剧本文本"翻译成真正的工具调用
# ============================================================

def make_model():
    """返回一个支持工具调用的离线模型对象.

    原理: 包一层, 每次调用底层 FakeListChatModel 后, 解析它返回的 JSON 文本,
    若包含 tool_calls 字段则构造真正的 AIMessage(tool_calls=...),
    否则把它当作最终回答的 AIMessage。这样 LangGraph 的
    should_continue 才能读到 last.tool_calls → 走 ToolNode。
    """
    import json
    base = ScriptedAgentModel()

    class OfflineToolModel:
        def bind_tools(self, tools):
            self._tools = tools          # 记录工具(仅示意, 离线脚本已写死行为)
            return self

        def invoke(self, messages, **kwargs) -> BaseMessage:
            text = base.invoke(messages).content   # 拿到剧本文本
            try:
                data = json.loads(text)            # 是工具调用指令?
                calls = []
                for c in data["tool_calls"]:
                    calls.append({
                        "name": c["name"],
                        "args": c.get("args", {}),
                        "id": c.get("id", "auto"),
                        "type": "tool_call",
                    })
                # 返回"带工具调用"的 AIMessage → should_continue 会路由去 tools
                return AIMessage(content="", tool_calls=calls)
            except Exception:
                # 不是工具调用 → 当作最终回答
                return AIMessage(content=text)

    return OfflineToolModel()


# ============================================================
# Part 3  LangGraph 手搭 ReAct 循环
# ============================================================

class State(TypedDict):
    messages: Annotated[list, add_messages]   # 用 add_messages 规则自动累加历史


def build_agent(llm=None):
    """组装并返回一个编译好的 LangGraph ReAct Agent。"""
    llm = llm or make_model()
    model = llm.bind_tools(TOOLS)

    # ---- Node 1: LLM 思考 ----
    def think(state: State) -> dict:
        resp = model.invoke(state["messages"])
        # 节点内埋点: 打印"这一步模型决定了什么"(等价于生产里的结构化日志)
        if getattr(resp, "tool_calls", None):
            names = [c["name"] for c in resp.tool_calls]
            logger.info(f"[think] 决定调用工具: {names}")
        else:
            logger.info(f"[think] 将给出最终答复: {resp.content[:40]}...")
        return {"messages": [resp]}             # 只返回增量, LangGraph 自动累加

    # ---- 条件边路由: 模型要调工具就去 tools, 否则结束 ----
    def should_continue(state: State) -> str:
        last = state["messages"][-1]
        return "tools" if getattr(last, "tool_calls", None) else "end"

    graph = (
        StateGraph(State)
        .add_node("think", think)
        .add_node("tools", ToolNode(TOOLS))
        .add_edge(START, "think")
        .add_conditional_edges("think", should_continue, {"tools": "tools", "end": END})
        .add_edge("tools", "think")             # 工具跑完回到思考 (这就是循环)
        .compile()
    )
    return graph


# ============================================================
# Part 4  熔断 + 结构化日志（生产工程要点最小实现）
# ============================================================

from loguru import logger
import uuid

def run_with_guard(graph, question: str, max_steps: int = 10):
    """
    给图调用包一层"熔断" + "全链路日志"。
    生产里 max_steps 是防止 Agent 无限循环烧钱的生命线。
    注意: ReAct 的"循环"发生在图内部(think→tools→think...)。
    这里只用"图内可达的总步数上限"做兜底防护, 并打印最终结果。
    """
    trace_id = uuid.uuid4().hex[:8]
    logger.info(f"[{trace_id}] 开始 | 问题={question}")

    try:
        # 传入 recursion_limit: LangGraph 内部达到这个超限会自动抛错,
        # 从根上防止"死循环烧钱"(生产必备, 等价于阶段二的 max_turns)。
        result = graph.invoke(
            {"messages": [HumanMessage(content=question)]},
            {"recursion_limit": max_steps * 2},   # 每"回合"约2个节点, 乘2
        )
    except Exception as e:
        logger.error(f"[{trace_id}] 调用失败或达到递归上限: {e}")
        return f"【熔断】已达到最大步数 {max_steps}, 强制终止, 防止死循环烧钱"

    # 图跑完后, 取 State 里最后一条消息作为最终回答
    last = result["messages"][-1]
    answer = last.content
    logger.info(f"[{trace_id}] 完成 | 消息数={len(result['messages'])} 条 | 回答={answer}")
    return answer


# ============================================================
# Part 5  切真实模型（教程注释用, 离线默认走 OfflineToolModel）
# ============================================================

def build_real_model():
    """切真实模型: 安装 openai 后取消注释即可. 支持 DeepSeek / Ollama 换 base_url。"""
    # from langchain_openai import ChatOpenAI
    # return ChatOpenAI(model="gpt-4o", temperature=0, api_key="sk-xxx")
    raise NotImplementedError("离线演示请使用默认 OfflineToolModel")


# ============================================================
# 运行
# ============================================================

def main():
    logger.info("========== 阶段三 LangGraph 综合实战 ==========")

    graph = build_agent()                        # 离线模型
    answer = run_with_guard(graph, "北京天气怎么样？再告诉我26加4的结果")

    print("\n最终答案:", answer)
    print("\n> 说明: 观察上方日志的 [回合] 序列, 你会看到完整的")
    print(">  think(调天气) → tools → think(调计算器) → tools → think(总结) → 完成")


if __name__ == "__main__":
    main()