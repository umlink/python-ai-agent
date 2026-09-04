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

### Part 2：模拟 LLM（关键设计）

```python
class MockLLM:
    def chat(self, messages, tools=None) -> LLMResponse: ...
```

- 用"规则"模仿大模型的行为：历史里已有工具结果 → 给最终答案；否则按用户提问关键词决定调用哪个工具。
- **为什么这么做**：让初学者**不花一分钱、不配 API Key** 也能看到 Agent 循环真实运转。真实模型和 MockLLM 的 `chat()` 接口完全一致，换模型只改一行（见 Part 3）。

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