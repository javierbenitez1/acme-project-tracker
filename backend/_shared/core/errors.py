"""One error type so every service returns the same error format."""


class ApiError(Exception):
    def __init__(self, status, code, message, details=None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.details = details


def bad_request(message, details=None, code="VALIDATION_ERROR"):
    return ApiError(400, code, message, details)


def unauthorized(message, code="UNAUTHORIZED"):
    return ApiError(401, code, message)


def forbidden(message="You do not have permission to perform this action."):
    return ApiError(403, "FORBIDDEN", message)


def not_found(entity="Resource"):
    return ApiError(404, "NOT_FOUND", f"{entity} not found.")


def conflict(message, details=None):
    return ApiError(409, "CONFLICT", message, details)
