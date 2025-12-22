from typing import Optional, Set
from sqlalchemy.orm import Session

from backend.utils.hash import verify_password, hash_password
from backend.repository.UserRepository import UserRepository
from backend.models.models import User
from backend.core.exceptions import ValidationError
from backend.controller.UserController.dto.RegisterRequest import RegisterRequest
from backend.controller.UserController.dto.LoginRequest import LoginRequest
from backend.controller.UserController.dto.LoginResponse import LoginResponse
from backend.controller.UserController.dto.UpdateProfileRequest import UpdateProfileRequest
from backend.controller.UserController.dto.ChangePasswordRequest import ChangePasswordRequest
from backend.core.security import create_access_token, decode_access_token
from backend.models.schemas import UserResponse


class UserService:
    # In-memory token blacklist (for production, use Redis or database)
    _blacklisted_tokens: Set[str] = set()

    def __init__(self, db: Session):
        self.user_repository = UserRepository(db)
    
    def login(self, request: LoginRequest) -> LoginResponse:
        """
        Authenticate user and return access token.
        
        Args:
            request: LoginRequest containing email and password
            
        Returns:
            LoginResponse with access token and user info
            
        Raises:
            ValidationError: If user not found or invalid credentials
        """
        user = self.user_repository.get_by_email(request.email)
        if user is None:
            raise ValidationError("Invalid credentials", code="INVALID_CREDENTIALS")
        if not verify_password(request.password, user.password):
            raise ValidationError("Invalid credentials", code="INVALID_CREDENTIALS")

        claims = {"email": user.email}
        user_response = UserResponse(
            id=user.id,
            display_name=user.display_name,
            email=user.email,
            status="active"
        )
        access_token = create_access_token(str(user.id), claims)
        
        return LoginResponse(
            access_token=access_token,
            token_type="bearer",
            user=user_response
        )

    def register(self, request: RegisterRequest) -> LoginResponse:
        """
        Register new user and return access token.
        
        Args:
            request: RegisterRequest containing name, email, and password
            
        Returns:
            LoginResponse with access token and user info
            
        Raises:
            ValidationError: If email already exists
        """
        if self.user_repository.exists_by_email(request.email):
            raise ValidationError("Email already registered", code="USER_ALREADY_EXISTS")
        
        user = User(
            display_name=request.name,
            email=request.email,
            password=hash_password(request.password)
        )

        self.user_repository.create_user(user)

        claims = {"email": request.email}
        access_token = create_access_token(str(user.id), claims)

        user_response = UserResponse(
            id=user.id,
            display_name=user.display_name,
            email=user.email,
            status="active"
        )
        
        return LoginResponse(
            access_token=access_token,
            token_type="bearer",
            user=user_response
        )

    def validate_token(self, token: str) -> Optional[UserResponse]:
        """
        Validate JWT token and return user if valid.
        
        Args:
            token: JWT access token
            
        Returns:
            UserResponse if token is valid, None otherwise
        """
        # Check if token is blacklisted
        if token in self._blacklisted_tokens:
            return None
        
        try:
            payload = decode_access_token(token)
            if payload is None:
                return None
            
            user_id = payload.get("sub")
            if user_id is None:
                return None
            
            user = self.user_repository.get_by_id(int(user_id))
            if user is None:
                return None
            
            return UserResponse(
                id=user.id,
                display_name=user.display_name,
                email=user.email,
                status="active"
            )
        except Exception:
            return None

    def invalidate_token(self, token: str) -> None:
        """
        Invalidate (blacklist) a JWT token for logout.
        
        Args:
            token: JWT access token to invalidate
        """
        self._blacklisted_tokens.add(token)

    def update_profile(self, user_id: int, request: UpdateProfileRequest) -> UserResponse:
        """
        Update user profile information.
        
        Args:
            user_id: ID of the user to update
            request: UpdateProfileRequest with optional name and email
            
        Returns:
            Updated UserResponse
            
        Raises:
            ValidationError: If user not found or email already taken
        """
        user = self.user_repository.get_by_id(user_id)
        if user is None:
            raise ValidationError("User not found", code="USER_NOT_FOUND")
        
        # Check if email is being changed and if it's already taken
        if request.email and request.email != user.email:
            if self.user_repository.exists_by_email(request.email):
                raise ValidationError("Email already registered", code="EMAIL_ALREADY_EXISTS")
            user.email = request.email
        
        if request.name:
            user.display_name = request.name
        
        self.user_repository.update_user(user)
        
        return UserResponse(
            id=user.id,
            display_name=user.display_name,
            email=user.email,
            status="active"
        )

    def change_password(self, user_id: int, request: ChangePasswordRequest) -> None:
        """
        Change user's password.
        
        Args:
            user_id: ID of the user
            request: ChangePasswordRequest with current and new password
            
        Raises:
            ValidationError: If user not found or current password is incorrect
        """
        user = self.user_repository.get_by_id(user_id)
        if user is None:
            raise ValidationError("User not found", code="USER_NOT_FOUND")
        
        if not verify_password(request.current_password, user.password):
            raise ValidationError("Current password is incorrect", code="INVALID_PASSWORD")
        
        user.password = hash_password(request.new_password)
        self.user_repository.update_user(user)

    def get_user_by_id(self, user_id: int) -> Optional[UserResponse]:
        """
        Get user by ID.
        
        Args:
            user_id: User ID
            
        Returns:
            UserResponse if found, None otherwise
        """
        user = self.user_repository.get_by_id(user_id)
        if user is None:
            return None
        
        return UserResponse(
            id=user.id,
            display_name=user.display_name,
            email=user.email,
            status="active"
        )