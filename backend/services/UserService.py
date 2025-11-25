from backend.utils.hash import verify_password, hash_password
from backend.repository.UserRepository import UserRepository
from sqlalchemy.orm import Session
from backend.models.models import User
from backend.core.exceptions import ValidationError
from backend.controller.UserController.dto.RegisterRequest import RegisterRequest
from backend.controller.UserController.dto.LoginRequest import LoginRequest
from backend.controller.UserController.dto.LoginResponse import LoginResponse
from backend.core.security import create_access_token
from backend.models.schemas import UserResponse

class UserService:
    def __init__(self, db: Session):
        self.user_repository = UserRepository(db)
    
    def login(self, request: LoginRequest) -> LoginResponse:
        user = self.user_repository.get_by_email(request.email)
        if (user is None):
            raise ValidationError("User not found", code="USER_NOT_FOUND"   )
        if (not verify_password(request.password, user.password)):
            raise ValidationError("Invalid credentials", code="INVALID_CREDENTIALS")

        claims = {
            "email": user.email
        }
        print(user)
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
        Service function for user registration

        Checks if user exists by email
        Creates user and stores it in database

        args:
            request: RegisterRequest -> taken from frontend

        returns:
            LoginResponse
        """
        if (self.user_repository.exists_by_email(request.email)):
            raise ValidationError("User with same email already exists", code="USER_ALREADY_EXISTS")
        

        user = User(
            display_name=request.name,
            email=request.email,
            password=hash_password(request.password)
        )

        self.user_repository.create_user(user)

        claims = {
            "email": request.email
        }
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