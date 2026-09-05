# ---------- 构建阶段 ----------
FROM python:3.11-slim AS builder

WORKDIR /build

# 先复制依赖清单，利用 Docker 层缓存
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt --prefix /install

# ---------- 运行阶段 ----------
FROM python:3.11-slim

# 非 root 运行（生产安全基线）
RUN useradd --create-home --uid 1000 appuser

WORKDIR /app

# 只复制已安装的依赖与源码，体积更小
COPY --from=builder /install /usr/local
COPY app/ ./app/
COPY web/ ./web/

USER appuser

EXPOSE 8000

# 生产环境：多 worker + 健康检查（阶段七部署伸缩）
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
