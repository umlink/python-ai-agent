"""统一响应封装 ApiResponse 与业务状态码 BizCode 单测。"""

from app.schemas import ApiResponse, BizCode


def test_biz_code_values():
    """业务状态码应有明确的 code 与描述。"""
    assert BizCode.SUCCESS.value == 0
    assert BizCode.SUCCESS.message == "成功"
    assert BizCode.PARAM_ERROR.value == 40001
    assert BizCode.TOOL_FAILED.value == 50201
    assert BizCode.INTERNAL_ERROR.value == 50000


def test_api_response_ok():
    """ok() 应构造 code=0 的成功响应并携带 data。"""
    resp = ApiResponse.ok({"a": 1})
    assert resp.code == 0
    assert resp.message == "成功"
    assert resp.data == {"a": 1}


def test_api_response_fail():
    """fail() 应构造业务错误响应，data 为 None。"""
    resp = ApiResponse.fail(BizCode.NOT_FOUND, trace_id="t1")
    assert resp.code == BizCode.NOT_FOUND.value
    assert resp.message == BizCode.NOT_FOUND.message
    assert resp.data is None
    assert resp.trace_id == "t1"


def test_api_response_fail_custom_message():
    """fail() 支持覆盖默认描述。"""
    resp = ApiResponse.fail(BizCode.NOT_FOUND, message="未找到该知识条目")
    assert resp.message == "未找到该知识条目"


def test_api_response_serialization_shape():
    """序列化后应呈 {code, message, data, trace_id} 结构。"""
    body = ApiResponse.ok({"k": "v"}, trace_id="abc").model_dump()
    assert set(body.keys()) == {"code", "message", "data", "trace_id"}
    assert body["code"] == 0
