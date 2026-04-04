from pydantic import BaseModel
from backend.models.schemas import UserResponse

class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse
