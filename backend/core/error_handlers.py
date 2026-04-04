from fastapi import Request, status
from fastapi.responses import JSONResponse

from .exceptions import (
    AppError,
    NotFoundError,
    ConflictError,
    ValidationError
)
from backend.utils.api_response import ApiResponse


def register_exception_handlers(app):
    """
    Registers exception handlers for the application
    Different exception handlers are registered for different types of exceptions

    args:
        app: FastAPI -> application to register exception handlers for
    """

    @app.exception_handler(NotFoundError)
    async def not_found_handler(request: Request, exc: NotFoundError) -> JSONResponse:
        return JSONResponse(    
            status_code=status.HTTP_404_NOT_FOUND,
            content=ApiResponse(
                status=404,
                message=exc.message,
                data={"errorCode": exc.code}
            ).dict()
        )

    @app.exception_handler(ValidationError)
    async def validation_handler(request: Request, exc: ValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=ApiResponse(
                status=400,
                message=exc.message,
                data={"errorCode": exc.code}
            ).dict()
        )

    @app.exception_handler(ConflictError)
    async def conflict_handler(request: Request, exc: ConflictError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=ApiResponse(
                status=409,
                message=exc.message,
                data={"errorCode": exc.code}
            ).dict()
        )

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ApiResponse(
                status=500,
                message="Internal application error",
                data={"errorCode": exc.code}
            ).dict()
        )
