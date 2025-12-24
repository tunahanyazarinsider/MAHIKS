"""
API Response Helper for MAHIKS-TR
Standardized response format for all endpoints
"""
from typing import Any, Optional
from fastapi.responses import JSONResponse


def success_response(
    data: Any = None,
    message: str = "Success",
    status_code: int = 200
) -> JSONResponse:
    """
    Create a standardized success response.
    
    Args:
        data: Response data (can be dict, list, or any serializable type)
        message: Success message
        status_code: HTTP status code (default 200)
        
    Returns:
        JSONResponse with standardized format
    """
    return JSONResponse(
        status_code=status_code,
        content={
            "status": status_code,
            "message": message,
            "data": data
        }
    )


def error_response(
    message: str = "An error occurred",
    status_code: int = 400,
    error_code: Optional[str] = None,
    details: Optional[Any] = None
) -> JSONResponse:
    """
    Create a standardized error response.
    
    Args:
        message: Error message
        status_code: HTTP status code (default 400)
        error_code: Optional error code for client-side handling
        details: Optional additional error details
        
    Returns:
        JSONResponse with standardized error format
    """
    content = {
        "status": status_code,
        "message": message,
        "data": None
    }
    
    if error_code:
        content["data"] = {"errorCode": error_code}
    
    if details:
        if content["data"] is None:
            content["data"] = {}
        content["data"]["details"] = details
    
    return JSONResponse(
        status_code=status_code,
        content=content
    )