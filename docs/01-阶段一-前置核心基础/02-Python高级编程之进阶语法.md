# 阶段一 · 小点 2：Python 高级编程之进阶语法

> 所属：阶段一 前置核心基础（必备打底）
> 定位：这里的语法不是"可选加分项"，而是你读懂框架源码的钥匙。LangChain 的 `@tool`、tenacity 的 `@retry`、asyncio 的流式生成——全都建立在这五样东西上。

## 精简大纲

1. 装饰器：重试、日志埋点、权限校验、函数计时
2. 生成器 / 迭代器：节省内存、流式返回、适配 SSE
3. 上下文管理器：with 语法、资源自动释放
4. 类型注解：TypedDict / Optional / Union / Literal
5. 闭包：作用域、状态保存、回调底层原理

## 学习内容详情

### 1. 装饰器（@ 语法糖）

#### 1.1 一张图看懂本质

```mermaid
graph LR
    A[你的原始函数 func] -->|被装饰| B[装饰器 wrapper]
    B --> C[自动包一层: 加日志/重试/计时]
    C --> D[返回一个 新函数]
    D --> E[下次调用 func 时=调新函数]
```

> 一句话：`@xxx` 就是 `func = xxx(func)`。装饰器不动原函数代码，只在外面包一层"横切逻辑"。
> 为什么 Agent 里离不开它？tenacity 的 `@retry`、LangChain 的 `@tool` 全是装饰器。**看不懂装饰器就看不懂框架**。

```python
import time
import functools

def timer(func):
    """计时装饰器：帮任何函数统计耗时，不改原函数一行代码。"""
    @functools.wraps(func)              # 关键！保留原函数的 __name__/docstring
    def wrapper(*args, **kwargs):       # *args 收所有位置参数，**kwargs 收所有关键字参数
        start = time.perf_counter()
        result = func(*args, **kwargs)  # 调用原函数，把参数原样传进去
        elapsed = time.perf_counter() - start
        print(f"{func.__name__} 耗时 {elapsed*1000:.2f} ms")
        return result                   # 把原函数的结果原样返回
    return wrapper

# 用法一：@ 语法糖（等价于 process_data = timer(process_data)）
@timer
def process_data(n: int) -> int:
    # 这里假装做了点耗时的计算
    time.sleep(0.05)
    return n * 2

# 用法二：显式调用（二者完全等价，理解 @ 的真相）
# process_data = timer(process_data)

print(process_data(10))   # 输出: process_data 耗时约 50 ms，然后 20
```

> **带参数的装饰器（进阶）**：当装饰器本身需要参数（如 `@retry(max_attempts=3)`）时，外面要多包一层函数。不理解可以先用着，能用是目标。

```python
def retry(max_attempts: int = 3):
    """生产：给 LLM 调用加一个简易重试的装饰器。"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)   # 成功就直接返回
                except Exception as e:
                    print(f"第 {attempt} 次失败: {e}")
                    if attempt == max_attempts:    # 最后一次失败就抛出
                        raise
        return wrapper
    return decorator

@retry(max_attempts=3)
def call_llm(messages):
    # 模拟一个偶尔超时的模型调用
    import random
    if random.random() < 0.5:
        raise ConnectionError("网络抖动")
    return "模型回答成功"
```

### 2. 生成器 / 迭代器（流式输出关键）

#### 2.1 yield 到底发生了什么

```mermaid
sequenceDiagram
    participant C as 外层调用方
    participant G as 生成器(带yield的函数)
    C->>G: 第一次 next() / for 进来
    G-->>C: 执行到第一个 yield，产出值并挂起
    Note over C,G: 内存只保存当前状态，而非全部数据
    C->>G: 再 next() 回到上次暂停处
    G-->>C: 从暂停处继续，到下一个 yield 再产出
```

- 带 `yield` 的函数是**惰性求值**：不一次性全部算出，而要一个才吐一个。内存只占当前元素。
- **Agent 里的直接收益**：模型分片输出、大文档分块处理、逐条流式返回给前端。

```python
def read_chunks(path: str, size: int = 8192):
    """生成器：逐块读取文件，一块都不浪费内存。"""
    with open(path, "r", encoding="utf-8") as f:
        while True:
            chunk = f.read(size)
            if not chunk:        # 读到末尾
                break
            yield chunk          # 产出当前块，暂停；下次从这继续

# 用法：for 循环就是反复 next() 的过程
for i, block in enumerate(read_chunks("big.txt")):
    print(f"第 {i} 块: 前10字符={block[:10]}")
    # 可以在这把 block 分块喂给模型做 embedding
    if i > 2:                   # 演示只要前 3 块
        break
```

```python
def stream_answer(text):
    """生成器：模拟模型分片输出，Agent 的 SSE 流式就长这样。"""
    words = text.split(" ")
    for w in words:
        yield w + " "          # 每次 yield 一个词，前端逐词打字机渲染

for piece in stream_answer("你好 我是 AI 助手 正在 流式 输出"):
    print(piece, end="")       # 每来一块打一个词，无换行
print()
```

> **生成器表达式**：把方括号换成圆括号就是惰性的，如 `(x*x for x in range(10))`，多用于大数据量遍历。

### 3. 上下文管理器（with）

#### 3.1 原理图

```mermaid
graph TD
    A[with obj as x:] --> B[进入: 自动调用 obj.__enter__]
    B --> C[拿到 __enter__ 的返回值 x]
    C --> D[执行 with 内的代码块]
    D -->|正常结束| E[退出: 自动调用 __exit__ 释放资源]
    D -->|中途抛异常| E2[退出: 照样调用 __exit__, 释放资源]
```

- 保证资源被释放，**即使中途抛异常也一样**。文件、数据库连接、HTTP 客户端都靠它自动关闭。
- 自定义场景用 `@contextmanager` 装饰器最简洁。

```python
from contextlib import contextmanager

@contextmanager
def open_db_conn(dsn: str):
    # 进入 with 块时执行（拿资源）
    conn = connect(dsn)                     # 假设有 connect 函数
    print("数据库连接已建立")
    try:
        yield conn                          # with xx as c 里的 c 就是它
    finally:
        # 退出 with 块（无论成败）必执行（释放资源）
        conn.close()                        # 保证连接一定被关，防泄漏
        print("数据库连接已关闭")

# 用法
with open_db_conn("postgres://...") as db:
    db.execute("SELECT 1")                  # 用连接干活，用完自动关
```

> **进阶**：`__exit__` 可以返回 True 表示"吞掉这个异常"。但 Agent 里别乱吞（连同小点1的裸 except 一样），留因果链才好排查。

### 4. 类型注解

类型注解让你 / IDE / 静态检查工具（mypy）三者共用一套"数据形状"契约。**注意：它只做提示，运行时默认不强制**；要运行时必校验，请配合小点 4 的 pydantic。

```python
from typing import TypedDict, Optional, Union, Literal

# TypedDict：给"形状已知的 dict"结构化提示
class ToolResult(TypedDict):
    tool_name: str          # 必填字段：工具名
    output: str             # 必填字段：工具输出
    cost: Optional[float]   # 可选字段：成本，可能为 None

def run_tool(tool: str) -> ToolResult:
    # 返回字典时，IDE 会帮你检查 key 是否拼错
    return {"tool_name": tool, "output": "搜到3条", "cost": 0.01}

# Literal：把所有合法取值写死，参数只准传这些
def load_config(env: Literal["dev", "test", "prod"]) -> dict:
    # env 只准是 dev/test/prod，传其他 IDE 立刻标红
    return {"env": env}

# Union / Optional：参数类型可以是多个
def merge(a: Union[int, str], b: Optional[int] = None) -> str:
    # a 是 int 或 str；b 可为 None
    return str(a) + (str(b) if b is not None else "")
```

> **和 Agent 的关系**：LangGraph 的 `State` 定义、pydantic 的模型字段，全以这套注解为语法基础。看懂它，后面阶段三的阶段状态机就顺了。

### 5. 闭包（Closure）

#### 5.1 作用域捕获图

```mermaid
graph TD
    A[外层函数 outer] -->|内部定义了变量 count| B[内层函数 inner]
    B -->|inner 引用 outer 的 count| C[形成闭包]
    C -->|返回 inner 后, count 存留在内存| D[每次调用 inner 都能改 count]
    style C fill:#e6eeff
```

- 内层函数捕获外层变量并"随身携带"，即使外层函数已经返回，这份私有状态依然存在。
- **Agent 场景**：为每个会话独立计数（尝试次数、轮次）、回调绑定底层原理。

```python
def make_counter():
    """闭包工厂：给每个会话生成一个独立的计数器。"""
    count = 0                       # 外层私有变量
    def inc():
        nonlocal count              # 关键！声明"我要改外层变量"，否则 UnboundLocalError
        count += 1
        return count
    return inc                      # 返回内层函数，count 被它带走

sessionA_counter = make_counter()   # 会话A的独立计数
sessionB_counter = make_counter()   # 会话B的独立计数(与A互不影响)

print(sessionA_counter())           # 1
print(sessionA_counter())           # 2
print(sessionB_counter())           # 1  ← B 从自己的 0 开始，不受 A 影响
```

> ⚠️ **最常见的报错**：内层函数直接 `count += 1` 而不写 `nonlocal count`，会报 `UnboundLocalError: local variable 'count' referenced before assignment`。因为 Python 认为你在内层局部新建了一个同名变量。记住：**要改外层就得 `nonlocal`**。

## 本节自检

- [ ] 能手写一个计时装饰器（含 `functools.wraps`），并解释 `@tool` 大致在做什么
- [ ] 能写一个 yield 生成器逐块读取大文件，并说清它为何省内存
- [ ] 会用 `@contextmanager` 保证资源被释放，即使抛异常
- [ ] 能说出 TypedDict / Literal / Optional 各自解决什么问题
- [ ] 能解释闭包为何能"携带"私有状态，并知道何时要写 `nonlocal`

## 本节配套思考题（快速入门的检验）

1. 去掉代码里的 `@functools.wraps(func)`，观察被装饰函数的 `__name__` 变成了什么，为什么框架里几乎都保留它？
2. `next(gen)` 和 `for x in gen` 都怎么推进生成器？生成器"用一次就耗尽"，你该如何理解？
3. 写一个闭包：让多次调用依次返回 0,1,1,2,3,5...（斐波那契），并说明它如何"记住"上一步状态。