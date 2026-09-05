# CLAUDE.md

本文件为 AI 助手（Claude Code / 类 IDE 编码代理）在本仓库工作时提供项目级上下文。**项目结构或规范变化时，必须同步更新本文件**（见文末「同步维护」）。

## 项目一句话

Python AI Agent 学习项目：一份从入门到生产的 Agent 开发学习计划（`docs/` 8 阶段 + 配套），一套 FastAPI Agent 服务骨架（`app/`），以及各阶段离线可运行的演示 Demo（`code/`）。

## 常用命令

```bash
# 运行服务（开发）
uvicorn app.main:app --reload --port 8000

# 运行离线 Demo（纯标准库, 无需 API Key）
python3 code/阶段二/react_agent.py          # 手写 ReAct
python3 code/阶段三/react_langgraph_agent.py
python3 code/阶段四/rag_agent.py            # RAG 工具 Agent
python3 code/阶段五/planning_memory_agent.py
python3 code/阶段六/data_analysis_agent.py  # 数据分析五道防线
python3 code/阶段七/monitoring_agent.py     # 观测/告警/Bad-case
python3 code/阶段八/project_roadmap_navigator.py

# 依赖 / 质量（服务侧）
pip install -r requirements.txt
ruff format . && ruff check .          # 代码质量（配置在 pyproject.toml）
pytest                               # 关键接口单测（tests/）

# 工程化（可选）
make dev / make test / make lint      # 等价上面命令的快捷方式
docker compose up -d                  # 一键拉起 PG/Redis/MinIO/Qdrant
docker build -t python-ai-agent:latest .   # 构建服务镜像
```

## 目录结构（速览）

| 路径 | 定位 | 规则 |
|-|-|-|
| `app/` | FastAPI 服务骨架（生产风格） | 遵循 `docs/12-Python开发规范.md` |
| `app/main.py` | 应用工厂：`create_app()` + `lifespan` + 全局异常处理器 + 静态托管 | 不写业务逻辑 |
| `app/api/routes.py` | 路由（`APIRouter` + `tags`） | 只做 HTTP 编排 |
| `app/schemas/` | 请求/响应 Pydantic 模型（`common.py` 统一响应 `ApiResponse` + `BizCode`，`sse.py` 流式协议，其余按域拆分） | 统一响应 `{code, message, data, trace_id}`；SSE 走 `format_sse()` |
| `app/dependencies.py` | 可复用 `Depends` 依赖（鉴权/会话/配置/追踪） | 新增横切能力放这里 |
| `app/config.py` | `pydantic-settings` `Settings` 读 `.env`（含 PG/Redis/MinIO/Qdrant 连接串） | 禁止业务模块散落 `os.getenv` |
| `app/errors.py` | 业务异常类 + 全局异常处理器 | 新异常继承 `AppError` |
| `app/agents/` `app/tools/` `app/storage/` | 编排层/工具层/存储层（骨架） | 依赖单向，阶段七扩展 |
| `tests/` | pytest 单测（health/chat/sse/config） | `pytest` 运行 |
| `code/阶段N/` | 教学 Demo（纯标准库优先, 可离线跑） | 命名/分层原则与生产一致 |
| `docs/` | 学习文档（`00-12` 编号） | 非代码 |
| `requirements.txt` | 服务侧依赖声明 | **前瞻清单**：声明按设计需要，可超前于 `app/` 当前 import；新增依赖先加这里 |
| `pyproject.toml` | ruff/pytest 配置 + 项目元数据 | 新增规则在此集中管理 |
| `Dockerfile` / `docker-compose.yml` / `Makefile` | 容器化 / 本地组件编排 / 常用命令 | 与 `.env` 组件对应 |

## 架构分层（依赖单向）

```
app/api（接入层） → app/agents（编排层） → app/tools（工具服务层） → app/storage（存储层）
```

- 接入层不碰存储层；编排层不写路由。出现「下层 import 上层」即违规。

## 核心编码约定（速查）

- **配置**：`pydantic-settings`（`BaseSettings` + `SettingsConfigDict(env_file=".env")`），不用 `python-dotenv` 手写加载。
- **依赖注入**：跨端点复用的鉴权/会话/配置一律 `Depends(...)` 注入，禁止路由内手动 `Client()`。
- **接口**：Pydantic 声明请求/响应 + `response_model` + `status_code` + `tags`；SSE 用 `StreamingResponse(media_type="text/event-stream")`。
- **统一响应**：所有成功响应 `ApiResponse.ok(data)`；业务错误 `ApiResponse.fail(BizCode.XXX)`；结构 `{code, message, data, trace_id}`（见 `app/schemas/common.py`）。
- **SSE 流式**：帧构造一律 `format_sse()`（见 `app/schemas/sse.py`），事件流转 `meta → message_start → (delta/tool_call/tool_result)* → done`，出错先发 `error` 再补 `done` 兜底；禁止路由内手拼帧字符串。
- **异常**：继承 `AppError`（含 `biz_code` + `http_status`），`register_exception_handlers` 全局转码为统一响应；`RequestValidationError`（422→`code=40001`）与 `HTTPException` 已接管，所有错误路径一律返回 `{code, message, data, trace_id}`。
- **追踪链路**：请求 ID 由 `main.py` 的中间件统一生成/沿用并写入 `request.state.trace_id`，路由、异常处理器、`X-Request-ID` 响应头读同一来源，保证正常与异常链路同源。
- **外呼**：`httpx` 必设 `timeout`；`tenacity` 指数退避重试（默认 `stop_after_attempt(3)`）；幂等才重试。
- **日志**：统一 `loguru.logger`，带 `trace_id`；Demo 教学文件可用 `print`。
- **空结果**：如实报空、勿编造，禁止模型补齐不存在的数据。
- **多租户**：`thread_key(tenant_id, session_id)` 组合会话键（见 `docs/08-阶段八-实战项目路线/05-Level5-…md`）。

## 防过度设计准则（必读）

本仓库是**学习项目 + 生产骨架**的混合体，最容易在「为将来做准备」时把基建做过头。任何新增抽象、分层、依赖、配置，先对照以下红线 —— 命中任意一条即应停下重新审视。

**1. 抽象必须有当下的受益者。** 每新增一层（service / repository / 中间件 / 基类 / 装饰器）先回答：现在有没有代码用它？没有受益者的空壳就是为抽象付费。典型反例：为「将来可能加 service」新建空的 `app/services/`。

**2. 用「推迟到触发时机」替代「提前预埋」。** 基础设施按真实需求点再建，不要一次性铺开。本仓库当前的推迟清单：Alembic 等第一张真实业务表；`/readyz` 等存储层接入后；API Key 鉴权等服务对外开放时；状态持久化等多 worker 真正要共享状态时；RAG 相关未用依赖等阶段四落地前不深层封装。

**3. 单一职责，但不为职责细分而细分。** 允许一个大文件承载一个完整职责（如 `high-level` 服务可适度内聚），不必为「内聚」强行拆包。文件拆分以「读的人会迷路」为标准，而非行数。

**4. 分层方向是硬约束，层数是软约束。** 依赖单向（`api → agents → tools → storage`）必须遵守；但四层各自内部是否再分子层，留给实际复杂度决定，不为「看起来规整」加层。

**5. 全局机制要给，但只给一次。** 统一响应、SSE 协议、异常转码、trace_id 等横切机制做一次、做对，后续一律复用、禁止绕行。与之相对：为单个调用点临时造的轮子（手拼 SSE 帧、散落 `os.getenv`）是漏不是省。

**6. 依赖与配置从简起步。** 新增依赖必须有当下真实用途（见 `requirements.txt` 头部注释）；新增配置项 = `Settings` 加字段 + `.env.example` 补一行。禁止「先装上大概率会用到的」。

**7. 扩展点要「留位置」，不要「做实现」。** 比如 SSE 已预留 `tool_call / tool_result / ping` 事件、SSM 配置、会话态等，位置已定但实现待真实接入。把 do-nothing 的占位实现留在那里，比预写一套将来要返工的实现更好。

**8. 怀疑自己的编辑器视野。** 感到「这里加一层更规范」时，反问：这是让**此刻**读代码的人更清楚，还是满足某种在别处看到的「最佳实践」？后者往往是过度设计。

> 权威版含推迟清单与自查三问：`docs/12-Python开发规范.md` §12。（同维护进 §4 同步触发）

## 文档索引（新增/修改文档时参考）

- 开发规范全文：[`docs/12-Python开发规范.md`](docs/12-Python开发规范.md)
- 学习总览 / Demo 表：[`docs/README.md`](docs/README.md)
- 阶段目录：`docs/0X-阶段X-…/`（每阶段一个文件夹，每小点一个 Markdown）

## 同步维护

**每次改动涉及以下任一项时，同步更新本文件**：

1. 新增/移动/删除 `app/` 或 `code/` 下的目录或模块；
2. 增删依赖（`requirements.txt`）或配置项（`.env.example` / `app/config.py`）；
3. 新增常用命令（新 Demo、新测试、新脚本）；
4. 分层或规范发生变更（先改 `docs/12-Python开发规范.md`，再回填本节「核心编码约定」；防过度设计准则若增删红色条款，同步 §「防过度设计准则」）。

同步时保持**精简**：只记录影响协作的事实（命令/路径/约束），详细论述留在 `docs/` 文档。
