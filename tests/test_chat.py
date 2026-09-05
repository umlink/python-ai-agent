"""Agent 对话接口单测。"""


def test_chat_ok(client):
    """POST /agent/chat 应返回骨架回答。"""
    resp = client.post("/agent/chat", json={"question": "你好"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["source"] == "skeleton"
    assert "你好" in body["answer"]


def test_chat_with_session(client):
    """携带 session_id 的多轮会话应正常处理。"""
    resp = client.post(
        "/agent/chat",
        json={"question": "测试会话", "session_id": "sess-001"},
    )
    assert resp.status_code == 200


def test_chat_empty_question_422(client):
    """空问题应被 Pydantic 校验拒绝（422）。"""
    resp = client.post("/agent/chat", json={"question": ""})
    assert resp.status_code == 422


def test_chat_missing_field_422(client):
    """缺少 question 字段应返回 422。"""
    resp = client.post("/agent/chat", json={})
    assert resp.status_code == 422


def test_chat_too_long_422(client):
    """超长问题应被校验拒绝（max_length=2000）。"""
    resp = client.post("/agent/chat", json={"question": "x" * 2001})
    assert resp.status_code == 422
