"""pytest 共享夹具。

提供 TestClient（FastAPI 官方推荐的 httpx 测试客户端）与全局配置隔离。
"""

import pytest
from app.main import create_app
from fastapi.testclient import TestClient


@pytest.fixture()
def client() -> TestClient:
    """返回独立的应用实例测试客户端（每用例新建，避免状态污染）。"""
    app = create_app()
    with TestClient(app) as c:
        yield c
