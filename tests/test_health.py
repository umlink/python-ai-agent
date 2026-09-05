"""健康检查接口单测。"""


def test_health_ok(client):
    """GET /health 应返回服务状态。"""
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["service"] == "python-ai-agent-learning"


def test_health_has_system_tag():
    """health 路由应带 system tag（规范 4.1）。"""
    from app.main import create_app

    app = create_app()
    # 遍历 OpenAPI 确认 tags 分组
    schema = app.openapi()
    ops = [
        op
        for path in schema["paths"].values()
        for op in path.values()
        if op.get("operationId") == "health_health_get"
    ]
    assert ops and "system" in ops[0].get("tags", [])
