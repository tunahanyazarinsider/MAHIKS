# app/core/auth.py
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy.orm import Session
from backend.config import Config
from backend.database.database import get_db
from backend.models.models import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:

    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            token,
            Config.JWT_SECRET,
            algorithms=[Config.JWT_ALGORITHM]
        )
    except JWTError:
        raise credentials_exc

    if payload.get("type") != "access":
        raise credentials_exc

    user_id = payload.get("sub")
    if user_id is None:
        raise credentials_exc

    user = db.query(User).get(int(user_id))
    if not user:
        raise credentials_exc

    return user
