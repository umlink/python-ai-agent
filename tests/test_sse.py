"""SSE 流式协议单测（app/schemas/sse.py + POST /agent/chat/stream）。"""

import json

from app.schemas import SSEDeltaPayload, SSEEventType, format_sse


def _parse_sse_frames(text: str) -> list[dict]:
    """把原始 SSE 文本按空行切分成 [{"event": ..., "data": ...}] 帧列表。"""
    frames = []
    for block in text.split("\n\n"):
        block = block.strip()
        if not block:
            continue
        event = ""
        data = ""
        for line in block.splitlines():
            if line.startswith("event:"):
                event = line[len("event:") :].strip()
            elif line.startswith("data:"):
                data = line[len("data:") :].strip()
        frames.append({"event": event, "data": data})
    return frames


def test_format_sse_payload_model():
    """Pydantic 负载应序列化为 event + data 两行 + 空行结尾的帧。"""
    frame = format_sse(SSEEventType.DELTA, SSEDeltaPayload(content="你"))
    assert frame == 'event: delta\ndata: {"content":"你"}\n\n'


def test_format_sse_no_data():
    """无负载（如 ping）应输出空对象 data。"""
    frame = format_sse(SSEEventType.PING)
    assert frame == "event: ping\ndata: {}\n\n"


def test_format_sse_dict():
    """dict 负载应走 JSON 序列化（ensure_ascii=False）。"""
    frame = format_sse(SSEEventType.ERROR, {"code": 50000, "message": "boom"})
    assert frame.startswith("event: error\ndata: ")
    payload = json.loads(frame.split("\n", 1)[1][len("data: ") :])
    assert payload == {"code": 50000, "message": "boom"}


def test_chat_stream_frames_order(client):
    """流式响应应固定 meta -> message_start -> delta* -> done 的事件顺序。"""
    resp = client.post("/agent/chat/stream", json={"question": "你好"})
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    events = [f["event"] for f in _parse_sse_frames(resp.text)]
    assert events[0] == "meta"
    assert events[1] == "message_start"
    assert all(e == "delta" for e in events[2:-1])
    assert events[-1] == "done"


def test_chat_stream_meta_payload(client):
    """meta 帧应携带会话 ID 与追踪 ID。"""
    resp = client.post(
        "/agent/chat/stream",
        json={"question": "你好", "session_id": "sess-001"},
    )
    meta = json.loads(_parse_sse_frames(resp.text)[0]["data"])
    assert meta["session_id"] == "sess-001"
    assert isinstance(meta["trace_id"], str) and meta["trace_id"]


def test_chat_stream_delta_joins_to_answer(client):
    """所有 delta 块拼接后应等于完整回答（逐块切片不应丢字）。"""
    resp = client.post("/agent/chat/stream", json={"question": "你好"})
    deltas = [
        json.loads(f["data"])["content"]
        for f in _parse_sse_frames(resp.text)
        if f["event"] == "delta"
    ]
    assert "".join(deltas) == (
        "收到问题：「你好」。这里是 Agent 服务骨架，接入编排层后返回真实回答。"
    )


def test_chat_stream_done_payload(client):
    """done 帧应携带结束原因。"""
    resp = client.post("/agent/chat/stream", json={"question": "你好"})
    done = json.loads(_parse_sse_frames(resp.text)[-1]["data"])
    assert done["finish_reason"] == "stop"


def test_chat_stream_empty_question_422(client):
    """空问题应被 Pydantic 校验拒绝（422）。"""
    resp = client.post("/agent/chat/stream", json={"question": ""})
    assert resp.status_code == 422
