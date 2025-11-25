# app/core/security.py
from datetime import datetime, timedelta
from jose import jwt
from passlib.context import CryptContext
from backend.config import Config

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def create_access_token(subject: str, claims: dict = None) -> str:
    now = datetime.utcnow()
    payload = {
        "sub": subject,
        "type": "access",
        "iat": now.timestamp(),
        "exp": (now + timedelta(minutes=Config.ACCESS_TOKEN_EXPIRE_MINUTES)).timestamp(),
        **(claims or {})
    }
    return jwt.encode(payload, Config.JWT_SECRET, algorithm=Config.JWT_ALGORITHM)

def create_refresh_token(subject: str) -> str:
    now = datetime.utcnow()
    payload = {
        "sub": subject,
        "type": "refresh",
        "iat": now.timestamp(),
        "exp": (now + timedelta(days=Config.REFRESH_TOKEN_EXPIRE_DAYS)).timestamp(),
    }
    return jwt.encode(payload, Config.JWT_SECRET, algorithm=Config.JWT_ALGORITHM)
