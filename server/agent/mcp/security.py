import jwt
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from datetime import datetime, timedelta
from typing import Optional, Tuple
import time
from cryptography.fernet import Fernet
import os
import base64
import hashlib

from .config import settings

# JWT token handling
security = HTTPBearer()


class JWTData(BaseModel):
    """Data stored in a JWT token"""
    user_id: int
    workspace_id: int
    exp: Optional[int] = None


def create_jwt_token(user_id: int, workspace_id: int, expiry: datetime) -> Tuple[str, int]:
    """Create a JWT token for a user and workspace"""
    expires_at = int(expiry.timestamp())
    
    payload = {
        "user_id": user_id,
        "workspace_id": workspace_id,
        "exp": expires_at
    }
    
    token = jwt.encode(
        payload,
        settings.SECRET_KEY,
        algorithm="HS256"
    )
    
    return token, expires_at


def verify_jwt_token(credentials: HTTPAuthorizationCredentials = Security(security)) -> JWTData:
    """Verify a JWT token and return the data"""
    try:
        token = credentials.credentials
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=["HS256"]
        )
        
        # Convert to JWTData model
        return JWTData(**payload)
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired"
        )
    except (jwt.JWTError, jwt.InvalidTokenError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Failed to authenticate: {str(e)}"
        )


# Token encryption for storing sensitive tokens
class TokenEncryption:
    """Handles encryption and decryption of tokens"""
    
    def __init__(self):
        """Initialize with a key derived from settings"""
        # Use SECRET_KEY to derive an encryption key
        # This ensures Fernet key is properly formatted (32 url-safe base64-encoded bytes)
        key_bytes = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
        self.cipher_suite = Fernet(base64.urlsafe_b64encode(key_bytes))
    
    def encrypt_token(self, token: str) -> str:
        """Encrypt a token for storage"""
        return self.cipher_suite.encrypt(token.encode()).decode()
    
    def decrypt_token(self, encrypted_token: str) -> str:
        """Decrypt a stored token"""
        return self.cipher_suite.decrypt(encrypted_token.encode()).decode()


# Create a global token encryption instance
token_encryption = TokenEncryption()
