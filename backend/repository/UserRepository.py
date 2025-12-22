from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from backend.models.models import User
from backend.core.exceptions import NotFoundError, AppError, ConflictError


class UserRepository:
    def __init__(self, db: Session):
        self.db = db
    
    def get_by_id(self, user_id: int) -> Optional[User]:
        """
        Get user by ID.
        
        Args:
            user_id: User ID to search for
            
        Returns:
            User if found, None otherwise
        """
        return self.db.query(User).filter(User.id == user_id).first()

    def get_by_email(self, email: str) -> Optional[User]:
        """
        Get user by email.
        
        Args:
            email: Email to search for
            
        Returns:
            User if found, None otherwise
        """
        return self.db.query(User).filter(User.email == email).first()

    def get_by_email_or_raise(self, email: str) -> User:
        """
        Get user by email or raise NotFoundError.
        
        Args:
            email: Email to search for
            
        Returns:
            User if found
            
        Raises:
            NotFoundError: If user not found
        """
        user = self.get_by_email(email)
        if user is None:
            raise NotFoundError(message="User not found", code="USER_NOT_FOUND")
        return user

    def exists_by_email(self, email: str) -> bool:
        """
        Check if a user exists by email.
        
        Args:
            email: Email to check
            
        Returns:
            True if user exists, False otherwise
        """
        return self.db.query(User).filter(User.email == email).first() is not None

    def create_user(self, user: User) -> User:
        """
        Create a new user in the database.
        
        Args:
            user: User entity to create
            
        Returns:
            Created user with generated ID
            
        Raises:
            ConflictError: If email already exists
            AppError: If database operation fails
        """
        try:
            self.db.add(user)
            self.db.commit()
            self.db.refresh(user)
            return user

        except IntegrityError:
            self.db.rollback()
            raise ConflictError("User with same email already exists")

        except SQLAlchemyError:
            self.db.rollback()
            raise AppError("Database operation failed")

    def update_user(self, user: User) -> User:
        """
        Update an existing user in the database.
        
        Args:
            user: User entity with updated fields
            
        Returns:
            Updated user
            
        Raises:
            ConflictError: If email already exists (unique constraint)
            AppError: If database operation fails
        """
        try:
            self.db.commit()
            self.db.refresh(user)
            return user

        except IntegrityError:
            self.db.rollback()
            raise ConflictError("Email already exists")

        except SQLAlchemyError:
            self.db.rollback()
            raise AppError("Database operation failed")

    def delete_user(self, user: User) -> None:
        """
        Delete a user from the database.
        
        Args:
            user: User entity to delete
            
        Raises:
            AppError: If database operation fails
        """
        try:
            self.db.delete(user)
            self.db.commit()

        except SQLAlchemyError:
            self.db.rollback()
            raise AppError("Database operation failed")

    def delete_by_id(self, user_id: int) -> bool:
        """
        Delete a user by ID.
        
        Args:
            user_id: ID of user to delete
            
        Returns:
            True if user was deleted, False if not found
            
        Raises:
            AppError: If database operation fails
        """
        try:
            user = self.get_by_id(user_id)
            if user is None:
                return False
            
            self.db.delete(user)
            self.db.commit()
            return True

        except SQLAlchemyError:
            self.db.rollback()
            raise AppError("Database operation failed")