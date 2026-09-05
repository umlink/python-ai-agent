"""异常处理器与追踪链路单测。

覆盖三类错误路径与 trace_id 一致性：
  1. 参数校验错误（422）     → 统一 ApiResponse，code=40001
  2. 未捕获异常/业务异常      → 统一 ApiResponse
  3. trace_id 生成与回传     → 正常/异常链路同源
"""


def _assert_unified(body: dict, code: int):
    """断言 body 为统一 ApiResponse 结构。"""
    assert set(body.keys()) == {"code", "message", "data", "trace_id"}
    assert body["code"] == code
    assert body["data"] is None


def test_validation_error_unified(client):
    """参数校验错误应统一为 {code, message, data, trace_id}。"""
    resp = client.post("/agent/chat", json={"question": ""})
    assert resp.status_code == 422
    _assert_unified(resp.json(), 40001)
    assert "参数校验失败" in resp.json()["message"]


def test_error_trace_id_generated(client):
    """异常链路：未传 x-request-id 时应自动生成，并与响应头一致。"""
    resp = client.post("/agent/chat", json={"question": ""})
    assert resp.status_code == 422
    tid = resp.headers["X-Request-ID"]
    assert tid
    assert resp.json()["trace_id"] == tid


def test_error_trace_id_echoes_upstream(client):
    """异常链路：上游 x-request-id 应同源回传。"""
    resp = client.post("/agent/chat", json={"question": ""}, headers={"x-request-id": "req-abc"})
    assert resp.status_code == 422
    assert resp.json()["trace_id"] == "req-abc"
    assert resp.headers["X-Request-ID"] == "req-abc"


def test_normal_trace_id_echoes_upstream(client):
    """正常链路：上游 x-request-id 应原样回传。"""
    resp = client.post("/agent/chat", json={"question": "hi"}, headers={"x-request-id": "req-123"})
    assert resp.status_code == 200
    assert resp.json()["trace_id"] == "req-123"
    assert resp.headers["X-Request-ID"] == "req-123"
