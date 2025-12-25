from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from backend.models.schemas import UserResponse
from backend.services.UserService import UserService
from backend.controller.UserController.dto.LoginRequest import LoginRequest
from backend.controller.UserController.dto.RegisterRequest import RegisterRequest
from backend.controller.UserController.dto.LoginResponse import LoginResponse
from backend.controller.UserController.dto.UpdateProfileRequest import UpdateProfileRequest
from backend.controller.UserController.dto.ChangePasswordRequest import ChangePasswordRequest
from backend.utils.api_response import ApiResponse
from backend.database.database import get_db

user_router = APIRouter()
security = HTTPBearer()


def get_user_service(db: Session = Depends(get_db)) -> UserService:
    return UserService(db)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    user_service: UserService = Depends(get_user_service)
) -> UserResponse:
    """
    Dependency to get the current authenticated user from JWT token.
    """
    token = credentials.credentials
    user = user_service.validate_token(token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


@user_router.post("/login", response_model=ApiResponse[LoginResponse])
def login(
    request: LoginRequest, 
    user_service: UserService = Depends(get_user_service)
) -> ApiResponse[LoginResponse]:
    """
    Login endpoint - authenticates user and returns JWT token.
    
    Args:
        request: LoginRequest containing email and password
        user_service: UserService dependency injection
    
    Returns:
        ApiResponse containing LoginResponse with access token and user info
    """
    response = user_service.login(request)
    return ApiResponse(status=200, message="Login successful", data=response)


@user_router.post("/register", response_model=ApiResponse[LoginResponse])
def register(
    request: RegisterRequest, 
    user_service: UserService = Depends(get_user_service)
) -> ApiResponse[LoginResponse]:
    """
    Register endpoint - creates new user account.
    
    Args:
        request: RegisterRequest containing name, email, and password
        user_service: UserService dependency injection
    
    Returns:
        ApiResponse containing LoginResponse with access token and user info
    """
    response = user_service.register(request)
    return ApiResponse(status=201, message="User registered successfully", data=response)


@user_router.get("/profile", response_model=ApiResponse[UserResponse])
def get_profile(
    current_user: UserResponse = Depends(get_current_user)
) -> ApiResponse[UserResponse]:
    """
    Get current user's profile information.
    
    Args:
        current_user: Authenticated user from JWT token
    
    Returns:
        ApiResponse containing user profile data
    """
    return ApiResponse(status=200, message="Profile retrieved successfully", data=current_user)


@user_router.put("/profile", response_model=ApiResponse[UserResponse])
def update_profile(
    request: UpdateProfileRequest,
    current_user: UserResponse = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service)
) -> ApiResponse[UserResponse]:
    """
    Update current user's profile information.
    
    Args:
        request: UpdateProfileRequest containing optional name and email
        current_user: Authenticated user from JWT token
        user_service: UserService dependency injection
    
    Returns:
        ApiResponse containing updated user profile data
    """
    updated_user = user_service.update_profile(current_user.id, request)
    return ApiResponse(status=200, message="Profile updated successfully", data=updated_user)


@user_router.post("/change-password", response_model=ApiResponse[None])
def change_password(
    request: ChangePasswordRequest,
    current_user: UserResponse = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service)
) -> ApiResponse[None]:
    """
    Change current user's password.
    
    Args:
        request: ChangePasswordRequest containing current and new password
        current_user: Authenticated user from JWT token
        user_service: UserService dependency injection
    
    Returns:
        ApiResponse with success message
    """
    user_service.change_password(current_user.id, request)
    return ApiResponse(status=200, message="Password changed successfully", data=None)


@user_router.post("/logout", response_model=ApiResponse[None])
def logout(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    user_service: UserService = Depends(get_user_service)
) -> ApiResponse[None]:
    """
    Logout endpoint - invalidates the current JWT token.
    
    Args:
        credentials: Bearer token from Authorization header
        user_service: UserService dependency injection
    
    Returns:
        ApiResponse with success message
    """
    token = credentials.credentials
    user_service.invalidate_token(token)
    return ApiResponse(status=200, message="Logged out successfully", data=None)


@user_router.get("/validate-token", response_model=ApiResponse[UserResponse])
def validate_token(
    current_user: UserResponse = Depends(get_current_user)
) -> ApiResponse[UserResponse]:
    """
    Validate current JWT token and return user info.
    
    Args:
        current_user: Authenticated user from JWT token
    
    Returns:
        ApiResponse containing user data if token is valid
    """
    return ApiResponse(status=200, message="Token is valid", data=current_user)