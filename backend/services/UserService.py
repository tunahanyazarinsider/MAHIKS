from backend.utils.hash import verify_password, hash_password
from backend.repository.UserRepository import UserRepository
from sqlalchemy.orm import Session
from backend.models.models import User
from backend.core.exceptions import ValidationError
from backend.controller.UserController.dto.RegisterRequest import RegisterRequest
from backend.controller.UserController.dto.LoginRequest import LoginRequest

class UserService:
    def __init__(self, db: Session):
        self.user_repository = UserRepository(db)
    
    def login(self, request: LoginRequest) -> User:
        print("in service")
        user = self.user_repository.get_by_email(request.email)
        print("Before password check")
        if (not verify_password(request.password, user.password)):
            print("Invalid credentials")
            raise ValidationError("Invalid credentials", code="INVALID_CREDENTIALS")
        print("After password check")

        return user

    def register(self, request: RegisterRequest) -> User:
        """
        Service function for user registration

        Checks if user exists by email
        Creates user and stores it in database

        args:
            request: RegisterRequest -> taken from frontend

        returns:
            User
        """
        if (self.user_repository.exists_by_email(request.email)):
            raise ValidationError("User with same email already exists", code="USER_ALREADY_EXISTS")
        user = User(
            display_name=request.name,
            email=request.email,
            password=hash_password(request.password)
        )

        return self.user_repository.create_user(user)