# 阶段一 · 小点 6：主流模型 API 实战

> 所属：阶段一 大模型基础与 Prompt 工程（Agent 核心根基）
> 定位：看懂 API 文档不算本事，能"一套代码换来换去对接不同模型、还能稳得住限流和流式"才是。这一节把"换模型只需改 base_url"和"流式 + 错误处理"这两件事彻底讲透。

## 精简大纲

1. 国际模型：OpenAI / Claude API 调用、流式、错误码、限流
2. 国内模型：DeepSeek / 通义千问 / 智谱，OpenAI 兼容接口
3. 本地大模型部署：Ollama 调试、vLLM 生产推理
4. 本地模型做 Agent 的局限与对策

## 学习内容详情

### 1. OpenAI 兼容生态（base_url 是钥匙）

#### 1.1 核心：替换 base_url 就完成换模型

```mermaid
graph LR
    A[你的OpenAI兼容代码] --> B[base_url = api.openai.com]
    A --> C[base_url = DeepSeek 地址]
    A --> D[base_url = Ollama 11434]
    A --> E[base_url = vLLM 8000]
```

- OpenAI SDK 开放 `base_url` 参数：换成 DeepSeek / Ollama / vLLM 的地址即完成模型切换，代码几乎不动。
- ⚠️ **兼容 ≠ 等同**：国内模型兼容的是"请求 / 响应格式"，能力并不等同。尤其小模型的 function calling 稳定性、JSON 输出质量差异大。**换模型后必须重跑评测**，不能想当然。

```python
import os
from openai import OpenAI

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),      # 密钥走环境变量
    base_url=os.getenv("BASE_URL", "https://api.openai.com/v1"),
    # ↑ 想切到 DeepSeek 就把它换成 "https://api.deepseek.com/v1"
)

resp = client.chat.completions.create(
    model="gpt-4o",                            # 换成 DeepSeek 要换成其模型名
    messages=[{"role": "user", "content": "你好"}],
    temperature=0.2,                           # 结构化场景调低
)
print(resp.choices[0].message.content)
```

#### 1.2 Claude 原生 SDK 对照

海外直连 Claude 不走 OpenAI 兼容格式，而是用官方 `anthropic` SDK——整体写法高度相似，但有三处结构差异要记牢。

```bash
pip install anthropic
```

```python
import os
from anthropic import Anthropic

client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

resp = client.messages.create(
    model="claude-sonnet-4-20250514",           # 如需最新可替换为 Claude Sonnet 4.5 系列 ID（见官方 docs）
    max_tokens=1024,                              # 必传: 限制输出长度
    system="你是一位严谨的技术助手。",               # 差异1: system 是顶层参数, 不塞进 messages
    messages=[{"role": "user", "content": "用一句话介绍 Agent"}],
)

# 差异2: 响应是 content blocks 列表, 文本要取每个块的 .text
print("".join(b.text for b in resp.content if b.type == "text"))
```

流式则换成 `client.messages.stream(...)`（上下文管理器，逐事件消费）：

```python
with client.messages.stream(
    model="claude-sonnet-4-20250514",
    max_tokens=1024,
    system="你是一位严谨的技术助手。",
    messages=[{"role": "user", "content": "写一段300字介绍AI Agent"}],
) as stream:
    for text in stream.text_stream:     # text_stream 只吐文本增量, 相当于 delta.content
        print(text, end="")
```

与 OpenAI 格式的三个差异点：

| 差异点 | OpenAI 兼容写法 | Claude 原生写法 |
|-|-|-|
| system 位置 | messages 首条 `{"role": "system", ...}` | 顶层参数 `system="..."` |
| 响应结构 | `resp.choices[0].message.content`（字符串） | `resp.content` 是 content blocks 列表，文本块要取 `.text` |
| 工具调用 | `tools` / `tool_choice` | 参数同名、无独立命名差异，照常支持 function calling |

> ⚠️ 国内生产环境常用 DeepSeek / Qwen 的 OpenAI 兼容接口，Claude 原生 SDK 主要用于海外模型直连；两者切换成本就集中在「system 位置」与「content 结构」这两处，改对它们基本就完成了平移。

### 2. 流式调用（stream=True）

#### 2.1 为什么流式重要

```mermaid
sequenceDiagram
    participant C as 你的程序
    participant S as 服务端
    C->>S: 发送请求 stream=True
    S-->>C: [第1片] 几百毫秒就到
    S-->>C: [第2片] ...
    Note over C,S: 首字延迟从数秒降到几百毫秒
    S-->>C: [最后一片] 流结束
```

- 服务端边生成边返回分片，**首字延迟从数秒降到几百毫秒**。Agent 的 SSE 输出、前端打字机效果全建立在它之上。

```python
from openai import OpenAI

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

# stream=True: 用 for 循环逐块接收; 每块都是一个增量片段
stream = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "写一段300字介绍AI Agent"}],
    stream=True,               # 关键开关: 开启流式
)

buffer: list[str] = []
for chunk in stream:
    # 每个 chunk 里才真正有增量文本; 有的 chunk 是空的/元数据
    delta = chunk.choices[0].delta.content
    if delta:                  # 为空说明是结束或元数据, 跳过
        buffer.append(delta)
        print(delta, end="")   # 前端在这里实时渲染 (打字机)
print()                        # 换行
print("完整回答:", "".join(buffer))
```

### 3. 错误码与限流处理

| 错误码 | 含义 | 处理 |
|-|-|-|
| 429 | 触发限流 | 等待退避后重试 |
| 401 | 密钥无效 | 检查 Key |
| 404 | 模型名写错 | 检查模型名 |
| 5xx | 服务商故障 | 重试或降级兜底 |

- 防御组合拳：信号量控并发 + 退避重试（tenacity）+ 必要时申请提额。

```python
import os
import time
from openai import OpenAI

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

def call_with_retry(messages, max_attempts: int = 3):
    """对 429/5xx 做指数退避重试, 401/404 直接失败不重试。"""
    wait = 1
    for attempt in range(1, max_attempts + 1):
        try:
            resp = client.chat.completions.create(model="gpt-4o", messages=messages)
            return resp.choices[0].message.content
        except Exception as e:
            code = getattr(e, "status_code", None)   # 拿到HTTP状态码
            if code in (401, 404):                   # 密钥/模型名错误, 重试没用
                raise
            print(f"第{attempt}次失败({code}), {wait}s后重试: {e}")
            time.sleep(wait)
            wait *= 2          # 1s→2s→4s 指数退避
            if attempt == max_attempts:
                raise          # 最后也失败就抛出去给上层兜底
```

### 4. 本地模型部署

| 工具 | 用途 | 特点 |
|-|-|-|
| Ollama | 本地调试 | 一键 `ollama pull` + `ollama serve`，自带 OpenAI 兼容端点 |
| vLLM | 生产吞吐 | 连续批处理 + PagedAttention 拉满 GPU 利用率 |

```bash
# Ollama: 拉一个 7B 小模型并启动 (默认端口 11434)
ollama pull qwen2.5:7b
ollama serve                     # 启动服务, 自带 OpenAI 兼容端点

# vLLM: 生产用, 端口 8000
vllm serve Qwen/Qwen2.5-7B-Instruct --port 8000
```

```python
# 本地模型调用: 只需换 base_url 和 model, 其他代码完全一致
from openai import OpenAI

local = OpenAI(
    api_key="EMPTY",                                   # 本地服务一般不需要真实key
    base_url="http://localhost:11434/v1",              # Ollama 的 OpenAI 兼容端点
)
resp = local.chat.completions.create(
    model="qwen2.5:7b",
    messages=[{"role": "user", "content": "1+1等于几"}],
)
print(resp.choices[0].message.content)
```

### 5. 本地模型做 Agent 的局限与对策

| 局限 | 现象 | 对策 |
|-|-|-|
| function calling 不稳 | 常漏参 / 传错参 | 工具 Function 描述写细 + Few-shot 给足示范 |
| JSON 输出不稳 | 结构错 / 被截断 | pydantic 强校验 + 「让模型重新输出」兜底 |
| 能力天花板 | 复杂推理差 | 关键业务场景直接切换云端大模型 |

```python
# 本地模型 JSON 兜底: 解析失败就让模型重新输出一次
def ask_llm_structured(prompt: str, max_try: int = 3):
    import json
    for i in range(max_try):
        out = local.chat.completions.create(   # local 为上文定义的本地 OpenAI 客户端(跨节依赖, 需先定义)
            model="qwen2.5:7b",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,       # 结构化输出调低
        ).choices[0].message.content
        try:
            return json.loads(out)          # 成功解析就返回
        except json.JSONDecodeError:
            prompt += f"\n上次输出不是合法JSON: {out}\n请重新只输出JSON。"  # 反馈重试
    raise RuntimeError("多次重试仍无法得到合法JSON，建议切换云端大模型")
```

## 本节自检

- [ ] 至少实操一家国内 + 一家国际模型 API（含流式调用）
- [ ] 能用 Ollama 本地部署并完成一次工具调用全流程
- [ ] 能为 429/5xx 写退避重试，对 401/404 直接 fail-fast

## 本节配套思考题（快速入门的检验）

1. 如果把 `base_url` 从 OpenAI 换成 DeepSeek，代码需要改哪几处？"兼容"到底兼容什么，不兼容什么？
2. 流式调用里 `chunk.choices[0].delta.content` 为空说明什么？你在 `for chunk in stream` 里如何过滤无用分片？
3. 本地小模型做 function calling 老出错，你会有哪三步具体对策（描述、示范、校验/兜底）？