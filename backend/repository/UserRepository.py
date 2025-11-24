from sqlalchemy.orm import Session
from backend.models.models import User
from backend.core.exceptions import NotFoundError, AppError, ConflictError
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

class UserRepository:
    def __init__(self, db: Session):
        self.db = db
    
    def get_by_email(self, email: str) -> User:
        item = self.db.query(User).filter(
            User.email == email
        ).first()
        if item is None:
            raise NotFoundError(message = "User not found", code = "USER_NOT_FOUND")

        return item

    def exists_by_email(self, email: str) -> bool:
        """
        Checks if a user exists by email

        args:
            email: str -> email to check

        returns:
            bool -> True if user exists, False otherwise
        """
        return self.db.query(User).filter(User.email == email).first() is not None

    def create_user(self, user: User) -> User:
        """
        Creates a new user in the database

        args:
            user: User -> user to create

        returns:
            User -> created user
        """
        try:
            self.db.add(user)
            self.db.commit()
            self.db.refresh(user)
            return user

        except IntegrityError:
            self.db.rollback()
            # email/username unique constraint violation
            raise ConflictError("User with same email or username already exists")

        except SQLAlchemyError:
            self.db.rollback()
            # DB ile ilgili genel bir arıza
            raise AppError("Database operation failed")