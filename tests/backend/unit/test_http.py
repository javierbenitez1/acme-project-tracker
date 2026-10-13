"""Unit tests for the shared router: path handling, status codes, role checks, and error format."""
import base64
import json
from datetime import date
from decimal import Decimal

import pytest

from core import http


@pytest.fixture(autouse=True)
def no_database(monkeypatch):
    monkeypatch.setattr(http.schema, "ensure_schema", lambda: None)
    monkeypatch.setattr(http.auth, "authenticate",
                        lambda req: {"id": 1, "name": "Tester", "role": req.headers.get("x-test-role", "employee")})


def make_router():
    router = http.Router("things")

    @router.route("GET", "", auth=False)
    def list_things(req):
        return {"query": req.query}

    @router.route("GET", "/{id}")
    def get_thing(req):
        return {"id": req.params["id"], "user": req.user["name"]}

    @router.route("POST", "", roles=["admin"])
    def create_thing(req):
        return 201, req.json()

    @router.route("DELETE", "/{id}", roles=["admin"])
    def delete_thing(req):
        return 204, None

    @router.route("GET", "/boom", auth=False)
    def boom(req):
        raise RuntimeError("secret internals")

    return router


def call(method, path, body=None, role=None, base64_body=False):
    event = {"rawPath": path, "requestContext": {"http": {"method": method}},
             "headers": {"X-Test-Role": role} if role else {}, "body": body}
    if base64_body:
        event["body"] = base64.b64encode(body.encode()).decode()
        event["isBase64Encoded"] = True
    response = make_router().handle(event)
    return response["statusCode"], (json.loads(response["body"]) if response["body"] else None)


@pytest.mark.parametrize("path", ["", "/", "/api/things", "/api/things/", "//"])
def test_local_and_cloudfront_paths_reach_the_same_route(path):
    assert call("GET", path)[0] == 200


def test_path_ids_become_integers():
    assert call("GET", "/api/things/42")[1] == {"id": 42, "user": "Tester"}


def test_unknown_route_returns_404():
    status, body = call("GET", "/api/things/42/extra")
    assert status == 404 and body["error"]["code"] == "ROUTE_NOT_FOUND"


def test_non_numeric_id_returns_404():
    assert call("GET", "/api/things/abc")[0] == 404


def test_wrong_method_returns_405_with_allowed_methods():
    status, body = call("PUT", "/api/things/5")
    assert status == 405 and "GET" in body["error"]["message"]


def test_role_check_returns_403():
    status, body = call("POST", "/api/things", body='{"a": 1}')
    assert status == 403 and body["error"]["code"] == "FORBIDDEN"


def test_allowed_role_can_create_with_201():
    assert call("POST", "/api/things", body='{"a": 1}', role="admin") == (201, {"a": 1})


def test_delete_returns_204_with_empty_body():
    assert call("DELETE", "/api/things/3", role="admin") == (204, None)


def test_malformed_json_returns_400():
    status, body = call("POST", "/api/things", body="{not json", role="admin")
    assert status == 400 and body["error"]["code"] == "MALFORMED_JSON"


def test_json_array_body_returns_400():
    assert call("POST", "/api/things", body="[1, 2]", role="admin")[0] == 400


def test_base64_encoded_body_is_decoded():
    assert call("POST", "/api/things", body='{"a": 2}', role="admin", base64_body=True) == (201, {"a": 2})


def test_options_preflight_returns_204():
    assert call("OPTIONS", "/api/things")[0] == 204


def test_unexpected_errors_return_500_without_leaking_details():
    status, body = call("GET", "/api/things/boom")
    assert status == 500 and body["error"]["code"] == "INTERNAL_ERROR"
    assert "secret internals" not in json.dumps(body)


def test_dates_and_decimals_serialize_to_json():
    response = http.respond(200, {"day": date(2026, 1, 2), "amount": Decimal("1.50")})
    assert json.loads(response["body"]) == {"day": "2026-01-02", "amount": 1.5}
