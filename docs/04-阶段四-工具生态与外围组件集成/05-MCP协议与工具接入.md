# MCP 协议与工具接入（工具生态的现代标准）

> 本讲为 2026 年补齐的时效性专题，建议穿插在「01-工具调用生态」之后学习。
> 定位：理解协议定位与安全边界即可，最小 Demo 跑通一遍；**工程上不必急着上**（见第 6 节触发时机）。

## 精简大纲

1. 为什么需要 MCP：N×M 集成爆炸 → 一套标准协议
2. 核心概念：Host / Client / Server 与三大原语（tools / resources / prompts）
3. 传输与部署形态：stdio（本地）/ Streamable HTTP（远程）
4. 最小实战：用 Python SDK 把「工具工厂」的工具暴露成 MCP Server
5. Agent 接入 MCP（客户端侧）：LangChain / OpenAI Agents SDK
6. 安全边界与工程落地建议（什么时候该上、什么时候不该）

## 学习内容详情

### 1. 为什么需要 MCP

回看「01-工具调用生态」：我们用**工具工厂**在进程内注册工具，Agent 与工具同进程。这在单一应用里没问题，但现实中工具生态是**跨应用**的：

- Claude Desktop、ChatGPT、自研 Agent 服务都想用「同一个搜索工具 / 同一个 Postgres 查询工具」；
- 每个宿主 × 每个工具都写一遍集成，就是 N×M 的爆炸；
- 工具方更惨：每接入一个新宿主要按对方的私有格式重写一遍。

**MCP（Model Context Protocol）** 把它收敛成 N+M：工具方实现一次 MCP Server，宿主方实现一次 MCP Client，中间走标准协议。类比「AI 工具的 USB-C」。

时间线（理解它的行业地位）：

- 2024-11：Anthropic 开源发布 MCP，首批参考 Server（GitHub / Postgres / 文件系统等）；
- 2025-03：OpenAI 宣布采纳（ChatGPT、Agents SDK 原生 MCP 客户端）；
- 2025-04：Google 确认 Gemini 支持；此后 Microsoft / AWS / Cloudflare / Snowflake 等跟进；
- 2025-12：治理权移交至 Linux Foundation 旗下的 **Agentic AI Foundation（AAIF）**（Anthropic / OpenAI / Block 等联合发起），社区 MCP Server 超过 1 万个；
- 2026 年现状：MCP 已是 Agent 接入外部工具的事实标准，ChatGPT 的 MCP 连接器已演化为「apps」生态。

> ⏳ **短期可不深究**：上面这串具体的发布日期（2024-11 / 2025-03 / 2025-12…）和厂商跟进节奏**第一遍听过即可，不用背年份**——它们只帮你建立“MCP 是主流标准”的行业直觉，面试不会考到具体哪年哪家。知道「Anthropic 发起、OpenAI/Google 采纳、已交 Linux Foundation 旗下 AAIF 治理」这条主线就够。

**与本大纲工具工厂的关系**（关键认知，防混淆）：

| | 工具工厂（阶段四 01） | MCP |
| - | - | - |
| 抽象层级 | 进程内注册表（Python dict） | 跨进程标准协议（JSON-RPC 2.0） |
| 解决什么 | 单应用内工具的组织与校验 | 跨应用/跨语言的工具共享 |
| 工具定义 | 五要素（name/desc/schema/execute/错误封装） | tools 原语（同样的五要素，换成协议格式） |

两者不冲突：工具的**开发五要素完全不变**，变的只是「注册与发现」这一层——从进程内 registry 换成协议级 Server。

> 🔬 **深度理解 · MCP 协议的 host-client-server 结构与价值**：
> 1. **本质**：MCP 把「工具集成」从**两两手写（N×M 爆炸）**规约成**一对标准化的“供应-消费”协议（N+M）**。**Host** 是跑 Agent 的宿主应用（Claude Desktop / ChatGPT / 你的服务）；**Client** 是宿主内对应某个 Server 的一条连接（协议真正在 client-server 之间跑，宿主可同时连很多个 Server，各持一连接）；**Server** 是暴露能力的进程或远程服务。工具的“注册与发现”从进程内 dict 升级成跨进程协议。
> 2. **机制（为什么能收敛）**：Server 只按标准宣称并暴露能力（tools/resources/prompts），Client 只按标准发现并调用——两边都实现一次协议，中间通用，于是「1 个宿主 × N 个工具」不再需要 N 份定制代码，新接入一个 Server 只是“多连一条 Client 连接”。数据面走 JSON-RPC 2.0（`tools/list` 列出工具、`tools/call` 发起调用），参数用 JSON Schema，与 OpenAI function calling 同构。它相当于给“工具接入”立了一个跨应用、跨语言的**互操作边界**：工具方写一次、多处消费，Host 方接一次、多工具通用。
> 3. **为什么重要**：它框定了「工具的互操作丢在哪一层」——能力描述、发现、调用、权限全部归一成协议，避免每个宿主×每个工具都重写一遍私有格式；也让第三方工具生态（上万 Server）直接可被任意 MCP 客户端接入。Actor 三角（Host/Client/Server）是理解所有 MCP 问题的最小坐标系。
> 4. **易错点/常见误解**：误解一「Host 就是 Client」——同一宿主内可以同时挂多条 Client 连接，Host 是应用、Client 是单条连接；误解二「Server 在宿主进程里」——它可以是独立子进程（stdio）或远程服务（HTTP），不必然在宿主内；误解三「MCP 取代工具工厂/五要素」——五要素照旧，MCP 只替换最上层的“注册与发现”，两者分层不冲突。

### 2. 核心概念：Host / Client / Server 与三大原语

三个角色：

- **Host**：宿主应用，即跑 Agent 的那端（Claude Desktop、ChatGPT、你的 FastAPI 服务）；
- **Client**：宿主内与某个 Server 的一条连接（协议在 client-server 之间，宿主可同时连多个 Server）；
- **Server**：暴露能力的服务（一个 Python 进程、一个远程 HTTP 服务均可）。

三大原语（Server 能暴露什么）：

| 原语 | 是什么 | 谁控制调用 | 对应本项目概念 |
| - | - | - | - |
| **tools** | 可执行函数，模型通过 function calling 决定调用 | 模型决定（LLM-controlled） | 工具工厂的 tool |
| **resources** | 只读数据源（文件内容、数据库行、配置） | 宿主决定（application-controlled） | 类似 RAG 的检索文档输入 |
| **prompts** | 可复用提示模板（用户主动唤起） | 用户决定（user-controlled） | 类似 prompt 模板库 |

消息层是 JSON-RPC 2.0：初始化时做**能力协商**（client/server 互相声明支持什么），之后工具列表发现（`tools/list`）与工具调用（`tools/call`）都是标准方法。工具参数 Schema 用的就是 JSON Schema——和 OpenAI function calling 同一套，所以模型侧无感。

> 🔬 **深度理解 · MCP 三大原语与 tools 的「模型约束」**：
> 1. **本质**：三大原语 `tools` / `resources` / `prompts` 是按**“谁能发起调用、谁控制使用”**划分的三类 server 能力，而不是“三样都是函数”。**tools** 是模型通过 function calling 自主决定调用的可执行动作（LLM-controlled）；**resources** 是只读数据源（文件、数据库行），由宿主代码按需取用喂给模型（application-controlled）；**prompts** 是可复用提示模板，由用户主动唤起（user-controlled）。
> 2. **机制**：区分它们的落点是**“控制权与信任边界”**。tools 让模型拿“执行权”、后果不可控，所以必须配鉴权与审计；resources 只读、风险小、相当于把“要喂给模型的外部知识/上下文”标准化；prompts 换成“用户点名要的指令配方”。MCP 的 `tools/list` / `resources/...` / `prompts/...` 分别对应三类 discovery，host 端据此决定把哪些交给模型。`tools` 的 Schema 沿用的是 JSON Schema——与 OpenAI/大部分 function calling 同一表述，所以“模型侧无感”。
> 3. **为什么重要**：它把“哪些能力可以暴露给模型、哪些不该由模型碰”变成协议内置的设计决策，避免把所有能力一股脑塞给 LLM；也给安全（只读 vs 可执行）和复用（模板 vs 数据 vs 动作）提供了清晰分层。
> 4. **易错点/常见误解**：误解一「resources 也能让模型随便调」——resources 由宿主控制，不直接交给模型决策；误解二「tools 就是一切」——很多数据接入场景该用 resources 而非 tools；误解三「MCP 改变了 function calling 本身」——它只换“工具如何被发现与被声明”，模型侧的工具调用推理协议照旧。

### 3. 传输与部署形态

| 传输 | 场景 | 说明 |
| - | - | - |
| **stdio** | 本地子进程 | 宿主拉起 Server 子进程、走标准输入输出；Claude Desktop 连本地工具的默认方式，零网络配置 |
| **Streamable HTTP** | 远程部署 | Server 独立部署、HTTP 暴露（可带 OAuth 鉴权）；多端共享、生产部署形态；已取代早期的 HTTP+SSE 旧传输 |

⚠️ 选型速记：个人/内网工具用 stdio（最简单）；多应用共享或跨网络用 Streamable HTTP + 鉴权。另外 Server 是有状态的：每个会话对应一条连接，不要把连接做成全局单例。

### 4. 最小实战：把工具工厂的工具暴露成 MCP Server

Python 官方 SDK 自带 FastMCP，装饰器风格与工具工厂几乎一致。依赖：`pip install "mcp[cli]"`。

```python
"""mcp_search_server.py —— 把阶段四工具工厂的搜索工具暴露成 MCP Server"""
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("search-tools")


@mcp.tool()
def search_web(query: str, max_results: int = 5) -> dict:
    """联网搜索，返回标题、摘要与链接。

    Args:
        query: 检索词
        max_results: 返回条数上限
    """
    # 这里复用阶段四 01 的真实实现（重试 / 截断 / 错误封装都留在函数内部）
    try:
        results = tavily_search(query, max_results)
        return {"ok": True, "results": results}
    except Exception as e:
        # 工具五要素之「错误封装」：回传结构化错误而非抛异常，让模型自己决定重试或换路
        return {"ok": False, "error": f"搜索失败: {e}"}


if __name__ == "__main__":
    mcp.run(transport="stdio")  # 远程部署改为 transport="streamable-http"
```

对照工具工厂的五个要素逐一看：`@mcp.tool()` 装饰器从函数签名自动生成 name/desc/JSON Schema（type hints + docstring），`execute` 就是函数体，错误封装还是自己写——**一个已经写好的工厂工具，加个装饰器就变成了 MCP Server 上的工具**。

> ⏳ **短期可不深究**：FastMCP 装饰器、`mcp.run(transport=...)` 换传输、SDK 版本用法这类**上手细节第一遍不必死磕**——目标是“看懂一次调用长什么样”，真到要写 MCP Server 时照着官方 SDK 抄即可。把「五要素不变、只换注册发现层」这句核心逻辑记住，比记住装饰器参数重要得多。

### 5. Agent 接入 MCP（客户端侧）

**LangChain / LangGraph 侧**（`pip install langchain-mcp-adapters`）：MCP 工具被加载成普通 LangChain tool，直接进 ReAct 循环 / ToolNode：

```python
import asyncio
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent


async def main():
    async with MultiServerMCPClient(
        {
            "search": {  # 本地 stdio Server
                "transport": "stdio",
                "command": "python",
                "args": ["mcp_search_server.py"],
            },
            "kb": {  # 远程知识库 Server
                "transport": "streamable_http",
                "url": "http://kb.internal:8000/mcp",
            },
        }
    ) as client:
        tools = client.get_tools()
        model = ChatOpenAI(model="gpt-4o")   # 需 import: from langchain_openai import ChatOpenAI
        agent = create_react_agent(model, tools)  # 用法与本地工具完全一致
        result = await agent.ainvoke({"messages": [("user", "搜一下 LangGraph 最新版本")]})
        print(result["messages"][-1].content)


asyncio.run(main())
```

**OpenAI Agents SDK** 原生支持 MCP 客户端（这也是 2025-03 OpenAI 采纳后的直接产物）：

```python
# 依赖: pip install openai-agents
from agents import Agent, Runner
from agents.mcp import MCPServerStdio

async with MCPServerStdio(params={"command": "python", "args": ["mcp_search_server.py"]}) as server:
    agent = Agent(name="helper", instructions="...", mcp_servers=[server])
    result = await Runner.run(agent, "搜一下 LangGraph 最新版本")
```

核心收益就一句话：**Agent 侧的 ReAct 循环、工具调用解析、错误回传全都不用改**，工具从「本地注册」换成「协议发现」对模型透明。

⚠️ 一个现实坑：Server 的工具是全量下发的。一个接了 10 个 Server、上百个工具的 Agent，光工具 Schema 就能吃掉大量上下文 token——按会话场景**按需挂载**（客服会话只挂知识库 Server，别把运维工具也挂上）。

### 6. 安全边界与工程落地建议

MCP 把工具从「进程内函数」变成「网络服务」，攻击面同步扩大。三条红线：

1. **只连可信 Server**：MCP Server 返回的内容（搜索结果、文档内容）可能藏指令——这就是「01-工具调用生态」与阶段五 05 讲过的**间接注入**，防护照旧（外部内容标签隔离 + 高危工具二次确认）；
2. **执行层二次鉴权**：模型选了哪个 MCP 工具只是「建议」，权限判定必须在工具执行层做（用户角色白名单，见阶段五 05「越权工具调用防护」）；远程 Server 还要校验 OAuth scope；
3. **审计每次调用**：MCP 调用进审计日志（谁 / 何时 / 哪个 Server 的哪个工具 / 结果摘要），与阶段七 03 的工具调用埋点同一套方案。

工程节奏（呼应 `CLAUDE.md` 防过度设计准则「推迟到触发时机」）：

| 情况 | 建议 |
| - | - |
| 单一 Agent、单进程、工具自用 | 工具工厂内聚即可，**不上 MCP** |
| 多个宿主要共享同一批工具（Claude Desktop + 自研服务） | 值得上：工具实现一次、两端复用 |
| 想直接接入第三方 MCP 生态（1 万+现成 Server） | 客户端侧接入即可，白名单筛选 |
| 工具需要独立伸缩 / 独立发布节奏 | Server 独立部署（Streamable HTTP） |

生态参考：官方 reference servers（GitHub / Postgres / 文件系统 / Puppeteer 等）与社区服务器目录见 [modelcontextprotocol.io](https://modelcontextprotocol.io)；接入前先读源码或选高星维护活跃的，理由同红线 1。

## 本节小结 / 自检

**小结**：MCP 是 Agent 工具接入的事实标准（Anthropic 发起、OpenAI/Google 采纳、Linux Foundation 治理），本质是把「工具五要素」从进程内注册升级为 JSON-RPC 协议级发现；三大原语 tools/resources/prompts，两种传输 stdio/Streamable HTTP；Agent 侧循环不用改，安全上按「可信 Server + 执行层鉴权 + 审计」三红线执行；工程上按触发时机再上，不为标准而标准。

**自检**：

- [ ] 能说清工具工厂与 MCP 的关系（进程内抽象 vs 跨进程协议，五要素不变）
- [ ] 能说出三大原语各自的「谁控制调用」
- [ ] 能用 FastMCP 把一个既有工具包成 Server 并跑通一次调用
- [ ] 知道 stdio 与 Streamable HTTP 的选型依据
- [ ] 能复述安全三红线，并指出它们分别呼应本大纲哪几讲
- [ ] 能说清「什么时候不该上 MCP」

## 本节常见面试题（深度解析）

> 针对本节核心知识的面试高频点，配合"本质+机制"式理解，能让你答得既有深度又有广度。

### 面试题 1：为什么会产生 MCP？请讲清 N×M 集成爆炸是怎么被收敛成 N+M 的。

- **面试官想考察**：是否理解 MCP 存在的根本动机（互操作问题）而不是背“MCP 是协议”这句话；能否明确 Host/Client/Server 的分工。
- **专业作答（含深度）**：
  1. **痛点（N×M）**：Claude Desktop、ChatGPT、自研 Agent 都想用「同一个搜索工具 / 同一个 PG 工具」，但每个宿主×每个工具都要按对方私有格式写一遍集成，工具方每接入一个新宿主还要对着一套新格式重写——集成数随双边数量乘积爆炸。
  2. **收敛（N+M）**：MCP 把它标准化并拆解为三个角色——**Host**（宿主应用）、**Client**（宿主内到某一 Server 的连接）、**Server**（暴露能力的服务）。工具方实现一次 Server，宿主实现一次 Client，两边都只碰一份标准协议，新增一个 Server 只是多连一条连接，于是接入数从“乘积”降到“相加”。
  3. **落点**：能力描述、发现（tools/list）、调用（tools/call）全走 JSON-RPC 2.0，参数用 JSON Schema——与 function calling 同构，模型侧无感。
- **加分亮点 / 深度追问**：可主动提“类比 USB-C：统一的插座+统一的数据面”；被追问“MCP 和 gRPC/REST 有什么区别”时答“它不是一般 RPC，而是围绕‘模型驱动的能力暴露’设计的标准化 server-capability 模型，三大原语和 function calling 契合才是重点”。

### 面试题 2：MCP 的三大原语 tools / resources / prompts 各是什么？为什么这样划分？

- **面试官想考察**：是否真的按“控制权/信任边界”理解三大原语，而不是把三者都当成“工具”。
- **专业作答（含深度）**：
  1. **按控制权划分**：**tools** 由模型通过 function calling 自主决定调用（LLM-controlled，可执行、后果不可控）；**resources** 是只读数据源（把要喂给模型的外部上下文/文档/数据库标准化，application-controlled）；**prompts** 是可复用的提示模板，由用户主动唤起（user-controlled）。
  2. **为什么重要**：它把“暴露给模型的能力”分成不同信任层级——可执行动作必须配鉴权审计，只读数据风险低、只负责供给上下文，模板只是配方。这样安全边界和复用边界都清晰，避免把所有能力一股脑塞给模型。
  3. **机制体现**：三类 discovery（`tools/list`、`resources/…`、`prompts/…`）+ JSON Schema 参数即 tools 与 function calling 的无缝衔接。
- **加分亮点 / 深度追问**：可补“RAG 的知识库检索往往对应 tools（可执行检索动作），而原始文档对应 resources（只读供给）——同一份内容走不同原语含义完全不同”；被追问“tools 所以危险吗”时答“工具拿到执行权，出问题的面更大，配合越权防护/审计链路（阶段五）是标配”。

### 面试题 3：MCP 和“工具工厂/function calling”是什么关系？什么时候才值得上 MCP？

- **面试官想考察**：能否分清“进程内抽象 vs 跨进程协议”两层，避免把 MCP 神话成函数调用的替代品；是否有工程上的落地判断力。
- **专业作答（含深度）**：
  1. **关系**：工具的**开发五要素完全不变**（name/desc/schema/execute/错误封装），MCP 只替换最上层的“注册与发现”——把进程内 registry 换成协议级 Server。它不影响 function calling 的推理方式，只是把工具如何被发现与声明标准化；模型侧的工具调用照旧。
  2. **什么时候该上**：单一 Agent、单进程、工具自用 → 工具工厂内聚即可，不上 MCP；多个宿主需要共享同一批工具、要接入第三方 MCP 生态、或工具需要独立伸缩/发布节奏 → 才值得上。
  3. **附带成本**：MCP 把工具从“进程内函数”变成“网络服务”，攻击面扩大（间接注入、越权调用），需按“可信 Server + 执行层鉴权 + 审计”三红线，并用按需挂载控制工具 Schema 吃掉上下文。
- **加分亮点 / 深度追问**：可主动补“不为标准而标准，推迟到触发时机再用”呼应防过度设计；被追问“Server 工具全量下发会怎样”时答“上百个工具 Schema 会占大量上下文 token，应按会话场景只挂需要的 Server”。
