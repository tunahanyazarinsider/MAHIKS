from sqlalchemy.orm import Session
from backend.models.models import User
from backend.core.exceptions import NotFoundError, AppError, ConflictError
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

class UserRepository:
    def __init__(self, db: Session):
        self.db = db
    
    def get_by_email(self, email: str) -> User:
        print("Before getting user from db")
        item = self.db.query(User).filter(
            User.email == email
        ).first()

        if item is None:
            print("User not found")
            raise NotFoundError(message = "User not found", code = "USER_NOT_FOUND")

        print("After user found")
        return item

    def exists_by_email(self, email: str) -> bool:
        print("Before checking email in db")
        return self.db.query(User).filter(User.email == email).first() is not None

    def create_user(self, user: User) -> User:
        print("Before creating user in db")
        try:
            self.db.add(user)
            self.db.commit()
            self.db.refresh(user)
            print("After creating user in db")
            return user

        except IntegrityError:
            self.db.rollback()
            # email/username unique constraint violation
            raise ConflictError("User with same email or username already exists")

        except SQLAlchemyError:
            self.db.rollback()
            # DB ile ilgili genel bir arıza
            raise AppError("Database operation failed")