"""Unit tests for backend/core/api_response.py"""
import pytest
from backend.core.api_response import success_response, error_response


@pytest.mark.unit
def test_success_response_status_code():
    resp = success_response(data={"key": "value"})
    assert resp.status_code == 200


@pytest.mark.unit
def test_success_response_body_structure():
    resp = success_response(data={"key": "value"}, message="OK")
    import json
    body = json.loads(resp.body)
    assert body["status"] == 200
    assert body["message"] == "OK"
    assert body["data"] == {"key": "value"}


@pytest.mark.unit
def test_success_response_custom_status():
    resp = success_response(data=None, status_code=201)
    assert resp.status_code == 201
    import json
    body = json.loads(resp.body)
    assert body["status"] == 201


@pytest.mark.unit
def test_success_response_no_data():
    resp = success_response()
    import json
    body = json.loads(resp.body)
    assert body["data"] is None


@pytest.mark.unit
def test_error_response_status_code():
    resp = error_response(message="Bad request", status_code=400)
    assert resp.status_code == 400


@pytest.mark.unit
def test_error_response_body_structure():
    resp = error_response(message="Not found", status_code=404)
    import json
    body = json.loads(resp.body)
    assert body["status"] == 404
    assert body["message"] == "Not found"


@pytest.mark.unit
def test_error_response_with_error_code():
    resp = error_response(message="err", error_code="USER_NOT_FOUND")
    import json
    body = json.loads(resp.body)
    assert body["data"]["errorCode"] == "USER_NOT_FOUND"


@pytest.mark.unit
def test_error_response_with_details():
    resp = error_response(message="err", details={"field": "email"})
    import json
    body = json.loads(resp.body)
    assert body["data"]["details"] == {"field": "email"}


@pytest.mark.unit
def test_error_response_no_data_when_no_extras():
    resp = error_response(message="generic error")
    import json
    body = json.loads(resp.body)
    assert body["data"] is None
