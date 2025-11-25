from typing import Generic, TypeVar, Optional
from pydantic import BaseModel

T = TypeVar("T")

class ApiResponse(BaseModel, Generic[T]):
    status: int
    message: str
    data: Optional[T] = None