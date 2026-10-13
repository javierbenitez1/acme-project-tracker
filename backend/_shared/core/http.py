"""Small router plus request and response helpers used by every service."""
import base64
import json
import logging
import re
from datetime import date, datetime
from decimal import Decimal

import psycopg

from . import auth, db, schema
from .errors import ApiError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

FRIENDLY_CONSTRAINTS = {
    "users_username_key": ("username", "That username is already taken."),
    "users_email_key": ("email", "That email is already in use."),
    "teams_manager_id_name_key": ("name", "You already have a team with that name."),
}


def _json_default(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    raise TypeError(f"Cannot serialize {type(value).__name__}")


def respond(status, body=None):
    if status == 204 or body is None:
        return {"statusCode": status, "headers": {}, "body": ""}
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body, default=_json_default),
    }


def error_response(status, code, message, details=None):
    error = {"code": code, "message": message}
    if details:
        error["details"] = details
    return respond(status, {"error": error})


class Request:
    def __init__(self, event):
        http = (event.get("requestContext") or {}).get("http") or {}
        self.method = (http.get("method") or event.get("httpMethod") or "GET").upper()
        self.headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
        self.query = event.get("queryStringParameters") or {}
        self.params = {}
        self.path = ""
        self.user = None
        raw = event.get("body")
        if raw and event.get("isBase64Encoded"):
            try:
                raw = base64.b64decode(raw).decode("utf-8")
            except Exception:
                raw = None
        self._raw_body = raw

    def json(self):
        if not self._raw_body:
            return {}
        try:
            data = json.loads(self._raw_body)
        except (ValueError, TypeError):
            raise ApiError(400, "MALFORMED_JSON", "Request body must be valid JSON.")
        if not isinstance(data, dict):
            raise ApiError(400, "MALFORMED_JSON", "Request body must be a JSON object.")
        return data


class Router:
    def __init__(self, service):
        self.service = service
        self._routes = []

    def route(self, method, pattern, auth=True, roles=None):
        """Register a handler. {name} in the pattern matches a numeric id."""
        regex = re.compile("^" + re.sub(r"\{(\w+)\}", r"(?P<\1>\\d+)", pattern) + "$")

        def decorator(fn):
            self._routes.append((method.upper(), regex, fn, auth, set(roles) if roles else None))
            return fn

        return decorator

    def _normalize(self, raw_path):
        # AWS (through CloudFront) sends /api/<service>/x, local proxy sends /x
        parts = [p for p in (raw_path or "").split("/") if p]
        if parts[:2] == ["api", self.service]:
            parts = parts[2:]
        return "".join("/" + p for p in parts)

    def _dispatch(self, req):
        schema.ensure_schema()
        allowed = []
        for method, regex, fn, needs_auth, roles in self._routes:
            match = regex.match(req.path)
            if not match:
                continue
            if method != req.method:
                allowed.append(method)
                continue
            req.params = {k: int(v) for k, v in match.groupdict().items()}
            if needs_auth:
                req.user = auth.authenticate(req)
                if roles and req.user["role"] not in roles:
                    raise ApiError(403, "FORBIDDEN", "You do not have permission to perform this action.")
            result = fn(req)
            status, body = result if isinstance(result, tuple) else (200, result)
            return respond(status, body)
        if allowed:
            raise ApiError(405, "METHOD_NOT_ALLOWED",
                           f"{req.method} is not allowed here. Allowed: {', '.join(sorted(set(allowed)))}.")
        raise ApiError(404, "ROUTE_NOT_FOUND", f"No route for {req.method} {req.path or '/'}.")

    def handle(self, event, context=None):
        req = Request(event)
        req.path = self._normalize(event.get("rawPath") or event.get("path"))
        if req.method == "OPTIONS":
            return respond(204)
        for attempt in (1, 2):
            try:
                return self._dispatch(req)
            except ApiError as e:
                return error_response(e.status, e.code, e.message, e.details)
            except psycopg.OperationalError as e:
                logger.warning("Database connection problem (attempt %s): %s", attempt, e)
                db.reset()
                if attempt == 2:
                    return error_response(503, "DATABASE_UNAVAILABLE",
                                          "The database is waking up. Please try again in a few seconds.")
            except psycopg.errors.UniqueViolation as e:
                field, msg = FRIENDLY_CONSTRAINTS.get(e.diag.constraint_name,
                                                      (None, "A record with these values already exists."))
                return error_response(409, "DUPLICATE", msg, {field: msg} if field else None)
            except psycopg.errors.ForeignKeyViolation:
                return error_response(400, "INVALID_REFERENCE", "A referenced record does not exist.")
            except psycopg.errors.CheckViolation:
                return error_response(400, "VALIDATION_ERROR", "One or more values are out of the allowed range.")
            except Exception:
                logger.exception("Unhandled error in %s %s", req.method, req.path)
                return error_response(500, "INTERNAL_ERROR", "Something went wrong on our side. Please try again.")
