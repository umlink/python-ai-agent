# Python AI Agent 学习计划（精简大纲 + 学习详情）

> 本目录由飞书文档《Python AI Agent 学习计划》拆解而来。
> 拆解规则：**每个阶段一个文件夹，每个学习小点一个 Markdown 文件**，编号命名，按序学习。

## 学习总览（8 个阶段）

| 阶段 | 主题 | 目录 |
|-|-|-|
| 阶段一 | 前置核心基础（Python 高级 / 大模型与 Prompt / 软件工程基础设施） | [01-阶段一-前置核心基础](01-阶段一-前置核心基础) |
| 阶段二 | AI Agent 核心理论与基础范式（含综合实战 Demo） | [02-阶段二-AI-Agent核心理论与基础范式](02-阶段二-AI-Agent核心理论与基础范式) |
| 阶段三 | 主流 Agent 开发框架（LangGraph / LlamaIndex / CrewAI / AutoGen） | [03-阶段三-主流Agent开发框架](03-阶段三-主流Agent开发框架) |
| 阶段四 | 工具生态与外围组件集成（工具调用 / 向量库 / RAG，含综合实战 Demo） | [04-阶段四-工具生态与外围组件集成](04-阶段四-工具生态与外围组件集成) |
| 阶段五 | 进阶能力增强与优化（多智能体 / 规划 / 记忆 / 评测 / 安全对齐，含综合实战 Demo） | [05-阶段五-进阶技术](05-阶段五-进阶技术) |
| 阶段六 | 垂直领域 Agent 落地实践（代码 / 数据分析 / 内容 / 客服 / 办公自动化，含综合实战 Demo） | [06-阶段六-垂直领域Agent落地实践](06-阶段六-垂直领域Agent落地实践) |
| 阶段七 | 工程化、部署与运维（含综合实战 Demo） | [07-阶段七-工程化部署与运维](07-阶段七-工程化部署与运维) |
| 阶段八 | 从入门到生产的实战项目路线（Level 1-5，含综合实战 Demo） | [08-阶段八-实战项目路线](08-阶段八-实战项目路线) |

## 配套文档

| 文档 | 说明 | 文件 |
|-|-|-|
| 专有名词速查表 | 正文出现名词的一句话解释 | [00-专有名词速查表.md](00-专有名词速查表.md) |
| 四个月学习计划 | 每周任务版（共 16 周） | [09-四个月学习计划.md](09-四个月学习计划.md) |
| 配套学习资源清单 | 官方文档 / 开源项目 / 论文 / 评测基准 | [10-配套学习资源清单.md](10-配套学习资源清单.md) |
| 学习建议与调整规则 | 学习方法论与节奏调整 | [11-学习建议与调整规则.md](11-学习建议与调整规则.md) |
| Python 开发规范 | 目录 / 分层抽象 / 接口 / 工具函数 / 错误处理等工程约定 | [12-Python开发规范.md](12-Python开发规范.md) |
| CLAUDE.md | AI 协作上下文（命令 / 结构 / 约定速查 / 同步维护） | [CLAUDE.md](../CLAUDE.md) |

## 使用方式

1. 先读本页总览与 [专有名词速查表](00-专有名词速查表.md) 建立整体认知。
2. 按阶段顺序（一 → 八）逐个文件学习；每个文件含「精简大纲」与「学习内容详情」两部分。
3. 每个小点文件末尾附「本节小结 / 自检」，达标后再进入下一个点。
4. 阶段八的实战项目按 [四个月学习计划](09-四个月学习计划.md) 穿插进行。

## 可运行代码（demo）

各阶段配套的**离线可运行 Demo** 放在根目录 [code](../code) 下，文档中会标注对应文件。已提供：

| Demo | 位置 | 运行方式 |
|-|-|-|
| 阶段二 手写完整 Agent（ReAct / Plan-and-Execute / Reflexion） | [code/阶段二/react_agent.py](../code/阶段二/react_agent.py) | `python3 code/阶段二/react_agent.py` |
| 阶段三 LangGraph + LangChain 完整 Agent | [code/阶段三/react_langgraph_agent.py](../code/阶段三/react_langgraph_agent.py) | `python3 code/阶段三/react_langgraph_agent.py` |
| 阶段四 RAG 知识库 + 工具 Agent（工具工厂 / 混合检索 / Agent-RAG） | [code/阶段四/rag_agent.py](../code/阶段四/rag_agent.py) | `python3 code/阶段四/rag_agent.py` |
| 阶段四 综合实战文档（讲解 Demo 各部分） | [阶段四综合实战](../docs/04-阶段四-工具生态与外围组件集成/04-阶段四综合实战-RAG工具Agent.md) | 阅读 |
| 阶段五 多智能体工作流 Agent（分工协作 / 断点恢复 / 记忆 / 评估 / 注入检测） | [code/阶段五/planning_memory_agent.py](../code/阶段五/planning_memory_agent.py) | `python3 code/阶段五/planning_memory_agent.py` |
| 阶段五 综合实战文档（讲解 Demo 各部分） | [阶段五综合实战](../docs/05-阶段五-进阶技术/06-阶段五综合实战-多智能体工作流Agent.md) | 阅读 |
| 阶段六 数据分析 Text-to-SQL Agent（Schema Prompt / 语义层 / 五道防线） | [code/阶段六/data_analysis_agent.py](../code/阶段六/data_analysis_agent.py) | `python3 code/阶段六/data_analysis_agent.py` |
| 阶段六 综合实战文档（讲解 Demo 各部分） | [阶段六综合实战](../docs/06-阶段六-垂直领域Agent落地实践/06-阶段六综合实战-数据分析Agent.md) | 阅读 |
| 阶段七 观测台 + 告警 + Bad-case 闭环 Agent（三支柱 / 黄金四指标 / 闭环迭代） | [code/阶段七/monitoring_agent.py](../code/阶段七/monitoring_agent.py) | `python3 code/阶段七/monitoring_agent.py` |
| 阶段七 综合实战文档（讲解 Demo 各部分） | [阶段七综合实战](../docs/07-阶段七-工程化部署与运维/04-阶段七综合实战-监控与运维Agent.md) | 阅读 |
| 阶段八 五级项目路线导航器（递进关系 / 能力覆盖 / 进度跟踪 / 排期映射） | [code/阶段八/project_roadmap_navigator.py](../code/阶段八/project_roadmap_navigator.py) | `python3 code/阶段八/project_roadmap_navigator.py` |
| 阶段八 综合实战文档（讲解 Demo 各部分） | [阶段八综合实战](../docs/08-阶段八-实战项目路线/06-阶段八综合实战-五级项目路线导航.md) | 阅读 |

> 这些 Demo 不需要 API Key 即可运行（阶段二内置 MockLLM、阶段三内置剧本模型 FakeListChatModel、阶段四内置 SimTiny 向量库 + MockLLM、阶段五~八纯标准库），替换为真实模型只需改一行，详见对应文档（[阶段二综合实战](02-阶段二-AI-Agent核心理论与基础范式/05-阶段二综合实战-手写完整Agent.md) / [阶段三综合实战](03-阶段三-主流Agent开发框架/07-阶段三综合实战-LangGraph完整Agent.md) / [阶段四综合实战](04-阶段四-工具生态与外围组件集成/04-阶段四综合实战-RAG工具Agent.md) / [阶段五综合实战](05-阶段五-进阶技术/06-阶段五综合实战-多智能体工作流Agent.md) / [阶段六综合实战](06-阶段六-垂直领域Agent落地实践/06-阶段六综合实战-数据分析Agent.md) / [阶段七综合实战](07-阶段七-工程化部署与运维/04-阶段七综合实战-监控与运维Agent.md) / [阶段八综合实战](08-阶段八-实战项目路线/06-阶段八综合实战-五级项目路线导航.md)）。

> 根目录 [app](../app) 是一份 FastAPI 接入层骨架（路由 / 请求模型 / 流式入口），对应阶段七「部署到 API」的示例；它依赖 `requirements.txt`，需按阶段七结合真实模型使用，不参与上述离线 Demo。

## 核心原则

- 先理解原理（阶段二），不要一上来复制框架 Demo；框架只是封装，底层原理一致。
- **阶段三框架不必全学**：必修 LangGraph（编排/状态/持久化），LlamaIndex 用于 RAG 时再深入，CrewAI / AutoGen / 其他方案了解选型即可——16 周计划只给前三者时间，其余在 Level3 项目中按需触碰。
- 每阶段用「达成标准」自检后再进入下一阶段。
- 实践为王：每个知识点搭配小 Demo，主动制造错误场景复现 Bad-case。
