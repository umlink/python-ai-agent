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

> ⏳ **短期可不深究**：离线剧本里"剧本 JSON → `AIMessage(tool_calls=...)`"这一层转换的底层写法，以及 `FakeListChatModel` 已标记废弃、改用 `GenericFakeChatModel` 的细节，第一遍只需知道「它是用预置回复离线模拟真实模型」即可；生产用的是真模型，这段只服务"无 API Key 也能跑通循环"的演示目的。
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

> 🔬 **深度理解 · ReAct 循环的"图"实现机理**：
> 1. **本质**：循环不是"for / while"，而是靠**一条把工具节点接回思考节点的边**（`.add_edge("tools", "think")`）+ 一个**决定何时退出循环的条件边**（`add_conditional_edges` 读 `last.tool_calls`）联合构造的。
> 2. **机制**：每次经过 `think`，模型要么返回 `tool_calls`（条件边路由到 `tools` 执行、把结果追加回 State，再沿 `tools→think` 回到思考节点），要么直接给答案（条件边路由到 `end`）。所以"循环 = 下游节点被一条边接回上游"，而不是程序里的循环语句。
> 3. **为什么重要**：用图来表达循环，使每一轮都可插入任意节点（审批 / 日志 / 校验）、可观测、可受 `recursion_limit` 熔断约束——这正是"生产级 Agent"需要而裸链给不了的。
> 4. **易错点**：以为循环发生在 think 节点内部；其实离开 think 后由边决定走向——若条件边把"没有 tool_calls 的回复"也路由到 `tools`，会让 ToolNode 处理空调用而报错或卡死。

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

> 🔬 **深度理解 · recursion_limit 熔断的取舍**：
> 1. **本质**：它是 LangGraph 给单次执行设置的「节点总步数上限」，达到上限即抛错中止——是防 Agent 死循环烧钱的生命线。
> 2. **机制**：LangGraph 默认不限制循环轮数，`invoke(..., {"recursion_limit": N})` 传入步数上限；每执行一个节点算一步，超限即报 `GraphRecursionError`。这里用 `max_steps * 2` 是按"每轮约 2 步（think + tools）"做的粗估预留，并不精确对应业务语义。
> 3. **为什么重要**：设太小 → 正常多步任务没跑完就被截断；设太大 → 等于没熔断，模型死循环时白烧钱、浪费资源。必须结合任务复杂度与成本预算权衡。
> 4. **易错点**：以为它按"对话轮数"计（实际按"步数"）；也常忽略超限报错没有友好降级——生产里应捕获该异常并给出用户可读的兜底回复。

> ⏳ **短期可不深究**：把"节点里打日志"升级成一套完整自定义观测（结构化落盘、trace_id 关联、run 编号还原轨迹）的工程细节，第一遍只要领会「在 think 节点登记'这一步要调什么工具'就是最小可观测」即可；大规模上生产一般直接用 LangSmith 或 APM 中间件。

### Part 5：切真实模型

```python
# build_real_model 打开注释
from langchain_openai import ChatOpenAI
return ChatOpenAI(model="gpt-4o", temperature=0, api_key="sk-xxx")
#         换成 DeepSeek/Ollama: ChatDeepSeek(...) / ChatOllama(...) 仅改一处
```

- 从离线剧本切到真实模型，只需把 `build_agent()` 里的模型换成 `ChatOpenAI`（或 `ChatDeepSeek` / `ChatOllama`），其余图结构与工具代码**一行不改**。

> 🔬 **深度理解 · "换模型只改一行"背后的接口抽象**：
> 1. **本质**：离线剧本模型（`FakeListChatModel`）与 `ChatOpenAI` 能互换，是因为它们都实现了 LangChain 同一个 `BaseChatModel` 接口——图的节点只认接口，不认具体实现。
> 2. **机制**：图里的 `think` 节点只调用 `llm.invoke(...)` 与 `llm.bind_tools(...)`，而这些方法对一切 ChatModel 实现都成立；离线模型返回预置 AIMessage、真模型返回模型生成，在节点看来都是"一个会说话的对象"。
> 3. **为什么重要**：这正是 ChatModel 抽象的红利——把"模型"变成可替换的依赖（依赖倒置），让离线测试与真实上线共用同一套图与工具代码，显著降低测试与联调成本。
> 4. **易错点**：能换的只是"实现了同一接口"的模型；若某能力（如 tool_calls / 工具绑定）某个模型不支持，换过去会在运行时暴露——接口统一不等于能力统一。

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

## 本节常见面试题（深度解析）

> 针对本节核心知识的面试高频点，配合"本质+机制"式理解，能让你答得既有深度又有广度。

### 面试题 1：LangGraph 版 ReAct 的"循环"到底靠什么实现？去掉 `tools→think` 那条边会发生什么？
- **面试官想考察**：是否真正理解"图上的边 + 条件路由"如何构成循环，而不是嘴上说"有个 while"。
- **专业作答（含深度）**：
  1. 循环由两部分构成：`add_conditional_edges` 根据 `last.tool_calls` 决定"继续走 tools 还是结束"，以及 `.add_edge("tools","think")` 把工具节点接回思考节点——后者让流程能"回到上一步"。
  2. 机制：think 返回带 tool_calls 的调用 → 条件边路由到 tools 执行并回传 → tools 的边把控制权交回 think → 再判，形成闭环。
  3. 若去掉 tools→think：执行完工具后流程没有回填路径，会被当作结束或直接抛错，Agent 做不了"调工具看结果再决策"的多步任务——这是"链"做不到而"图"能做到的本质。
  4. 工程价值：这种循环可被可视化、可插入任意节点、可受 `recursion_limit` 熔断，可观测可控。
- **加分亮点 / 深度追问**：强调"循环 = 下游边接回上游"这一最小要件；追问常是"条件边不写映射会怎样"——答：路由函数返回的节点名必须在映射表里，否则等价于结束，静默丢任务。

### 面试题 2：`recursion_limit` 设太小 / 太大各自有什么后果？为什么说它是生产生命线？
- **面试官想考察**：对"熔断参数需要权衡"以及"死循环是 Agent 生产事故"的工程认知。
- **专业作答（含深度）**：
  1. LangGraph 默认不限制循环轮数，必须显式传 `recursion_limit`（按节点步数计）作为上限，超限抛 `GraphRecursionError`。
  2. 设太小：正常的多步任务没跑完就被截断，用户拿不到结果；设太大：等于没设熔断，模型陷入死循环时持续消耗 token 与算力、烧钱且不可控。
  3. 权衡：结合业务任务的最大合理步数与成本预算来设，并留余量；对超时 / 超限统一做降级（给出兜底回复或重试）。
  4. 配合手段：还可以用自定义计数节点、超时控制、幂等工具等手段，熔断只是兜底而非唯一防线。
- **加分亮点 / 深度追问**：提"它按步数不按轮数计"这个易错细节；追问常是"超限后怎么办"——答：捕获异常降级，必要时把已完成的部分结果回传给用户或升级人工处理。

### 面试题 3：为什么这个 Demo 能"换模型只改一行"？离线剧本模型有什么工程价值？
- **面试官想考察**：是否理解接口抽象（ChatModel）与"离线测试 / 真实上线共用代码"的设计价值。
- **专业作答（含深度）**：
  1. 根因是依赖倒置：图与节点只依赖 `BaseChatModel` 接口（`invoke` / `bind_tools`），不依赖具体实现，`FakeListChatModel` 与 `ChatOpenAI` 都实现该接口，故可互换。
  2. 离线剧本用预置 AIMessage 模拟"思考→调工具→总结"，让循环在无 API Key 下也能完整跑通，可用于 CI、教学和确定性测试。
  3. 上线时换 `ChatOpenAI`（或 `ChatDeepSeek` / `ChatOllama`）只改一处构造，图结构与工具代码一行不改。
  4. 注意边界：接口统一不等于能力统一，若目标模型不支持 tool_calls 等能力，运行时才会暴露。
- **加分亮点 / 深度追问**：把"接口抽象 + 依赖注入"提升为一般软件设计原则；追问常是"为什么离线/真实要共用同一套图"——答：保证测试与生产行为一致，降低联调与回归成本。