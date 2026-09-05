"""配置模块单测：pydantic-settings 读取与连接串生成。"""

from app.config import Settings


def test_settings_read_env(monkeypatch):
    """应从环境变量读取配置。"""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    s = Settings(_env_file=None)
    assert s.openai_api_key == "sk-test"


def test_settings_defaults():
    """未提供环境变量时应回落默认值（禁用 .env 避免被本机配置污染）。"""
    s = Settings(_env_file=None)
    assert s.app_name == "Python AI Agent 学习项目"
    assert s.request_timeout == 30.0


def test_pg_dsn_builds_correctly():
    """pg_dsn 应生成带异步驱动的连接串。"""
    s = Settings(
        _env_file=None,
        pg_host="db.example.com",
        pg_port=5433,
        pg_db="mydb",
        pg_user="myuser",
        pg_password="secret",
    )
    assert s.pg_dsn == "postgresql+asyncpg://myuser:secret@db.example.com:5433/mydb"


def test_redis_url_with_and_without_password():
    """redis_url 应正确处理有无密码两种情况。"""
    s = Settings(_env_file=None, redis_host="r.example.com", redis_port=6379, redis_db=1)
    assert s.redis_url == "redis://r.example.com:6379/1"

    s2 = Settings(
        _env_file=None,
        redis_host="r.example.com",
        redis_port=6379,
        redis_password="p@ss",
        redis_db=0,
    )
    assert s2.redis_url == "redis://:p@ss@r.example.com:6379/0"
