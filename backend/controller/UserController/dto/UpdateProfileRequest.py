from pydantic import BaseModel, EmailStr
from typing import Optional


class UpdateProfileRequest(BaseModel):
    """
    Request model for updating user profile.
    All fields are optional - only provided fields will be updated.
    """
    name: Optional[str] = None
    email: Optional[EmailStr] = None

    class Config:
        json_schema_extra = {
            "example": {
                "name": "Ahmet Yılmaz",
                "email": "ahmet@example.com"
            }
        }