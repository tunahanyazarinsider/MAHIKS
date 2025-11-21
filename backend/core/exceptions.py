# app/core/exceptions.py

class AppError(Exception):
    """Base application exception with optional error code."""

    def __init__(self, message: str, code: str = None):
        super().__init__(message)
        self.message = message
        self.code = code


class NotFoundError(AppError):
    """Entity not found."""

    def __init__(self, message="Not Found", code="NOT_FOUND"):
        super().__init__(message, code)


class ConflictError(AppError):
    """Business rule conflict."""

    def __init__(self, message="Conflict", code="CONFLICT"):
        super().__init__(message, code)


class ValidationError(AppError):
    """Domain-level validation error."""

    def __init__(self, message="Validation error", code="VALIDATION_ERROR"):
        super().__init__(message, code)

