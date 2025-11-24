from backend.models.schemas import UserResponse
from backend.services.UserService import UserService
from fastapi import APIRouter
from backend.controller.UserController.dto.LoginRequest import LoginRequest
from backend.controller.UserController.dto.RegisterRequest import RegisterRequest
from backend.utils.api_response import ApiResponse
from backend.database.database import get_db
from sqlalchemy.orm import Session
from fastapi import Depends
from backend.controller.UserController.dto.LoginResponse import LoginResponse

user_router = APIRouter()
def get_user_service(db: Session = Depends(get_db)) -> UserService:
    return UserService(db)

@user_router.post("/login", response_model=ApiResponse[LoginResponse])
def login(request: LoginRequest, user_service: UserService = Depends(get_user_service)) -> ApiResponse[LoginResponse]:
    """
    Login endpoint

    args:
        request: LoginRequest -> taken from frontend
        user_service: UserService -> dependency injection

    returns:
        ApiResponse[LoginResponse]
    """
    response = user_service.login(request)
    return ApiResponse(status=200, message="Login successful", data=response)

@user_router.post("/register", response_model=ApiResponse[LoginResponse])
def register(request: RegisterRequest, user_service: UserService = Depends(get_user_service)) -> ApiResponse[LoginResponse]:
    """
    Register endpoint

    args:
        request: RegisterRequest -> taken from frontend
        user_service: UserService -> dependency injection

    returns:
        ApiResponse[LoginResponse]
    """
    response = user_service.register(request)
    return ApiResponse(status=201, message="User registered successfully", data=response)