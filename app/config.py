"""应用配置（pydantic-settings）。

对应「docs/12-Python开发规范.md」6.1 节：全应用唯一配置入口，启动时读取 .env。
禁止在业务模块散落 os.getenv；新增配置项 = Settings 加字段 + .env.example 补一行。

用法：
    from app.dependencies import get_settings
    settings: Settings = Depends(get_settings)
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """从环境变量 / .env 读取的应用配置。"""

    # 应用基础
    app_name: str = "Python AI Agent 学习项目"
    app_version: str = "0.1.0"
    debug: bool = False

    # 模型 API（密钥只从 .env 读，不入库）
    openai_api_key: str = ""
    deepseek_api_key: str = ""
    tavily_api_key: str = ""

    # 远程服务器
    remote_host: str = "101.34.52.229"
    remote_user: str = "root"

    # PostgreSQL
    pg_host: str = "localhost"
    pg_port: int = 5432
    pg_db: str = "datapilot_app"
    pg_user: str = "datapilot"
    pg_password: str = ""

    @property
    def pg_dsn(self) -> str:
        """SQLAlchemy 异步连接串（app/storage/pg.py 使用）。"""
        return (
            f"postgresql+asyncpg://{self.pg_user}:{self.pg_password}"
            f"@{self.pg_host}:{self.pg_port}/{self.pg_db}"
        )

    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: str = ""
    redis_db: int = 0

    @property
    def redis_url(self) -> str:
        """Redis 连接串（redis.asyncio 使用）。"""
        auth = f":{self.redis_password}@" if self.redis_password else ""
        return f"redis://{auth}{self.redis_host}:{self.redis_port}/{self.redis_db}"

    # MinIO
    minio_endpoint: str = "http://localhost:9000"
    minio_access_key: str = ""
    minio_secret_key: str = ""
    minio_bucket: str = "datapilot"

    # Qdrant
    qdrant_url: str = "http://localhost:6333"

    # 服务行为
    cors_allow_origins: list[str] = ["*"]
    request_timeout: float = 30.0
    llm_retry_attempts: int = 3

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings_cached() -> Settings:
    """缓存单例 Settings（进程内只解析一次 .env）。"""
    return Settings()


settings = get_settings_cached()
