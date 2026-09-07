# Python AI Agent 学习项目

> 一套**从原理到生产**的 AI Agent 工程化学习系统：`8 个阶段 · 53 篇结构化文档 · 全离线可运行 Demo · 可用于生产的 FastAPI 服务骨架`。

本项目把"AI Agent 开发"的完整知识栈拆解为一条**可执行的学习路线**：既提供**分层严密的文档体系**（`docs/`，每一阶段、每一知识点独立成文），也配套**每阶段可离线运行的示例代码**（`code/`），并附一份**可直接扩展的 FastAPI Agent 服务骨架**（`app/`，对应阶段七「部署到 API」）与一套 **React 前端界面**（`frontend/`）。

## 项目定位

- **面向对象**：想系统学习 AI Agent 开发（而非碎片化调 API）的 Python 开发者。
- **学习路径**：阶段一（基础） → 阶段二（Agent 理论） → 阶段三（主流框架） → 阶段四（工具生态/RAG/MCP） → 阶段五（进阶能力） → 阶段六（垂直落地） → 阶段七（工程化部署） → 阶段八（实战项目路线）。
- **配套原则**：先理解原理再上手框架、文档与代码一一对应、实践为王（主动制造 Bad-case 复现）。

## docs/：学习文档体系（核心能力）

`docs/` 下是一套**按阶段组织、每知识点独立成文**的知识库。每个阶段一个文件夹、每个学习小点一个 Markdown 文件，编号命名、按序学习。每个文件统一包含「精简大纲 / 学习内容详情 / 本节自检 / 常见面试题（深度解析）」，并穿插 **⏳ 短期可不深究**（弱化非主线知识点）、**🔬 深度理解**（关键概念的"本质/机制/为何重要/易错点"）两类增强块，指导你**哪块该精学、哪块可先跳过**。

### 八阶段总览

| 阶段 | 主题 | 核心能力覆盖 | 配套 Demo |
|-|-|-|-|
| 一 | [前置核心基础](docs/01-阶段一-前置核心基础) | Python 高级编程、并发/异步、工具库、大模型原理、Prompt 工程、软件工程基础设施 | - |
| 二 | [AI Agent 核心理论与基础范式](docs/02-阶段二-AI-Agent核心理论与基础范式) | Agent 运行闭环、四大核心组件、ReAct / Plan-and-Execute / Reflexion、手写完整 Agent | ✅ [react_agent.py](code/阶段二/react_agent.py) |
| 三 | [主流 Agent 开发框架](docs/03-阶段三-主流Agent开发框架) | LangChain / LangGraph / LlamaIndex / CrewAI / AutoGen / 选型决策 | ✅ [react_langgraph_agent.py](code/阶段三/react_langgraph_agent.py) |
| 四 | [工具生态与外围组件集成](docs/04-阶段四-工具生态与外围组件集成) | 工具调用、向量数据库与记忆、RAG 技术体系、MCP 协议 | ✅ [rag_agent.py](code/阶段四/rag_agent.py) |
| 五 | [进阶技术](docs/05-阶段五-进阶技术) | 多智能体系统、规划增强、记忆优化、评估评测、安全与对齐 | ✅ [planning_memory_agent.py](code/阶段五/planning_memory_agent.py) |
| 六 | [垂直领域 Agent 落地实践](docs/06-阶段六-垂直领域Agent落地实践) | 代码开发 / 数据分析(Text-to-SQL) / 内容创作 / 智能客服 / 办公自动化 | ✅ [data_analysis_agent.py](code/阶段六/data_analysis_agent.py) |
| 七 | [工程化、部署与运维](docs/07-阶段七-工程化部署与运维) | 工程化最佳实践、部署伸缩、监控运维（黄金四指标/trace/SLI/SLO） | ✅ [monitoring_agent.py](code/阶段七/monitoring_agent.py) |
| 八 | [实战项目路线](docs/08-阶段八-实战项目路线) | Level 1-5 递进项目（问答→RAG→多角色→数据分析→企业客服） | ✅ [project_roadmap_navigator.py](code/阶段八/project_roadmap_navigator.py) |

> 每一阶段的「综合实战」均配有**图文讲解文档**，逐块拆解 Demo 的实现与生产化思路，见各阶段目录下的综合实战 Markdown 文件。

### 配套方法论文档

| 文档 | 说明 |
|-|-|
| [专有名词速查表](docs/00-专有名词速查表.md) | 正文出现的名词一句话解释，建立整体认知 |
| [四个月学习计划](docs/09-四个月学习计划.md) | 每周任务版（共 16 周），主路线规划 |
| [配套学习资源清单](docs/10-配套学习资源清单.md) | 官方文档 / 开源项目 / 论文 / 评测基准 |
| [学习建议与调整规则](docs/11-学习建议与调整规则.md) | 学习方法论、时间不足时的取舍规则、复盘规则 |
| [Python 开发规范](docs/12-Python开发规范.md) | 目录 / 分层抽象 / 接口 / 工具函数 / 错误处理等工程约定 |
| [迁移心智陷阱清单](docs/13-迁移心智陷阱清单.md) | 从旧领域/旧思维迁移到 Agent 开发时的认知陷阱（10 条）与破解抓手 |

> 学习从 [docs/README.md](docs/README.md) 开始，它含完整导航、全量 Demo 清单与核心学习原则。

## code/：全部离线可运行的示例

`code/` 下每个 Demo **无需 API Key 即可运行**（阶段二内置 MockLLM、阶段三内置剧本模型、阶段四内置 SimTiny 向量库 + MockLLM、阶段五至八纯标准库），替换为真实模型只需改一行，便于你离线理解并逐步接入真实能力。

```bash
# 例如运行阶段六的 Text-to-SQL 数据分析 Agent
python3 code/阶段六/data_analysis_agent.py
# 阶段五的多智能体工作流 Agent（分工/断点恢复/记忆/评估/注入检测）
python3 code/阶段五/planning_memory_agent.py
# 阶段七的监控与运维 Agent（三支柱/黄金四指标/Bad-case 闭环）
python3 code/阶段七/monitoring_agent.py
```

完整的逐文件运行方式见 [docs/README.md「可运行代码」](docs/README.md)。

## app/：FastAPI Agent 服务骨架（可用于生产）

`app/` 是一份**分层清晰的 FastAPI 服务骨架**，对应学习大纲「阶段一 / 阶段七」的分层设计：**API 接入层 → Agent 编排层 → 工具服务层 → 存储层**。内置：

- 统一请求追踪 `trace_id`（中间件生成 + 回写响应头）
- 全局异常处理器（统一转码）与 Pydantic 请求/响应校验
- SSE 流式对话接口（`POST /agent/chat`）、健康检查（`GET /health`）
- CORS、日志、配置分层与静态前端托管
- 配套 `tests/` 单元测试（`pytest`）与 `Dockerfile` / `docker-compose.yml`

## web/ 与 frontend/ 前端调试界面

- `web/index.html`：**零依赖接口调试台**，浏览器直接打开即可调 `/health` 与 `/agent/chat`。
- `frontend/`：**React + Vite + TypeScript + TailwindCSS v4 + shadcn/ui(Base UI) + React Router**（SPA 模式）构建的现代前端，用于后续对接服务与后续章节扩展。

## 快速开始

```bash
# 1. 安装服务侧依赖
pip install -r requirements.txt

# 2. 启动开发服务（热重载）
uvicorn app.main:app --reload --port 8000
#    亦可使用 make dev

# 3. 访问
# 健康检查:  GET  http://localhost:8000/health
# Swagger:   http://localhost:8000/docs
# 对话接口:  POST http://localhost:8000/agent/chat

# 4. 接口调试（可选）
# 浏览器直接打开 web/index.html，用图形界面调 /health 与 /agent/chat

# 5. 运行测试
pytest
```

更多命令见 [Makefile](Makefile)（`install / dev / test / lint / format / build / compose-up / compose-down`）。

## 项目结构

```
├── docs/                  # 学习文档体系（8 阶段 × 53 篇 + 配套方法论）
│   ├── README.md          # 文档导航总览
│   ├── 01~08-阶段*/       # 按序学习的学习文章 + 综合实战
│   ├── 00-专有名词速查表.md
│   └── 09~13-*.md         # 学习计划 / 资源 / 建议 / 开发规范 / 迁移心智陷阱
├── code/                  # 各阶段全离线可运行 Demo（阶段二~八）
├── app/                   # FastAPI Agent 服务骨架（API/编排/工具/存储分层）
├── web/index.html         # 零依赖接口调试台
├── frontend/              # React + Vite + TS + Tailwind v4 + Base UI(SPA)
├── tests/                 # 服务侧单元测试（pytest）
├── requirements.txt       # Python 依赖
├── pyproject.toml         # 工程配置 / ruff
├── Dockerfile             # 服务镜像
├── docker-compose.yml     # 一键拉起 PG/Redis/MinIO/Qdrant 等组件
└── Makefile               # 常用开发命令
```

## 核心学习原则

- **先原理后框架**：理解阶段二的 Agent 运行闭环与四大组件，再上手框架；框架只是封装，底层原理一致。
- **抓大放小**：阶段三框架不必全学——必修 LangGraph，LlamaIndex 用于 RAG 时深入，CrewAI / AutoGen 了解选型即可；文档以 **⏳ 短期可不深究** 标注非主线点，助你聚焦。
- **实践为王**：每个知识点搭配小 Demo，主动制造错误场景复现幻觉、死循环、解析失败等 Bad-case。
- **认识陷阱**：从旧领域迁移到 Agent 开发时的思维惯性容易踩坑，阅读《[迁移心智陷阱清单](docs/13-迁移心智陷阱清单.md)》可系统规避。

## 许可

[MIT License](LICENSE)。