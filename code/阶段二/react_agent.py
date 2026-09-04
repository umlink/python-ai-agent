#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
阶段二 · 综合实战：手写一个完整可运行的 Agent（无需 API Key，离线直接跑）
========================================================================

运行方式：
    python3 react_agent.py

本文件把阶段二的核心概念全部落到可运行代码上：
    Part 1  工具注册表        —— 对应四大组件之「工具调用」
    Part 2  模拟 LLM         —— 无需 API Key，先让循环真正跑起来
    Part 3  OpenAI 适配器    —— 换一行就能接真实大模型
    Part 4  ReAct 主循环      —— 思考→行动→观察 + 记忆修剪 + 熔断
    Part 5  Plan-and-Execute —— 先规划后执行的变体
    Part 6  Reflexion        —— 失败反思重试的变体
    Part 7  运行示例

阅读建议：先直接运行一次看输出，再回头逐 Part 读代码。
"""

import json
import re
from dataclasses import dataclass, field
from typing import Callable, Optional


# ============================================================
# Part 1  工具注册表（Tool Registry）
# ============================================================

@dataclass
class Tool:
    """一个工具 = 名称 + 描述 + 参数Schema + 真实函数。"""
    name: str
    description: str
    parameters_schema: dict
    func: Callable


# ---- 工具 1：查天气 ----
def get_weather(city: str) -> str:
    """模拟真实天气接口。"""
    table = {"北京": "晴 26°C", "上海": "小雨 24°C", "广州": "多云 30°C", "深圳": "晴 28°C"}
    return table.get(city, f"抱歉，暂未收录城市「{city}」的数据")


# ---- 工具 2：计算器 ----
def calculator(expression: str) -> str:
    """只允许数字和四则运算的"安全"计算器。"""
    expr = expression.strip()
    if not re.fullmatch(r"[\d+\-*/().\s]+", expr):
        # 输入不合法 → 返回错误消息而非抛异常（关键工程习惯）
        return f"表达式不合法: {expression}"
    try:
        result = eval(expr, {"__builtins__": {}}, {})   # 真实计算工具通常走 AST 或 numexpr
        return str(result)
    except ZeroDivisionError:
        return "错误: 除数不能为 0"                        # 错误封装成消息回传
    except Exception as e:
        return f"计算失败: {e}"


# ---- 工具 3：知识库检索 ----
def search_knowledge(query: str) -> str:
    """模拟一个简易知识库。"""
    kb = {
        "react": "ReAct = 思考Reason → 行动Act → 观察Observe 的循环，是最小 Agent 单元",
        "agent": "Agent = 循环的 LLM 调用 + 工具执行 + 历史累积",
        "langgraph": "LangGraph 用图（Node + Edge）组织 Agent 流程，支持持久化与中断恢复",
        "memory": "记忆分短期（会话）/工作（本任务）/长期（跨会话）三级",
    }
    for key, val in kb.items():
        if key in query.lower():
            return val
    return f"知识库中未找到与「{query}」相关的内容"


# ---- 注册表：把所有工具集中管理，Agent 只认这个表 ----
TOOL_REGISTRY = [
    Tool(
        name="get_weather",
        description="查询指定城市的天气",
        parameters_schema={
            "type": "object",
            "properties": {"city": {"type": "string", "description": "城市名，如 北京"}},
            "required": ["city"],
        },
        func=get_weather,
    ),
    Tool(
        name="calculator",
        description="计算数学表达式，如 (3+5)*2",
        parameters_schema={
            "type": "object",
            "properties": {"expression": {"type": "string", "description": "四则运算表达式"}},
            "required": ["expression"],
        },
        func=calculator,
    ),
    Tool(
        name="search_knowledge",
        description="在知识库中检索一个概念的解释",
        parameters_schema={
            "type": "object",
            "properties": {"query": {"type": "string", "description": "要查询的概念关键词"}},
            "required": ["query"],
        },
        func=search_knowledge,
    ),
]


# ============================================================
# Part 2  模拟 LLM（MockLLM）
# ============================================================

@dataclass
class ToolCall:
    """模型决定的一次工具调用（OpenAI tool_calls 的最小版）。"""
    id: str
    name: str
    arguments: dict


@dataclass
class LLMResponse:
    """一次模型回复：要么给最终答案(content)，要么想调工具(tool_calls)。"""
    content: Optional[str] = None
    tool_calls: Optional[list] = None


class MockLLM:
    """
    模拟大模型：用"规则"模仿模型"根据上下文决定调工具 or 给答案"的行为。
    好处：不需要 API Key，任何人复制就能跑通整个循环。
    换真实模型时，把它替换成 Part 3 的 OpenAILLM 即可（接口一模一样）。
    """

    def __init__(self):
        self.calls = 0          # 统计被调用次数 → 直观感受"每轮 token 消耗"

    def chat(self, messages: list, tools: Optional[list] = None) -> LLMResponse:
        self.calls += 1

        # 规则 1：历史里已经有工具返回结果 → 说明该给最终答案了
        tool_msgs = [m for m in messages if m.get("role") == "tool"]
        if tool_msgs:
            last = tool_msgs[-1]["content"]
            return LLMResponse(content=f"根据查询得到的结果如下：{last}")

        # 规则 2：还没有工具结果 → 根据最近一次用户提问决定调用哪个工具
        last_user = next(
            (m["content"] for m in reversed(messages) if m["role"] == "user"), ""
        )

        if "天气" in last_user:
            return LLMResponse(tool_calls=[
                ToolCall("c1", "get_weather", {"city": _extract_city(last_user)})
            ])
        if "计算" in last_user or any(op in last_user for op in ["+", "-", "*", "/"]):
            return LLMResponse(tool_calls=[
                ToolCall("c2", "calculator", {"expression": _extract_expr(last_user)})
            ])
        if "是什么" in last_user or "解释" in last_user:
            return LLMResponse(tool_calls=[
                ToolCall("c3", "search_knowledge", {"query": _extract_query(last_user)})
            ])

        # 规则 3：兜底，给一个"无法处理"的回复（真实模型会尝试追问）
        return LLMResponse(content="这个问题我暂时无法处理，请换个问法。")


def _extract_city(text: str) -> str:
    """从"北京今天天气"里抓城市名（演示用简单匹配，真实场景靠模型）。"""
    for city in ["北京", "上海", "广州", "深圳"]:
        if city in text:
            return city
    return "北京"


def _extract_expr(text: str) -> str:
    """从"帮我计算 3+5*2"里抓表达式。"""
    m = re.search(r"[\d+\-*/().\s]+", text)
    return m.group(0).strip() if m else "1+1"


def _extract_query(text: str) -> str:
    """从"什么是 react"里抓关键词。"""
    for kw in ["react", "agent", "langgraph", "memory"]:
        if kw in text.lower():
            return kw
    return text


# ============================================================
# Part 3  OpenAI 适配器（换一行接真实模型）
# ============================================================

class OpenAILLM:
    """把官方 SDK 的返回翻译成本项目的 LLMResponse，接口与 MockLLM 一致。"""

    def __init__(self, api_key: str, model: str = "gpt-4o", base_url: Optional[str] = None):
        from openai import OpenAI                       # 延迟导入：不装 SDK 也能跑 mock
        kwargs = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self.client = OpenAI(**kwargs)
        self.model = model
        self.calls = 0

    def chat(self, messages: list, tools: Optional[list] = None) -> LLMResponse:
        self.calls += 1
        resp = self.client.chat.completions.create(
            model=self.model, messages=messages, tools=tools,
        )
        msg = resp.choices[0].message
        if msg.tool_calls:
            calls = [
                ToolCall(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=json.loads(tc.function.arguments or "{}"),
                )
                for tc in msg.tool_calls
            ]
            return LLMResponse(tool_calls=calls)
        return LLMResponse(content=msg.content)


# ============================================================
# Part 4  ReAct 主循环 Agent
# ============================================================

class Agent:
    """
    一个真正能跑的 Agent：
      - 记忆：保留最近 N 条（记忆修剪，防上下文膨胀）
      - 工具：只允许白名单（注册表）内工具
      - 执行：工具报错封装成消息回传，绝不抛异常中断循环
      - 熔断：超过 max_turns 强制终止，防死循环烧钱
    """

    def __init__(self, llm, tools=None, max_turns: int = 5, max_history: int = 20,
                 verbose: bool = True):
        self.llm = llm
        self.tools = {t.name: t for t in (tools or TOOL_REGISTRY)}
        self.max_turns = max_turns
        self.max_history = max_history
        self.verbose = verbose
        self.system_prompt = (
            "你是一个智能助手。需要外部信息时，必须调用工具；"
            "拿到工具结果后，再给出最终回答。不要编造工具没有返回的内容。"
        )

    # ---- 日志：全链路可追踪 ----
    def log(self, tag: str, msg: str) -> None:
        if self.verbose:
            print(f"  [{tag}] {msg}")

    # ---- 把工具注册表转成模型的 JSON Schema ----
    def _tool_schema(self) -> list:
        return [{
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters_schema,
            },
        } for t in self.tools.values()]

    # ---- 记忆修剪：超长时丢最旧的助手/工具消息，系统消息永远保留 ----
    def _trim(self, messages: list) -> list:
        if len(messages) > self.max_history:
            head = messages[:1]              # 保留 system
            tail = messages[-(self.max_history - 1):]
            self.log("记忆", f"历史超长，裁剪掉 {len(messages) - len(head) - len(tail)} 条")
            return head + tail
        return messages

    # ---- 执行单个工具调用：错误一律封装成消息 ----
    def _execute(self, call: ToolCall) -> str:
        tool = self.tools.get(call.name)
        if tool is None:
            return f"错误: 未知工具「{call.name}」（不在白名单内）"
        self.log("行动", f"{call.name}({call.arguments})")
        try:
            result = tool.func(**call.arguments)
        except TypeError as e:
            result = f"参数错误: {e}"          # 参数不对 → 回传消息让模型修正
        except Exception as e:
            result = f"执行失败: {e}"
        self.log("观察", result)
        return str(result)

    # ---- 主循环：思考 → 行动 → 观察，直到答案或熔断 ----
    def run(self, user_input: str) -> str:
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_input},
        ]
        turn = 0
        while turn < self.max_turns:
            turn += 1
            self.log("回合", f"第 {turn}/{self.max_turns} 轮")
            messages = self._trim(messages)

            resp = self.llm.chat(messages, self._tool_schema())

            if resp.tool_calls:
                # ① 先追加模型的"工具调用请求"消息
                messages.append({
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{
                        "id": c.id, "type": "function",
                        "function": {"name": c.name, "arguments": json.dumps(c.arguments)},
                    } for c in resp.tool_calls],
                })
                # ② 逐个执行，再把"工具结果"回传（tool_call_id 一一对应）
                for call in resp.tool_calls:
                    result = self._execute(call)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": result,
                    })
                continue                                   # 回到循环顶部继续"思考"

            # 模型给了最终答案 → 结束
            messages.append({"role": "assistant", "content": resp.content})
            self.log("完成", resp.content)
            return resp.content or ""

        # 熔断：到达最大轮次还没给答案
        self.log("熔断", f"已达最大轮次 {self.max_turns}，强制终止（防止死循环烧钱）")
        return "【熔断】任务未完成：已达最大轮次"


# ============================================================
# Part 5  Plan-and-Execute Agent（先规划后执行）
# ============================================================

class PlanAndExecuteAgent(Agent):
    """
    变体：先把任务拆成步骤清单（Plan），再逐条执行（Execute）。
    优势：长任务有条理、token 更省；风险：初始计划错则全错，需动态重规划。
    这里用 MockLLM 按"意图数"拆步骤演示；真实场景由模型生成计划。
    """

    def _plan(self, task: str) -> list:
        # 简化规划：根据任务里包含几个意图，拆成步骤
        steps = []
        if "天气" in task:
            steps.append(f"查询天气：{_extract_city(task)}")
        if "计算" in task or any(op in task for op in ["+", "-", "*", "/"]):
            steps.append(f"计算表达式：{_extract_expr(task)}")
        if "是什么" in task or "解释" in task:
            steps.append(f"检索概念：{_extract_query(task)}")
        return steps or [task]

    def _execute_step(self, step: str) -> str:
        # 每个步骤转成一次"子任务"交给 LLM 决策（这里直接按关键词路由到工具）
        if step.startswith("查询天气"):
            return self._execute(ToolCall("p1", "get_weather", {"city": _extract_city(step)}))
        if step.startswith("计算表达式"):
            return self._execute(ToolCall("p2", "calculator", {"expression": _extract_expr(step)}))
        if step.startswith("检索概念"):
            return self._execute(ToolCall("p3", "search_knowledge", {"query": _extract_query(step)}))
        return f"无法识别的步骤: {step}"

    def run(self, task: str) -> str:
        self.log("规划", f"任务：{task}")
        plan = self._plan(task)
        self.log("计划", " → ".join(plan))

        results = []
        for step in plan:
            self.log("执行", f"步骤：{step}")
            results.append(self._execute_step(step))

        # 汇总所有子结果 → 拼接成最终答案（真实场景会让模型润色）
        self.log("汇总", " | ".join(results))
        return "完成！" + " | ".join(results)


# ============================================================
# Part 6  Reflexion Agent（失败反思重试）
# ============================================================

class ReflexionAgent(Agent):
    """
    变体：普通 Agent 失败后，先让"反思器"复盘错在哪，把教训塞回提示，
    再带教训重试。代价：多跑几轮、token 更高；收益：成功率明显提升。
    """

    def __init__(self, *args, max_attempts: int = 3, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_attempts = max_attempts

    def _reflect(self, task: str, last_error: str) -> str:
        # 反思器：让 LLM 复盘（mock 下直接返回固定教训；真实场景调模型）
        return f"上次失败原因：{last_error}。下次注意先确认参数再调用工具。"

    def run(self, task: str) -> str:
        reflection = ""
        for attempt in range(1, self.max_attempts + 1):
            self.log("尝试", f"第 {attempt}/{self.max_attempts} 次")
            # 把历史教训拼进 system，让模型"带着教训"重试
            old_system = self.system_prompt
            if reflection:
                self.system_prompt = old_system + f"\n[教训] {reflection}"
            result = super().run(task)
            self.system_prompt = old_system

            if result and "熔断" not in result and "无法处理" not in result:
                return result                        # 成功
            # 失败 → 反思并继续
            reflection = self._reflect(task, result)
            self.log("反思", reflection)

        return "【Reflexion 失败】多次尝试后仍未成功"


# ============================================================
# Part 7  运行示例
# ============================================================

def main():
    print("=" * 60)
    print("Demo 1: ReAct —— 查天气（单工具，展示主循环）")
    print("=" * 60)
    agent = Agent(llm=MockLLM(), max_turns=5)
    agent.run("北京今天天气怎么样？")
    print(f"（本次共调用模型 {agent.llm.calls} 次 = 每轮一次，可感知 token 消耗）")

    print("\n" + "=" * 60)
    print("Demo 2: ReAct —— 计算 10/0（工具报错，观察错误如何被回传）")
    print("=" * 60)
    agent2 = Agent(llm=MockLLM(), max_turns=5)
    agent2.run("帮我计算 10/0")
    print(f"（模型调用 {agent2.llm.calls} 次）")

    print("\n" + "=" * 60)
    print("Demo 3: Plan-and-Execute —— 多意图任务一次规划")
    print("=" * 60)
    pea = PlanAndExecuteAgent(llm=MockLLM(), max_turns=5)
    pea.run("上海天气怎么样？顺便解释一下什么是 react")

    print("\n" + "=" * 60)
    print("Demo 4: Reflexion —— 故意制造失败再自我修正")
    print("=" * 60)
    ra = ReflexionAgent(llm=MockLLM(), max_turns=2, max_attempts=3)
    ra.run("计算 3+5")


if __name__ == "__main__":
    main()
