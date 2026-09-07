# 阶段三 · 小点 1：LangChain 基础

> 所属：阶段三 主流 Agent 开发框架（生产级首选·重中之重）
> 定位：LangChain 是整套 LangGraph 生态的地基——你用的 ChatModel / @tool / LCEL 全在这里。这一讲把 5 个核心零件逐个弄懂，并回答一个关键问题：为什么"链"不够用、必须上"图"（LangGraph）。

> **选用策略（读阶段三前先看）**：本阶段必修 LangChain + LangGraph；LlamaIndex 在阶段四做 RAG 时再深入；CrewAI / AutoGen / 其他方案了解选型即可。不必 6 套框架全啃，16 周计划只给前两者时间。

## 精简大纲

1. ChatModel：统一模型接口
2. PromptTemplate / FewShotPrompt：模板 + 变量分离
3. LCEL：表达式语言管道
4. @tool / bind_tools / AIMessage.tool_calls：工具体系
5. Chain 的局限与 LangGraph 的必然

## 学习内容详情

> 版本说明：LangChain / LangGraph 已于 2025 年 10 月发布 **1.0**（`langchain` 包重构，聚焦内置 Agent 架构）。本文示例基于稳定的 **LCEL 核心 API**，在 0.3.x 与 1.0 之间均兼容；`LLMChain` / `initialize_agent` 等旧接口已废弃，切记不要照抄旧教程。认准 LCEL、`@tool` 与 LangGraph 的 `StateGraph`。

### 1. ChatModel（模型封装）

#### 1.1 一张图看懂"换模型不改代码"

```mermaid
graph LR
    A[你的业务代码: 只调 .invoke()] --> B[ChatOpenAI]
    A --> C[ChatDeepSeek]
    A --> D[ChatOllama]
    B --> E[统一返回 AIMessage]
    C --> E
    D --> E
```

- 不管底层是 OpenAI、DeepSeek 还是本地 Ollama，都换成同一套 `.invoke()` 调用方式——切换模型只改 import 和一个参数，业务代码零改动。
- 例：`ChatDeepSeek(model="deepseek-chat")` 切 `ChatOllama(model="qwen2.5:7b")`。

```python
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

# 换模型只改这一行: ChatOpenAI( ... ) ↔ ChatDeepSeek(...) ↔ ChatOllama(...)
llm = ChatOpenAI(model="gpt-4o", temperature=0.2)

resp = llm.invoke([HumanMessage(content="用一句话介绍 Agent")])
print(resp.content)          # 统一都是 AIMessage, 用 .content 取文本
```

> 🔬 **深度理解 · ChatModel 统一接口**：
> 1. **本质**：ChatModel 是「各家 Chat 补全 API」之上的一层适配器抽象，把请求格式 / 认证方式 / 返回结构的差异收敛成同一个 `.invoke()`。
> 2. **机制**：`ChatOpenAI`、`ChatDeepSeek`、`ChatOllama` 等类都继承自 `BaseChatModel`，各自实现对应供应商的底层调用逻辑，但对外统一返回 `AIMessage`（内含 `content`、`additional_kwargs`、`tool_calls` 等标准化字段）。
> 3. **为什么重要**：它把「业务代码」和「具体模型」彻底解耦——换模型只改 import 与构造参数，prompt 模板 / 链 / 工具逻辑零改动。这是 LangChain「可插拔」的根基。
> 4. **易错点**：接口统一**不等于能力统一**。某模型不支持 function calling 时你绑工具会在运行时失败；不同模型的上下文窗口、`temperature` 支持范围也不同。类型检查和 IDE 都帮不了你，只能真机验证。

### 2. PromptTemplate / ChatPromptTemplate

- 把 prompt 里「固定不变」和「动态变化」分离成模板 + 变量（`{xxx}` 占位）。
- ChatPromptTemplate 专用于多轮对话（system / human / assistant 三种角色消息）。
- FewShotPrompt：自动把若干「输入→输出」示例拼进 prompt。

> ⏳ **短期可不深究**：FewShotPrompt（少样本示例）第一遍只需记住「它把若干示范问答拼进 prompt、让模型照猫画虎」，属于锦上添花的技巧，真正做 few-shot 场景时再补，不是主线重点。

```python
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

# 模板 + 变量分离: {topic} 是占位, 每次调用填入不同内容
prompt = ChatPromptTemplate.from_messages([
    ("system", "你是一位{domain}专家，回答请简洁专业。"),   # 系统角色+变量
    MessagesPlaceholder("history"),                      # 多轮历史占位
    ("human", "请解释：{topic}"),                         # 用户角色+变量
])

# 渲染成消息: 等价于手写一个字典列表
msgs = prompt.invoke({
    "domain": "AI",
    "history": [],                    # 假设没有历史
    "topic": "什么是 RAG",
})
print(msgs.to_messages())
```

> **记忆力点**：`MessagesPlaceholder("history")` 是 LangChain 做多轮对话的开关——后面接的变量 `history` 会被替换成历史消息列表。阶段三第 2 讲的 `MessagesState` 也是同样的"messages 占位"思想。

### 3. LCEL（LangChain 表达式语言）

- 用竖线 `|` 把组件串成管道：`prompt | llm | parser`，数据从左往右流过每个环节。
- LangChain 0.1 之后的核心语法，替代旧的 Chain 类。

```python
from langchain_core.output_parsers import StrOutputParser

# LCEL: 一条数据从左流到右的管道
chain = prompt | llm | StrOutputParser()
#   prompt  → 把词填进模板
#   llm     → 调用模型
#   parser  → 把 AIMessage 剥成纯字符串

text = chain.invoke({
    "domain": "编程", "history": [], "topic": "什么是装饰器",
})
print(text)   # 已经是纯字符串, 不用再取 .content
```

> **一句话理解 LCEL**：就是把"先 A 再 B 再 C"写成 `A | B | C`。组件之间自动做类型对接，少写大量样板代码。

> 🔬 **深度理解 · LCEL 与 Runnable 协议**：
> 1. **本质**：这里的 `|` 不是普通的语法糖运算，而是 `Runnable.__or__()` 重载——`A | B` 会构造一个 `RunnableSequence`，而它本身也是一个 Runnable。
> 2. **机制**：LangChain 里几乎所有东西（`ChatPromptTemplate`、`ChatModel`、`StrOutputParser`、自定义函数）都实现了同一个抽象协议 `Runnable`（`invoke` / `stream` / `batch` 及对应异步版 `ainvoke`/`astream`/`abatch`）。`|` 负责把前一个 Runnable 的输出作为后一个 Runnable 的输入，并在两端做类型适配。
> 3. **为什么重要**：正因为「一切皆 Runnable」，单链 `A|B|C` 和复杂并行、streaming、async、retry、fallback 共用同一套执行接口——改管道结构、换执行方式都不用改调用代码。这是理解 LCEL 一切高级能力的原点。
> 4. **易错点**：`A | B` 只是**构造对象**，不会立即执行，真正触发要看 `.invoke()`。另外管道有类型约束：前一个的输出必须能被下一个消化，若不匹配通常要到真正 `invoke` 时才作为错误暴露——接口能连上，不等于运行时一定对。

#### 3.1 LCEL 实战：Agent 场景的并行、子链与工具调用

三个生产高频玩法，全部用 LCEL 原生能力完成，不引入任何新框架（`@tool` / `bind_tools` 的正式讲解在第 4 节，这里先看它们如何嵌进管道）：

```python
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda, RunnableParallel
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI

# OpenAI 兼容风格: 换 base_url 即可切 DeepSeek / Qwen / Ollama
llm = ChatOpenAI(
    model="deepseek-chat",
    api_key="YOUR_KEY",
    base_url="https://api.deepseek.com/v1",
    temperature=0.2,
)

# ---- 玩法1: RunnableParallel —— 「检索」与「问题改写」两路同时跑 ----
def retrieve(query: str) -> str:
    """模拟向量检索, 返回召回的参考资料。"""
    return f"[{query}] 召回的资料: Agent = LLM + 记忆 + 工具 + 规划..."

def rewrite(query: str) -> str:
    """把口语化的模糊问题补全成完整、无歧义的问题。"""
    return f"请说明 {query} 的核心概念与典型应用场景"

fan_out = RunnableParallel(
    docs=RunnableLambda(retrieve),      # 路A: 拿原问题直接检索
    question=RunnableLambda(rewrite),   # 路B: 同时补全问题, 两路互不等待
)
# 输出形如 {"docs": "...", "question": "..."}, 正好对上子链的两个占位变量

# ---- 玩法2: 子链组合 —— 「格式化上下文 | llm | 解析」封装一次, 处处复用 ----
format_prompt = ChatPromptTemplate.from_messages([
    ("system", "你是一位严谨的助手, 只依据给定资料回答。"),
    ("human", "资料:\n{docs}\n\n问题: {question}"),
])
answer_chain = format_prompt | llm | StrOutputParser()   # ← 可复用的子链

# 玩法1 + 玩法2 串起来: 并行产出 → 直接喂给子链
qa_chain = fan_out | answer_chain
print(qa_chain.invoke("Agent 是什么"))

# ---- 玩法3: LCEL 里调工具 —— bind_tools 后接自定义 Runnable Lambda 执行 ----
@tool
def query_order(order_id: str) -> str:
    """查询订单的物流状态。当用户询问订单进度时调用。"""
    return f"订单{order_id}: 已发货, 预计3日内送达"

llm_with_tools = llm.bind_tools([query_order])

def run_tool_calls(ai_msg):
    """自定义 Runnable Lambda: 执行模型返回的 tool_calls, 拼装工具结果。"""
    results = [query_order.invoke(call["args"]) for call in ai_msg.tool_calls]
    return "\n".join(results) if results else ai_msg.content

tool_chain = llm_with_tools | RunnableLambda(run_tool_calls)
print(tool_chain.invoke("我的订单 A1024 到哪了?"))
```

> ⏳ **短期可不深究**：`RunnableLambda` / `RunnableParallel` 这类「把任意函数包装成可在管道里执行」的底层类型对接细节，这一遍掌握主链 `prompt | llm | parser` 即可；它们在阶段四做并行检索 / RAG 时自然用得上，届时再回来深入。

> ⚠️ LCEL 是「管道组合」思维，擅长把固定流程串成一条直线。一旦出现「调完工具看结果、再决定走哪条分支」这类**超过两层的复杂分支逻辑**，就该考虑 LangGraph 的条件边，而不是用 Runnable 嵌套 if/else 硬拼——那会把管道拼成面条代码。

### 4. 工具体系（第四大件）

#### 4.1 三个零件的关系

```mermaid
graph LR
    A[@tool 把函数变工具] --> B[自动生成 JSON Schema]
    C[bind_tools 把工具附加到模型] --> D[模型能看到这些工具]
    E[AIMessage.tool_calls 模型返回调用请求] --> F[统一了各家API 免去手写解析]
```

- `@tool` 装饰器：把普通 Python 函数一键包装成「模型可调用的工具」——自动提取函数名、docstring（作描述）和参数类型注解（作 Schema），等价于手写 JSON Schema 声明。
- `bind_tools`：把工具列表附加到模型对象，之后每次调用模型都能「看到」工具。
- `AIMessage.tool_calls`：模型返回里携带工具调用请求（工具名 + 参数 + 调用 ID），统一了各家 API 返回，不用再手写 `json.loads` 解析。

```python
from langchain_core.tools import tool

# @tool: docstring 就是给模型的"使用说明", 一定要写清楚!
@tool
def get_weather(city: str) -> str:
    """查询指定城市的实时天气。当用户问天气时调用。"""
    return {"北京": "晴 26°C"}.get(city, f"暂无{city}数据")

# bind_tools: 让模型"看到"这个工具
llm_with_tools = llm.bind_tools([get_weather])

# 调用后模型可能返回 tool_calls
resp = llm_with_tools.invoke("北京天气怎样？")
if resp.tool_calls:
    call = resp.tool_calls[0]
    print("工具名:", call["name"])            # get_weather
    print("参数:", call["args"])              # {'city': '北京'}
    print("调用ID:", call["id"])              # 回传结果时要配对
```

> **对照阶段二的手写版**：`@tool` 自动做了你手写的 `TOOLS = [{...}]` 那份 JSON Schema；`AIMessage.tool_calls` 替你省掉了 `json.loads(tc.function.arguments)`。

> 🔬 **深度理解 · @tool 与工具调用机制**：
> 1. **本质**：`@tool` 是一个装饰器，它通过读函数签名（`inspect.signature` + 类型注解）和 docstring，在运行时把普通函数编译成一个带 JSON Schema 声明的 `BaseTool` 对象——相当于把你的函数「翻译」成一份模型能读懂的说明书。
> 2. **机制**：`bind_tools` 把若干 tool 的 Schema 附加到模型对象上；之后每次调用模型，这些 Schema 会被塞进请求体发给模型（对应 OpenAI 的 `tools` 参数）。模型判断需要时返回标准化的 `AIMessage.tool_calls`：`[{name, args, id}]`。**执行工具和回传结果仍需你自己（或用 `ToolNode`）完成**——把工具返回以 `ToolMessage`（带上对应的 `tool_call_id`）回传，模型才能结合结果续答。
> 3. **为什么重要**：这套机制把「模型如何声明想用工具」从各家 API 的非标 JSON 解析中解放出来，成为 LangChain / LangGraph / LlamaIndex 等框架底层共同遵守的工具调用协议。
> 4. **易错点**：`bind_tools` 只负责「让模型能看到工具」，**绝不负责执行**。新手常以为 bind_tools 后工具会自动被调用。此外 `tool_call_id` 必须正确配对，配错或缺失时，模型无法把工具结果对应回具体请求。

### 5. 对比手写版与常见坑

- 框架帮你省掉 Schema 手写、参数 JSON 解析、结果回传拼装；但「模型何时调用工具、参数是否合法」本质问题框架同样解决不了，仍需自己兜底。
- 常见坑：
  1. **docstring 不写清楚** → 模型乱调或漏调。
  2. **工具描述与参数类型注解缺失** → Schema 生成失败。
  3. **认准 LCEL 与 LangGraph**，别学已废弃的旧 Chain。

### 6. Chain 的局限（为什么生产用 LangGraph）

#### 6.1 链是"一条单向管道"

```mermaid
graph LR
    A[输入] --> B[节点A] --> C[节点B] --> D[输出]
    style A stroke-dasharray: 5 5
    style D stroke-dasharray: 5 5
```

- 链是**单向直线**流程：没有循环、没有条件分支、没有状态管理。
- Agent 恰恰需要「调工具→看结果→再决定」的**循环**——LangGraph 用「图」替代「链」，支持循环和条件分支。

```mermaid
graph LR
    A[LLM节点] -->|调工具?| B{条件路由}
    B -->|是| C[工具节点]
    C --> A
    B -->|否| D[输出]
    style A stroke-dasharray: 5 5
    style D stroke-dasharray: 5 5
```

> **结论**：LangChain 是"搭积木的零件箱"，LangGraph 是"拼图的图纸"。单独用 LangChain 只能做"一条线跑完"，要做会循环、会分支、会记住状态的 Agent，必须上 LangGraph（下一讲）。

## 本节自检

- [ ] 能用 ChatPromptTemplate + LCEL 组装一条 `prompt | llm | parser` 管道
- [ ] 能用 @tool 定义一个工具并解释 bind_tools 的作用
- [ ] 能说清为什么 Chain 做不了 Agent、必须用图

## 本节配套思考题（快速入门的检验）

1. `ChatOpenAI` 换成 `ChatOllama` 时，你的业务代码哪里要改？`AIMessage` 这一抽象帮你免掉了什么？
2. `@tool` 从你函数里到底"偷走"了哪些信息来生成 Schema？（提示：函数名 / docstring / 类型注解）缺哪个会影响模型？
3. 用一句话向同事解释：LCEL 的 `|` 和传统「先 A 后 B」的函数嵌套有什么本质不同？
4. 为什么"链"做不了 Agent？缺了循环和条件分支，具体会导致哪些 Agent 关键行为无法实现？

## 本节常见面试题（深度解析）

> 针对本节核心知识的面试高频点，配合"本质+机制"式理解，能让你答得既有深度又有广度。

### 面试题 1：LangChain 的 LCEL「|」与普通函数嵌套「先 A 后 B」的本质区别是什么？
- **面试官想考察**：是否真正理解 LCEL 不是语法糖，而是基于 Runnable 协议的对象组合。
- **专业作答（含深度）**：
  1. `|` 不是语法糖，而是 `Runnable.__or__()`，返回的 `RunnableSequence` 本身也是 Runnable，从而支持流式 / 批量 / 异步等统一执行接口。
  2. 函数嵌套是「定义时就层层执行、一次性跑完」，LCEL 是「先声明一个可组合的对象，调用 `.invoke()` 时才跑」，可复用、可内省（如转成图可视化）。
  3. LCEL 自带类型适配与中间过程的可观测性，方便 Debug 与维护；普通嵌套每加一层都要手写传参和解析。
  4. 横向对比：LCEL 的裸 `|` 是单向管道，表达循环 / 分支能力有限，这正是要升级到 LangGraph 的原因。
- **加分亮点 / 深度追问**：主动提 `stream` / `abatch` 与 `RunnableSequence` 共用同一接口；追问常是「LCEL 能表达循环吗」——答：不能，循环正是 LangGraph 的用武之地。

### 面试题 2：`@tool` 是怎么生成 JSON Schema 的？`bind_tools` 到底做了、又没做什么？
- **面试官想考察**：是否理解工具调用全流程，以及「工具声明 vs 工具执行」的边界。
- **专业作答（含深度）**：
  1. `@tool` 通过函数名、docstring（作为描述）、参数类型注解（`inspect.signature`）自动编译出 JSON Schema，等价于手写 `TOOLS = [{...}]`。
  2. `bind_tools` 把 Schema 附加到模型，之后每次请求把这些 Schema 发给模型，模型才会「看得到」工具。
  3. **关键边界**：bind_tools 只负责「让模型看到」，不负责执行。模型返回的 `tool_calls`（含 name / args / id）仍需自己调用工具函数，并以 `ToolMessage` + 对应 `tool_call_id` 回传，模型才能续答。
  4. 联系生产：真实 Agent 里这一步由 LangGraph 的 `ToolNode` 或自封装组件统一完成。
- **加分亮点 / 深度追问**：主动说「docstring 描述是否清楚」直接决定模型的调用时机与参数正确性；追问常是「写差会怎样」——答：模型乱调或漏调。

### 面试题 3：为什么说「链（Chain）做不了 Agent」？LangChain 与 LangGraph 的分工点在哪？
- **面试官想考察**：对 Agent 本质需求（循环 + 分支 + 状态）的理解与框架选型判断。
- **专业作答（含深度）**：
  1. Agent 的核心是「模型思考 → 调工具 → 看结果 → 再思考」的循环，路径不固定、需要跨步共享状态（工作记忆）。
  2. Chain 是单向直线管道，没有循环、没有条件路由、没有状态管理——只能跑固定流程，一旦「根据结果决定下一步」就无能为力。
  3. LangGraph 用「图」建模：State 是全局背包、Node 是一个动作、Edge（含条件边）决定走向，天然支持循环 / 分支 / 持久化。
  4. 结论分工：LangChain 是「零件箱」负责拼装单链，LangGraph 是「图纸」负责编排流程；典型协同方式是把检索引擎 / @tool 包成节点塞进 LangGraph。
- **加分亮点 / 深度追问**：补充「链到底缺了三样东西」——循环、条件分支、状态管理；追问常是「既然 LangGraph 能做，何必学 LCEL」——答：LangGraph 节点内部仍常用 LCEL / Runnable 组装。