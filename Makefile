# 常用开发命令（Makefile）
.PHONY: install dev test lint format build compose-up compose-down

install:            ## 安装服务侧依赖
	pip install -r requirements.txt

dev:                ## 启动开发服务（热重载）
	uvicorn app.main:app --reload --port 8000

test:               ## 运行单测
	pytest

lint:               ## 静态检查（工程代码；教学 Demo 由 extend-exclude 豁免）
	ruff check .

format:             ## 自动格式化（工程代码；教学 Demo 保持原样）
	ruff format app tests

build:              ## 构建 Docker 镜像
	docker build -t python-ai-agent:latest .

compose-up:         ## 一键拉起 PG/Redis/MinIO/Qdrant
	docker compose up -d

compose-down:       ## 停止依赖组件
	docker compose down
