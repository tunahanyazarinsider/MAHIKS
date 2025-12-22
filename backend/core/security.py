# app/core/security.py
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from jose import jwt, JWTError
from passlib.context import CryptContext
from backend.config import Config

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain: str, hashed: str) -> bool:
    """
    Verify a plain password against a hashed password.
    
    Args:
        plain: Plain text password
        hashed: Hashed password to compare against
        
    Returns:
        True if password matches, False otherwise
    """
    return pwd_context.verify(plain, hashed)


def hash_password(password: str) -> str:
    """
    Hash a plain password using bcrypt.
    
    Args:
        password: Plain text password to hash
        
    Returns:
        Hashed password string
    """
    return pwd_context.hash(password)


def create_access_token(subject: str, claims: dict = None) -> str:
    """
    Create a JWT access token.
    
    Args:
        subject: Token subject (usually user ID)
        claims: Additional claims to include in token
        
    Returns:
        Encoded JWT token string
    """
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
    """
    Create a JWT refresh token.
    
    Args:
        subject: Token subject (usually user ID)
        
    Returns:
        Encoded JWT refresh token string
    """
    now = datetime.utcnow()
    payload = {
        "sub": subject,
        "type": "refresh",
        "iat": now.timestamp(),
        "exp": (now + timedelta(days=Config.REFRESH_TOKEN_EXPIRE_DAYS)).timestamp(),
    }
    return jwt.encode(payload, Config.JWT_SECRET, algorithm=Config.JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Decode and validate a JWT access token.
    
    Args:
        token: JWT token string to decode
        
    Returns:
        Token payload dict if valid, None if invalid or expired
    """
    try:
        payload = jwt.decode(
            token, 
            Config.JWT_SECRET, 
            algorithms=[Config.JWT_ALGORITHM]
        )
        
        # Verify token type is 'access'
        if payload.get("type") != "access":
            return None
        
        return payload
        
    except JWTError:
        return None


def decode_refresh_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Decode and validate a JWT refresh token.
    
    Args:
        token: JWT refresh token string to decode
        
    Returns:
        Token payload dict if valid, None if invalid or expired
    """
    try:
        payload = jwt.decode(
            token, 
            Config.JWT_SECRET, 
            algorithms=[Config.JWT_ALGORITHM]
        )
        
        # Verify token type is 'refresh'
        if payload.get("type") != "refresh":
            return None
        
        return payload
        
    except JWTError:
        return None


def get_token_subject(token: str) -> Optional[str]:
    """
    Extract subject (user ID) from a token without full validation.
    
    Args:
        token: JWT token string
        
    Returns:
        Subject string if extractable, None otherwise
    """
    try:
        payload = jwt.decode(
            token, 
            Config.JWT_SECRET, 
            algorithms=[Config.JWT_ALGORITHM]
        )
        return payload.get("sub")
    except JWTError:
        return None