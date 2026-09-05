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
- 治理权移交 Linux Foundation，社区 MCP Server 超过 1 万个；
- 2026 年现状：MCP 已是 Agent 接入外部工具的事实标准，ChatGPT 的 MCP 连接器已演化为「apps」生态。

**与本大纲工具工厂的关系**（关键认知，防混淆）：

| | 工具工厂（阶段四 01） | MCP |
| - | - | - |
| 抽象层级 | 进程内注册表（Python dict） | 跨进程标准协议（JSON-RPC 2.0） |
| 解决什么 | 单应用内工具的组织与校验 | 跨应用/跨语言的工具共享 |
| 工具定义 | 五要素（name/desc/schema/execute/错误封装） | tools 原语（同样的五要素，换成协议格式） |

两者不冲突：工具的**开发五要素完全不变**，变的只是「注册与发现」这一层——从进程内 registry 换成协议级 Server。

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
        agent = create_react_agent(model, tools)  # 用法与本地工具完全一致
        result = await agent.ainvoke({"messages": [("user", "搜一下 LangGraph 最新版本")]})
        print(result["messages"][-1].content)


asyncio.run(main())
```

**OpenAI Agents SDK** 原生支持 MCP 客户端（这也是 2025-03 OpenAI 采纳后的直接产物）：

```python
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
