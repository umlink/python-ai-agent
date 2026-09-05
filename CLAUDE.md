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

## 目录结构（速览）

| 路径 | 定位 | 规则 |
|-|-|-|
| `app/` | FastAPI 服务骨架（生产风格） | 遵循 `docs/12-Python开发规范.md` |
| `app/main.py` | 应用工厂：`create_app()` + `lifespan` + 全局异常处理器 + 静态托管 | 不写业务逻辑 |
| `app/api/routes.py` | 路由（`APIRouter` + `tags`） | 只做 HTTP 编排 |
| `app/schemas/` | 请求/响应 Pydantic 模型（`common.py` 统一响应 `ApiResponse` + `BizCode`，其余按域拆分） | 统一响应结构 `{code, message, data, trace_id}` |
| `app/dependencies.py` | 可复用 `Depends` 依赖（鉴权/会话/配置/追踪） | 新增横切能力放这里 |
| `app/config.py` | `pydantic-settings` `Settings` 读 `.env`（含 PG/Redis/MinIO/Qdrant 连接串） | 禁止业务模块散落 `os.getenv` |
| `app/errors.py` | 业务异常类 + 全局异常处理器 | 新异常继承 `AppError` |
| `app/agents/` `app/tools/` `app/storage/` | 编排层/工具层/存储层（骨架） | 依赖单向，阶段七扩展 |
| `tests/` | pytest 单测（health/chat/config） | `pytest` 运行 |
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
- **异常**：继承 `AppError`（含 `biz_code` + `http_status`），`register_exception_handlers` 全局转码为统一响应（Pydantic 422 自动处理, 不自定义）。
- **外呼**：`httpx` 必设 `timeout`；`tenacity` 指数退避重试（默认 `stop_after_attempt(3)`）；幂等才重试。
- **日志**：统一 `loguru.logger`，带 `trace_id`；Demo 教学文件可用 `print`。
- **空结果**：如实报空、勿编造，禁止模型补齐不存在的数据。
- **多租户**：`thread_key(tenant_id, session_id)` 组合会话键（见 `docs/08-阶段八-实战项目路线/05-Level5-…md`）。

## 文档索引（新增/修改文档时参考）

- 开发规范全文：[`docs/12-Python开发规范.md`](docs/12-Python开发规范.md)
- 学习总览 / Demo 表：[`docs/README.md`](docs/README.md)
- 阶段目录：`docs/0X-阶段X-…/`（每阶段一个文件夹，每小点一个 Markdown）

## 同步维护

**每次改动涉及以下任一项时，同步更新本文件**：

1. 新增/移动/删除 `app/` 或 `code/` 下的目录或模块；
2. 增删依赖（`requirements.txt`）或配置项（`.env.example` / `app/config.py`）；
3. 新增常用命令（新 Demo、新测试、新脚本）；
4. 分层或规范发生变更（先改 `docs/12-Python开发规范.md`，再回填本节「核心编码约定」）。

同步时保持**精简**：只记录影响协作的事实（命令/路径/约束），详细论述留在 `docs/` 文档。
