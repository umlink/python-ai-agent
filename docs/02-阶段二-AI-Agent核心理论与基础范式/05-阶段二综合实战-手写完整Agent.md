# 阶段二 · 综合实战：手写一个完整可运行的 Agent

> 所属：阶段二 AI Agent 核心理论与基础范式（动手收尾）
> 定位：前面 4 讲是"零件 + 图纸"，这一讲把它们**焊成一个能跑的真家伙**。不依赖任何框架、也不需要 API Key，复制到本地 `python3 react_agent.py` 就能看到 Agent 循环完整跑起来。先跑通，再读懂，最后换上真模型。

## 配套文件

- 可运行代码：[`/workspace/code/阶段二/react_agent.py`](../../code/阶段二/react_agent.py)（复制到本地直接跑）

## 一次运行能学到什么

```bash
python3 react_agent.py
```

你会看到 4 个 Demo，分别演示阶段二的核心：

| Demo | 演示点 | 对应概念 |
|-|-|-|
| 1 查天气 | ReAct 主循环：思考→行动→观察→回答 | 经典范式 + 主循环 |
| 2 计算 10/0 | 工具报错被**封装成消息回传**而非崩溃 | 工具结果处理 |
| 3 多意图任务 | 先规划步骤清单再逐条执行 | Plan-and-Execute |
| 4 Reflexion | 失败后反思、带教训重试 | Reflexion 变体 |

## 代码结构（Part 1 ~ 7）

### Part 1：工具注册表（四大组件之「工具调用」）

```python
@dataclass
class Tool:
    name: str                    # 工具名：模型靠它识别
    description: str             # 描述：决定模型何时触发
    parameters_schema: dict      # 参数 Schema：喂给模型的 JSON Schema
    func: Callable               # 真实函数：真正干活的代码
```

- 三个工具：`get_weather`（查天气）、`calculator`（四则运算）、`search_knowledge`（知识库）。
- 注意 `calculator` 的两个细节，都是阶段二强调的工程习惯：
  - **白名单校验**：`re.fullmatch` 只允许数字和四则运算符号，防注入。
  - **错误回传**：除零 / 非法表达式都 `return "错误: ..."` 而不是 `raise`——这样模型能看到错误并换方案，而不是整个循环崩掉。

> 🔬 **深度理解 · 工具（Tool）与工具抽象：为什么注册的是"描述和 Schema"而非直接传函数**：
> 1. **本质**：工具抽象是一种"把外部能力翻译成模型能理解和调用的语言"的桥——模型并不执行代码，它只"决定要不要用、用什么参数"，所以注册的一定是**名字 + 描述 + 参数 Schema + 真实函数**这四元组，而非裸函数。
> 2. **机制**：`Tool(name, description, parameters_schema, func)` 构成注册表；`_tool_schema()` 把注册表转成 OpenAI 的 `tools`（JSON Schema）喂给模型；模型凭 `description` 判断何时触发、按 `parameters_schema` 生成参数；执行时 `_execute` 校验参数、绑定 `func`，再把返回结果统一封装成消息回传。
> 3. **为什么重要**：整个"模型-工具"协作的正确性建立在两件事上——描述是否足以让模型在正确时机选用、Schema 是否足以让模型填对参数；同时白名单与错误回传决定了单次失控的上限，属于安全边界的一部分。
> 4. **易错点/常见误解**：新手以为"描述越简越好"，其实工具是否被触发完全取决于描述与 Schema 是否准确；也常把"工具定义"和"工具执行"混为一谈——定义是给模型看的说明书，执行才是真正干活的代码，二者解耦才便于安全插拔。

### Part 2：模拟 LLM（关键设计）

```python
class MockLLM:
    def chat(self, messages, tools=None) -> LLMResponse: ...
```

- 用"规则"模仿大模型的行为：历史里已有工具结果 → 给最终答案；否则按用户提问关键词决定调用哪个工具。
- **为什么这么做**：让初学者**不花一分钱、不配 API Key** 也能看到 Agent 循环真实运转。真实模型和 MockLLM 的 `chat()` 接口完全一致，换模型只改一行（见 Part 3）。

> ⏳ **短期可不深究**：MockLLM 里"按关键词判断该调哪个工具、历史里有工具结果就给答案"这类 if-else 逻辑只是为了离线演示，不是真实模型的行为机制。第一遍看懂它的**接口 `chat(messages, tools)` 和数据流**即可，别被规则逻辑误导，以为真模型也是这么"判"的。

```python
@dataclass
class LLMResponse:
    content: Optional[str] = None      # 模型直接给答案
    tool_calls: Optional[list] = None  # 模型决定调用工具
```

> 这两个字段就是 OpenAI `chat.completions` 返回里最重要的两部分。看懂 `LLMResponse`，就看懂了所有框架的"模型层抽象"。

### Part 3：OpenAI 适配器（换一行接真模型）

```python
class OpenAILLM:
    def __init__(self, api_key, model="gpt-4o", base_url=None): ...
    def chat(self, messages, tools=None) -> LLMResponse: ...
```

- 把官方 SDK 的返回翻译成 `LLMResponse`，接口与 `MockLLM` 完全一致。
- 所以从 Mock 切到真实模型只需：

```python
from openai import OpenAI
llm = OpenAILLM(api_key="sk-xxx", model="gpt-4o")   # 代替 MockLLM()
agent = Agent(llm=llm, max_turns=5)
agent.run("北京今天天气怎么样？")
```

### Part 4：ReAct 主循环（Agent 基类）

这是整个文件的灵魂，逐段拆解：

```python
def run(self, user_input: str) -> str:
    messages = [
        {"role": "system", "content": self.system_prompt},  # 立规矩，始终保留
        {"role": "user", "content": user_input},            # 用户问题
    ]
    turn = 0
    while turn < self.max_turns:        # 熔断：最多 N 轮，防死循环
        messages = self._trim(messages)  # 记忆修剪：超长丢最旧的
        resp = self.llm.chat(messages, self._tool_schema())

        if resp.tool_calls:
            messages.append({...assistant tool_calls...})   # ① 追加"工具调用请求"
            for call in resp.tool_calls:
                result = self._execute(call)                # 执行工具
                messages.append({...role:tool, tool_call_id: call.id...})  # ② 回传结果
            continue                                        # 回到循环，继续"思考"
        return resp.content  # 模型给了最终答案 → 结束
    return "【熔断】已达最大轮次"
```

配套的四个"工程习惯"方法：

| 方法 | 作用 | 对应概念 |
|-|-|-|
| `_tool_schema()` | 把注册表转成模型的 JSON Schema | 工具定义 |
| `_trim()` | 消息超长丢最旧、永远保留 system | 短期记忆修剪 |
| `_execute()` | 未知工具/参数错/执行错 → 封装成消息回传 | 工具结果处理 + 白名单 |
| `log()` | 每个回合/行动/观察都打日志 | 全链路追踪 |

> 运行 Demo 1 时观察 `[回合] → [行动] → [观察] → [回合] → [完成]` 的顺序，并看"模型调用 2 次"这个数字——这就是循环里每次 `chat()` 都在花 token 的直观证据。

> 🔬 **深度理解 · Agent 主循环的实现本质（run() 里发生了什么）**：
> 1. **本质**：`run()` 不是一次代码运行，而是一个"把每一轮对话追加进 messages、交给 LLM 判断、再根据判断执行工具并回传结果"的 while 循环；所谓"循环实操"就是这个 loop 加上一套消息协议。
> 2. **机制**：循环里的关键是一对成对的协议——先追加模型产出的 assistant 消息（含 `tool_calls`，每个带 `tool_call_id` 与动作），再用**同一个** `tool_call_id` 追加 `role: tool` 的对应结果。这样模型才能把"哪个动作的哪个结果"挂起来，继续下一轮推理，直到它返回不含工具调用的最终答案。
> 3. **为什么重要**：它把阶段二第 3 讲抽象的 ReAct 落成可执行代码；看懂这几十行，就等于看懂了任何框架"抽壳后的 Agent 内核"。循环里的 `_trim`、`_execute`、`log` 恰对应记忆修剪、工具容错、链路追踪。
> 4. **易错点/常见误解**：新手常把"一次 while 迭代"当成"一次 LLM 调用"，其实一轮里可能既有工具请求又有多个工具结果；也常漏掉 `role: tool` 必须带 `tool_call_id` 且与请求一一对应的约束——漏了，模型就无法正确把结果关联到动作。

### Part 5：Plan-and-Execute 变体

```python
class PlanAndExecuteAgent(Agent):
    def _plan(self, task): ...      # 拆步骤：按意图数生成计划
    def _execute_step(self, step): ...  # 每步路由到对应工具
    def run(self, task):
        plan = self._plan(task)      # ① 先规划
        for step in plan:            # ② 再逐条执行
            results.append(self._execute_step(step))
        return 汇总所有子结果
```

- 对比 ReAct：这里**先规划再执行**，一次性拆好步骤，不必每步都问模型"下一步做什么"，所以 token 更省。
- 真实场景由模型生成计划；这里用关键词规则拆解，是为了离线可跑。

### Part 6：Reflexion 变体

```python
class ReflexionAgent(Agent):
    def run(self, task):
        reflection = ""
        for attempt in range(self.max_attempts):
            result = super().run(task)          # 跑一轮普通 Agent
            if 成功: return result
            reflection = self._reflect(...)     # 失败 → 让反思器复盘
            # 把教训拼进 system_prompt 再重试
```

- 关键机制：失败后不是盲目重试，而是把"教训"拼进系统提示，让模型**带着上次的错误认知**重新开始。
- 代价：多跑几轮、token 更高；收益：成功率明显提升。

### Part 7：运行入口

```python
if __name__ == "__main__":
    main()
```

`main()` 里跑了 4 个 Demo，方便你一次看到所有范式的行为差异。

## 进阶练习（把 Demo 改造成你的）

1. **换真模型**：把 `MockLLM()` 换成 `OpenAILLM(api_key=..., base_url=...)`，试试国内 DeepSeek / 本地 Ollama（只需改 base_url + model）。
2. **加新工具**：照着 `Tool(...)` 的格式往 `TOOL_REGISTRY` 里加一个"查汇率"或"查时间"工具，看 Agent 是否会自动调用它（记得在 `MockLLM.chat` 里加对应规则）。
3. **复现三种失败模式**（阶段二第 3 讲的动手任务）：
   - 让工具返回 `{"error": ...}` → 观察模型自救。
   - 把 `max_turns` 调到 1 且问题需要 2 步 → 观察熔断。
   - 让 `MockLLM` 故意返回错误 JSON → 观察解析兜底。
4. **数 token**：`llm.calls` 就是模型调用次数，把它乘以每次消息长度，就能估算一次任务的 token 成本——理解为什么"每轮都调模型"很贵。

> ⏳ **短期可不深究**："数 token / 按调用次数估算成本"是进阶的省钱优化题，第一遍不必追求精确估量——当前你只需记住"每轮都调模型很贵"这个结论，等真正按 token 计费、需要成本精算的需求出现时再回来做。

## 本节自检

- [ ] 能不看提示，画出 `Agent.run()` 主循环的 `while` 逻辑（含 tool_calls 分支）
- [ ] 能说出 `_execute` 为什么把错误 return 成消息而不是 raise
- [ ] 已跑通 `react_agent.py` 的 4 个 Demo，并至少改造成：换真模型 或 加一个新工具
- [ ] 能说清 ReAct / Plan-and-Execute / Reflexion 在代码上的核心差异

## 本节配套思考题（快速入门的检验）

1. `Agent.run()` 里如果去掉 `_trim()`，跑一个特别长的多轮任务会发生什么？结合"上下文窗口"回答。
2. `_execute()` 对"未知工具"返回错误消息，这背后是"白名单"思想。如果换成"黑名单"（只禁高危），风险在哪？
3. Plan-and-Execute 用 `_plan` 一次性拆步骤，省在哪、险在哪？什么情况下它反而比 ReAct 更差？
4. Reflexion 把教训拼进 `system_prompt`，和直接拼进对话历史有什么区别？哪种更不容易"串味"到新任务？
5. 如果把 `max_turns` 设为 1，Demo 1 会发生什么？跑一下验证你的判断。

## 本节常见面试题（深度解析）

> 针对本节核心知识的面试高频点，配合"本质+机制"式理解，能让你答得既有深度又有广度。

### 面试题 1：为什么要把 LLM 封装成 `LLMResponse` 与 MockLLM/OpenAILLM 两层？"换一行接真模型"背后靠什么做到？
- **面试官想考察**：是否理解"接口抽象"这一软件工程手段在 Agent 里的必要性，以及是否真的懂"依赖注入"而非只是看过这个 Demo。
- **专业作答（含深度）**：
  1. **切的原因**：Agent 主循环只关心"给消息和工具、拿到'要不要调工具'的决策"，并不关心底层是 Mock 还是真实 OpenAI；把差异收敛到统一 `chat(messages, tools) -> LLMResponse` 接口上，主循环与厂商 SDK 彻底解耦。
  2. **`LLMResponse` 是抽象契约**：它只保留 `content`（最终答案）和 `tool_calls`（模型决定调哪些工具）两个字段——这正是 OpenAI `chat.completions` 返回里 Agent 层真正在乎的两部分，其余响应元数据被隔离在适配器内。
  3. **机制**：`OpenAILLM.chat()` 把官方 SDK 的返回翻译成 `LLMResponse`，因此 `Agent(llm=...)` 通过注入不同对象即可切换实现，伪代码"换一行"实指"注入对象换一个"，主循环零改动。
  4. **价值**：便于测试（Mock 注入跑通流程）、便于切换/多模型（DeepSeek、Ollama 只需换 base_url+model）、便于下沉到框架时对齐"模型层抽象"。
- **加分亮点 / 深度追问**：补"这是策略模式 / 适配器模式的落地，也让 Agent 逻辑与模型厂商解耦"；追问：MockLLM 会不会误导对真实模型的理解？答：会，它只是替身，判据只在"接口一致、数据流一致"，真正理解了协议才是目的。

### 面试题 2：为什么 `role: tool` 必须用同一个 `tool_call_id` 回传？漏掉或乱配会发生什么？
- **面试官想考察**：是否真懂"工具调用的成对协议"，这是手写 Agent（也是如实用官方 SDK）时最容易被坑的地方之一。
- **专业作答（含深度）**：
  1. **协议要求**：当模型返回带 `tool_calls` 的 assistant 消息时，聊天协议要求对每个 `tool_call_id` 必须追加一条 `role: tool` 的结果消息，且 id 与请求一一对应。
  2. **原因**：模型需要把"每个动作"与其"真实结果"精确配对，才能基于正确反馈继续推理；id 就是关联二者并维持有序性的键。
  3. **漏掉/乱配的后果**：要么校验报错（缺结果），要么结果挂到错误动作上，导致模型基于错乱信息推理出幻觉或错误结论；在支持并行多工具调用时尤其致命。
  4. **与本 Demo 的关系**：主循环里"先追加 assistant 的 tool_calls，再 for 循环逐一追加 tool 结果"这两步就是该协议的完整落地，也是最该手写吃透的一段。
- **加分亮点 / 深度追问**：可补"多工具并行调用时，每个 id 仍要各自成对，顺序可乱、配对不能错"；追问：收到 `role: tool` 但模型并不再返回 tool_calls 会出现什么？答：说明 Agent 判定任务完成、给出最终答案，循环正常终止。

### 面试题 3：ReAct / Plan-and-Execute / Reflexion 在这份代码里各自的核心差异在哪？为什么说它们是同一内核的不同变体？
- **面试官想考察**：能否从"类继承 + 策略"角度讲清三种范式的代码差异，而非停留在概念复述。
- **专业作答（含深度）**：
  1. **共用内核**：三者都复用 `Agent` 基类的 `_tool_schema / _execute / _trim / log` 等"循环基础设施"，差异只在于"如何决策下一步"这一步的策略。
  2. **ReAct**：基类本身——每轮都让 LLM 判断"下一步调哪个工具"，`while` 内一问一执行，出现 `tool_calls` 就继续、否则返回最终答案。
  3. **Plan-and-Execute**：在基类外套一层"先 `_plan` 一次性拆步骤、再逐条 `_execute_step`"的变体，把"每步征询模型"变成"执行定好的清单"，这就是 token 更省的代码出处。
  4. **Reflexion**：在 `run()` 外层用 `for attempt` 循环，失败后让反思器生成 `reflection` 并把它拼进 system_prompt 再重跑——把"教训注入"体现在 `super().run()` 的输入构造上。
- **加分亮点 / 深度追问**：可补"三者都缺不了熔断与错误回传，AutoGPT 的教训正是少了这些护栏"；追问：ReAct 基类同时被三者复用，会不会让变体出现耦合？答：会，所以规范化时要把"决策策略"再抽象一层（如执行器/规划器/反思器接口），本 Demo 为入门做了简化。