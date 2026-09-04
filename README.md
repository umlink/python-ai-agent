# Python AI Agent 学习项目（FastAPI 服务骨架）

基于 FastAPI 的 Python 3 Agent 服务骨架，对应学习大纲「阶段一 / 阶段七」的分层设计：
**API 接入层 → Agent 编排层 → 工具服务层 → 存储层**。

## 项目结构

```
├── app/
│   ├── main.py          # FastAPI 入口（/health 健康检查）
│   ├── schemas.py       # Pydantic 数据模型（请求/响应校验）
│   ├── api/
│   │   └── routes.py    # API 接入层路由（/agent/chat）
│   └── __init__.py
├── docs/                # 学习大纲文档（飞书《Python AI Agent 学习计划》拆解）
│   ├── README.md        # 文档导航总览
│   ├── 00-专有名词速查表.md
│   ├── 01-阶段一-前置核心基础/   ...（每阶段一个文件夹，每个小点一个文件）
│   └── 11-学习建议与调整规则.md
├── requirements.txt
├── .env.example
└── .gitignore
```

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 启动服务
uvicorn app.main:app --reload --port 8000

# 3. 访问
# 健康检查:  GET  http://localhost:8000/health
# Swagger:   http://localhost:8000/docs
# 对话接口:  POST http://localhost:8000/agent/chat
```

## 学习路线

学习大纲已按「每个阶段一个文件夹、每个小点一个文件」拆解在 `docs/` 下，
从 [docs/README.md](docs/README.md) 开始按序学习。
