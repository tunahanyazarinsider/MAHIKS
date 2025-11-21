from backend.models.schemas import UserResponse
from backend.services.UserService import UserService
from fastapi import APIRouter
from backend.controller.UserController.dto.LoginRequest import LoginRequest
from backend.controller.UserController.dto.RegisterRequest import RegisterRequest
from backend.utils.api_response import ApiResponse
from backend.database.database import get_db
from backend.models.models import User
from sqlalchemy.orm import Session
from fastapi import Depends

user_router = APIRouter()
def get_user_service(db: Session = Depends(get_db)) -> UserService:
    return UserService(db)

@user_router.post("/login", response_model=ApiResponse[UserResponse])
def login(request: LoginRequest, user_service: UserService = Depends(get_user_service)) -> ApiResponse[UserResponse]:
    print("in controller")
    user = user_service.login(request)
    print("After login")
    return ApiResponse(status=200, message="Login successful", data=user)

@user_router.post("/register", response_model=ApiResponse[UserResponse])
def register(request: RegisterRequest, user_service: UserService = Depends(get_user_service)) -> ApiResponse[UserResponse]:
    print("In Controller")
    user = user_service.register(request)
    return ApiResponse(status=201, message="User registered successfully", data=user)