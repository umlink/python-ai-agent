# 阶段三 · 小点 2：LangGraph 核心（Agent 开发事实标准）

> 所属：阶段三 主流 Agent 开发框架（核心实战·重中之重）
> 定位：LangGraph 是生产级 Agent 的事实标准。它的心智模型就一句话：**把 Agent 画成一张图，State 是全局背包，Node 是一次动作，Edge 决定下一步去哪**。这一讲把它彻底讲透，并对照阶段二手写版，让你看到"框架做的每件事"都对应你手写过的某几行代码。

## 精简大纲

1. 核心概念：State / Node / Edge / ConditionalEdge / StateGraph
2. 从零搭建 ReAct Agent（对照阶段二手写版）
3. 持久化记忆与人工中断恢复（Checkpointer / thread_id / interrupt）
4. 多智能体：Supervisor 主管模式
5. 观测：LangSmith 与自建追踪

## 学习内容详情

> 用官方 StateGraph 手搭一遍 ReAct 循环——对照阶段二手写版，你会发现「框架做的每一件事」都对应你手写过的某几行代码。

### 1. 核心概念

#### 1.1 一张图看懂整个运行机制

```mermaid
graph TD
    A[START 入口] --> B["LLM节点 (a: 思考)"]
    B --> C{条件边: 要调工具?}
    C -->|是| D["ToolNode (b: 执行)"]
    D --> B
    C -->|否| E[END 出口]
    style A stroke-dasharray: 5 5
    style E stroke-dasharray: 5 5
    style D fill:#e6eeff
```

- **State：** 贯穿整个图运行的「全局数据包」，用 TypedDict 或 Pydantic 定义；最常见字段是 messages，可加任意业务字段（任务进度 / 工具调用次数 / 审批状态）。对照阶段二：State ≈ 工作记忆。
- **Node：** 图中的「处理单元」，就是一个函数：接收当前 State，返回 State 的**增量更新**（只返回要改的字段）。
- **Edge：** 节点连线，三种：普通边（必去 B）、条件边（按 State 动态决定去哪）、入口边（START → 第一个节点）。
- **ConditionalEdge：** 边上的「路由函数」读 State 返回下一个节点名——ReAct 的循环就是条件边把「工具节点」接回「LLM 节点」实现的。
- **StateGraph / compile / invoke：** 声明式画图（add_node / add_edge）→ compile() 编译校验 → invoke(初始 State) 执行。
- **add_messages：** State 里 messages 的「追加」而非「覆盖」规则注解，LangGraph 自动做历史累加。
- **ToolNode：** 预置的「工具执行节点」，接收 tool_calls 批量执行、自动把结果包成 tool 消息追加进 State。
- **MessagesState：** 预置的「只含 messages 字段」的 State 定义。
- **熔断提醒：** 默认无最大轮次限制！生产必须加（recursion_limit 参数或自定义计数节点），防死循环烧钱。

### 2. 从零搭建 ReAct Agent

#### 2.1 轨迹预览（对照图）

```
START → think(要查北京天气) → tools(查北京) → think(还要查上海)
     → tools(查上海) → think(算温差) → tools(计算器) → think(汇总) → END
```

- 框架帮做的三件事：
  1. **messages 历史追加**（`add_messages` 自动化，省掉你手写的 `messages.append(...)`）。
  2. **工具调用解析与执行回传**（ToolNode 自动化，省掉你手写的 `json.loads + tool_call_id 配对`）。
  3. **循环控制**从 `for` 循环变成「图上的边」（可视化、可插入任意节点如审批 / 日志）。

#### 2.2 完整可运行代码（LangGraph 版 ReAct）

```python
from typing import Annotated, TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

# ---- ① 定义 State: 全局背包, messages 用 add_messages 规则自动累加 ----
class State(TypedDict):
    messages: Annotated[list, add_messages]

# ---- ② 定义工具: 等价于阶段二手写版里的 TOOL_REGISTRY ----
@tool
def get_weather(city: str) -> str:
    """查询城市天气。当用户问天气时调用。"""
    return {"北京": "晴 26°C", "上海": "小雨 24°C"}.get(city, "暂无数据")

tools = [get_weather]
llm = ChatOpenAI(model="gpt-4o", temperature=0).bind_tools(tools)

# ---- ③ 定义 LLM 节点: 输入 State, 返回 State 的增量 ----
def think(state: State) -> dict:
    resp = llm.invoke(state["messages"])     # 让模型思考
    return {"messages": [resp]}              # 只返回"要追加的"消息(LangGraph 帮你累加)

# ---- ④ 条件边路由: 模型要调工具就去 tools, 否则结束 ----
def should_continue(state: State) -> str:
    last = state["messages"][-1]
    return "tools" if last.tool_calls else "end"

# ---- ⑤ 组装图 ----
graph = (
    StateGraph(State)
    .add_node("think", think)          # 智能节点
    .add_node("tools", ToolNode(tools))  # 预置工具节点
    .add_edge(START, "think")          # 入口→think
    .add_conditional_edges("think", should_continue, {"tools": "tools", "end": END})  # 条件边
    .add_edge("tools", "think")        # 工具跑完→回到 think(这就是循环!)
    .compile()
)

# ---- ⑥ 执行 ----
result = graph.invoke({"messages": [HumanMessage(content="北京天气？")]})
print(result["messages"][-1].content)
```

> **与阶段二手写版逐行对照**（建议边看边回想手写版）：
> - `think` 节点 = 手写版里"调用模型判断走 action 还是 content"。
> - `ToolNode` = 手写版里"解析 tool_calls + 执行 + tool_call_id 配对回传"。
> - `add_conditional_edges` + `.add_edge("tools","think")` = 手写版的 `while` 循环 + `continue`。
> - `add_messages` = 手写版里一行行 `messages.append(...)`。

> 💡 **可直接跑起来的完整版**：进阶练习请直接使用 [阶段三综合实战：LangGraph 完整 Agent](07-阶段三综合实战-LangGraph完整Agent.md) 的配套代码 [`react_langgraph_agent.py`](../../code/阶段三/react_langgraph_agent.py)。它内置"剧本模型"，**无需 API Key 离线可运行**，跑完 `python3 code/阶段三/react_langgraph_agent.py` 再对照第 2 讲的"轨迹预览图"逐条核对即可。

### 3. 持久化记忆与人工中断（两大生产必备能力）

#### 3.1 记忆与隔离

```mermaid
graph LR
    A[用户A 会话t1] --> C[同一 Checkpointer]
    B[用户B 会话t2] --> C
    A -->|thread_id=A| D[历史A]
    B -->|thread_id=B| E[历史B]
    D & E -->|互不干扰| F[多租户/多用户隔离]
```

- **A) 多轮对话记忆：** compile 时挂上 Checkpointer，同一 `thread_id` 的多次 invoke 共享历史；不同 `thread_id` 完全隔离（多用户 / 多租户隔离就靠它）。

```python
from langgraph.checkpoint.memory import MemorySaver

# 挂记忆: 同一 thread_id 的多次调用共享历史
checkpointer = MemorySaver()
app = graph.compile(checkpointer=checkpointer)

# 第 1 次调用: "介绍一下 Agent"
app.invoke({"messages": [HumanMessage("介绍一下 Agent")]}, {"configurable": {"thread_id": "u1_s1"}})
# 第 2 次调用: 模型还记得上一轮, "它有什么价值?" 里的"它"被正确理解
app.invoke({"messages": [HumanMessage("它有什么价值？")]}, {"configurable": {"thread_id": "u1_s1"}})
# 换个 thread_id → 完全独立的历史(多用户隔离)
```

- **生产要点：**
  1. ① `MemorySaver` 存内存、重启即丢 → 生产换 `SqliteSaver` / `RedisSaver` / `PostgresSaver`（同一接口，只换 import）。
  2. ② `thread_id` 用业务会话 ID（`user_id + session_id`）。
  3. ③ 服务重启后 invoke 自动从 Checkpointer 恢复线程历史——「中断恢复」就是这么简单。
  4. ④ 拒绝路径应生成友好回复而非静默结束。

#### 3.2 人工中断恢复（高危工具审批）

```python
from langgraph.types import interrupt, Command

def human_confirm(state: State) -> dict:
    """高危操作前暂停整张图, 抛给外部人工确认。"""
    params = {"action": "DELETE FROM users", "row_count": 100}
    decision = interrupt({                              # 暂停! 图在此挂起
        "question": "高危操作, 请确认",
        "params": params,
    })                                                  # 外部 resume 后才继续
    return {"messages": [HumanMessage(content=f"人工决定: {decision}")]}

# 外部(如 API handler)在收到中断后:
#   Command(resume="确认执行") 或 Command(resume="取消")
# → State 由 Checkpointer 保住, 从断点继续
```

### 4. 多智能体：Supervisor 主管模式

#### 4.1 一张图看懂

```mermaid
graph TD
    S[Supervisor主管: 决定下一步派谁] --> W1[撰稿人]
    S --> W2[SEO优化师]
    S --> W3[事实核查员]
    W1 --> S
    W2 --> S
    W3 --> S
```

- 场景：一个「内容总监」调度撰稿人、SEO 优化师、事实核查员三个工人。
- Supervisor 只做一件事——决定下一个派谁；工人节点各司其职（每次都是「角色化」的 LLM 调用）。
- 三大工程要点：
  1. ① 共享 messages 越滚越长 → 每轮做摘要压缩或只传相关切片控 token。
  2. ② 主管路由错误会带偏全局 → route 加兜底分支 + `recursion_limit` 熔断。
  3. ③ **先问「真的需要多智能体吗」**——单 Agent + 多工具能解决的别上多智能体（复杂度翻倍）。

### 5. 观测：LangSmith 与自建追踪

- LangSmith 官方观测平台（付费 SaaS，敏感数据不能出内网时用不了）。
- 自建方案：用 loguru 记录「每一步」的输入输出，落盘成结构化 JSON 行日志；用 run 编号 grep 日志还原完整轨迹。这就是 LangSmith 的最小平替：**trace_id + 节点 / 工具埋点 + 结构化落盘**。

```python
from loguru import logger
import uuid

def logged_node(name: str):
    """给每个节点套一层日志装饰器: 全链路追踪的最小实现。"""
    trace_id = uuid.uuid4().hex[:8]
    def decorator(func):
        def wrapper(state: dict) -> dict:
            logger.info(f"[{trace_id}] 进入节点 {name}, 输入={state}")
            out = func(state)
            logger.info(f"[{trace_id}] 离开节点 {name}, 输出={out}")
            return out
        return wrapper
    return decorator

# 用 run 编号(这里 trace_id) grep 日志即可还原一次完整轨迹
```

## 本节自检

- [ ] 能用 StateGraph 从零搭一个带持久化的 ReAct Agent
- [ ] 能实现一次人工中断审批流（高危工具）
- [ ] 理解 thread_id 的会话隔离与 Checkpointer 的存储后端切换

## 本节配套思考题（快速入门的检验）

1. `add_messages` 到底做了什么？如果去掉它，`messages` 字段会变成什么行为（覆盖 vs 追加）？
2. 条件边 `should_continue` 读 `last.tool_calls` 判断去向。如果模型既没调工具也没给答案，这里会发生什么？你怎么兜底？
3. 为什么 `MemorySaver` 只能本地演示、不能上生产？换个持久化后端只需要改什么？
4. `interrupt()` 挂起后，外部怎么让图继续？State 是靠谁保住的？
5. 用一句话解释：为什么"图"能实现"链"做不到的循环和分支？