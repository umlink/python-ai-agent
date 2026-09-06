# 阶段三 · 综合实战：用 LangGraph + LangChain 搭一个完整 Agent

> 所属：阶段三 主流 Agent 开发框架（动手收尾）
> 定位：前 6 讲是"概念 + 片段代码"，这一讲把它们**焊成一个能跑的真 Agent**。用 LangGraph 的 `StateGraph` 手搭 ReAct 循环，内置一个"剧本模型"离线驱动——不花一分钱、不需要 API Key，复制到本地就能看到完整的「思考→调工具→看结果→再思考→总结」循环。

## 配套文件

- 可运行代码：[`/workspace/code/阶段三/react_langgraph_agent.py`](../../code/阶段三/react_langgraph_agent.py)
- 前置依赖：

```bash
pip install langgraph langchain-openai langchain-community loguru
```

## 一次运行能学到什么

```bash
python3 code/阶段三/react_langgraph_agent.py
```

你会看到如下日志，这正是阶段三第 2 讲那张"图"的真实运行:

```
[think] 决定调用工具: ['get_weather']     # 第1轮思考→调天气
[think] 决定调用工具: ['calculator']      # 第2轮思考→调计算器
[think] 将给出最终答复: 北京今天晴...        # 第3轮总结→结束
```

**问题只用了一句人话**（"北京天气怎么样？再告诉我26加4的结果"），但 Agent 内部自动拆成了两步工具调用再加总结——这就是"循环"的价值。

## 代码结构（Part 1 ~ 5）

### Part 1：用 `@tool` 定义工具（对照第 1 讲）

```python
@tool
def get_weather(city: str) -> str:
    """查询指定城市的实时天气。当用户问天气时调用。"""
    return {"北京": "晴 26°C"}.get(city, f"暂无{city}天气数据")

TOOLS = [get_weather, calculator]
```

- 一句 `docstring` 就是给模型的"使用说明"，决定模型何时触发。
- 注意 `calculator` 把错误 `return` 成消息而非 `raise`——模型能看到错误自行换思路。
- LangGraph 的 `bind_tools(TOOLS)` 会自动从 `@tool` 提取 JSON Schema，**无需手写**。

### Part 2：离线"剧本模型"（关键设计）

```python
class ScriptedAgentModel(FakeListChatModel):
    SCRIPT = [ "{"tool_calls": [...]}",
               "{"tool_calls": [...]}",
               "北京今天晴，气温26°C，高温加4后是30。" ]
```

- 用 LangChain 的 `FakeListChatModel` 按剧本顺序返回回复（离线演示，不依赖真实 API）。⚠️ 该模型已标记废弃，新代码建议改用 `GenericFakeChatModel`；示例仅演示离线流程，理解不受影响。
- `make_model()` 里再用一层包装，把剧本 JSON 翻译成真正的 `AIMessage(tool_calls=...)`，这样 LangGraph 的 `should_continue` 才能读到 `last.tool_calls` 并路由去 `ToolNode`。
- **为什么这么设计**：让循环在"不依赖真实 API"下完整跑起来。切真模型只需换 `build_agent(llm=真模型)`。

### Part 3：LangGraph 手搭 ReAct（核心，对照第 2 讲）

```python
graph = (
    StateGraph(State)
    .add_node("think", think)                    # LLM 思考节点
    .add_node("tools", ToolNode(TOOLS))          # 预置工具执行节点
    .add_edge(START, "think")
    .add_conditional_edges("think", should_continue, {"tools": "tools", "end": END})
    .add_edge("tools", "think")                  # ← 这一条边把工具接回思考 = 循环
    .compile()
)
```

- `State`：`messages: Annotated[list, add_messages]` —— `add_messages` 让历史自动累加而非覆盖。
- `should_continue`：读最后一条 `tool_calls`，有就回 `tools`，否则去 `end`。
- **与阶段二手写版对照**：
  - `think` 节点 = 手写版"调模型判断走 action 还是 content"。
  - `ToolNode` = 手写版"解析 tool_calls + 执行 + id 配对回传"。
  - `.add_edge("tools","think")` = 手写版的 `while` 循环 + `continue`。

### Part 4：熔断 + 节点埋点（生产工程要点）

```python
result = graph.invoke(
    {"messages": [...]},
    {"recursion_limit": max_steps * 2},   # ★ 熔断: LangGraph 内部达到上限自动抛错
)
```

- **熔断**：LangGraph 默认**不限制循环轮数**。生产必须传 `recursion_limit`（相当于阶段二的 `max_turns`），防死循环烧钱。
- **节点埋点**：在 `think` 节点内打日志，打印"这一步决定调什么工具"——这就是 LangSmith 最小平替的雏形。

```python
# think 节点内的埋点
if getattr(resp, "tool_calls", None):
    logger.info(f"[think] 决定调用工具: {[c['name'] for c in resp.tool_calls]}")
```

### Part 5：切真实模型

```python
# build_real_model 打开注释
from langchain_openai import ChatOpenAI
return ChatOpenAI(model="gpt-4o", temperature=0, api_key="sk-xxx")
#         换成 DeepSeek/Ollama: ChatDeepSeek(...) / ChatOllama(...) 仅改一处
```

- 从离线剧本切到真实模型，只需把 `build_agent()` 里的模型换成 `ChatOpenAI`（或 `ChatDeepSeek` / `ChatOllama`），其余图结构与工具代码**一行不改**。

## 进阶练习（把 Demo 改造成你的）

1. **加第三个工具**：往 `TOOLS` 加一个"查汇率"，并在 `SCRIPT` 里加一段对应的工具调用剧本，看循环多一步。
2. **改剧本触发熔断**：把 `SCRIPT` 改成永远返回工具调用（永不给最终答案），观察 `recursion_limit` 如何把死循环截断。
3. **切真实模型**：装 `openai` 后打开 `build_real_model`，用一句真正需要两步工具的问题（先查天气再算温差）验证。
4. **加 State 业务字段**：在 `State` 里加一个 `tool_calls_counter`，在每个 think 节点自增，看它跨节点累加——体验"State 是全局背包"。
5. **对照两张图**：把本 Demo 生成的运行日志，和阶段三第 2 讲的"轨迹预览图"一条条对上（think→tools→think→tools→think→END）。

## 本节自检

- [ ] 能不看代码说出 LangGraph 版 ReAct 里"循环"是靠哪条边实现的
- [ ] 已跑通 `react_langgraph_agent.py`，并至少做对进阶练习的 1 和 2
- [ ] 能说清 `recursion_limit` 为什么是生产生命线、`ToolNode` 帮你省了哪些手写代码

## 本节配套思考题（快速入门的检验）

1. 把 `add_messages` 从 `State` 里删掉，循环会发生什么（历史覆盖导致模型失忆）？跑一下验证。
2. `should_continue` 读 `last.tool_calls`。如果真实模型既没调工具也没给答案，这里怎么兜底？
3. `recursion_limit` 设太小会怎样（任务做不完），设太大又会怎样（可能死循环烧钱）？你如何权衡？
4. 为什么这个 Demo 能把"换模型"收敛到只改一行？`FakeListChatModel` 和 `ChatOpenAI` 共享了哪个接口？（提示：`invoke` / `bind_tools`）