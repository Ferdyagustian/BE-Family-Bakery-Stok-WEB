import os
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.models import User, Role

security = HTTPBearer()

JWT_SECRET = os.getenv("JWT_SECRET", "family-bakery-local-dev-secret-key-12345")
ALGORITHM = "HS256"

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> User:
    """
    Validates the JWT token from the Authorization header and returns the user payload.
    This implementation is stateless and relies on the signed token from Next.js.
    """
    token = credentials.credentials
    try:
        # Next.js `jose` payload has { user: { id, role, storeId }, expires }
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        user_data = payload.get("user")
        
        if not user_data:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication payload",
                headers={"WWW-Authenticate": "Bearer"},
            )
            
        return User(
            id=user_data.get("id", "unknown"),
            role=user_data.get("role", Role.MANAGER),
            storeId=user_data.get("storeId"),
            username="jwt-user",
            passwordHash=""
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
