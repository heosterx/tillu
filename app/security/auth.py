"""
JWT Authentication Manager
Secure token verification and user authentication
"""
from typing import Optional, Dict, Any
from datetime import datetime
from jose import JWTError, jwt
from fastapi import HTTPException, status
from app.config import settings
from app.utils.logging import get_logger

logger = get_logger("auth")


class AuthManager:
    """Secure JWT verification and authentication"""
    
    def __init__(self, jwt_secret: str):
        self.jwt_secret = jwt_secret
    
    def verify_token(self, token: str) -> Dict[str, Any]:
        """
        Verify JWT token and return claims
        
        Args:
            token: JWT token string
            
        Returns:
            Token claims including user_id
            
        Raises:
            HTTPException: If token is invalid
        """
        try:
            payload = jwt.decode(
                token,
                self.jwt_secret,
                algorithms=["HS256"]
            )
            
            user_id = payload.get("sub")
            if not user_id:
                logger.warning("Token missing 'sub' claim")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token: missing user ID"
                )
            
            # Check token expiration
            exp = payload.get("exp")
            if exp and datetime.utcfromtimestamp(exp) < datetime.utcnow():
                logger.warning(f"Token expired for user {user_id}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token expired"
                )
            
            logger.debug(f"Token verified for user {user_id}")
            
            return {
                "user_id": user_id,
                "payload": payload,
                "verified_at": datetime.utcnow().isoformat()
            }
            
        except JWTError as e:
            logger.warning(f"JWT verification failed: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid token: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Unexpected error during token verification: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Token verification failed"
            )
    
    def create_token(
        self,
        user_id: str,
        expires_in_hours: int = 24
    ) -> str:
        """
        Create JWT token for user
        
        Args:
            user_id: User ID
            expires_in_hours: Token expiration time
            
        Returns:
            JWT token
        """
        from datetime import timedelta
        
        payload = {
            "sub": user_id,
            "iat": datetime.utcnow(),
            "exp": datetime.utcnow() + timedelta(hours=expires_in_hours)
        }
        
        token = jwt.encode(
            payload,
            self.jwt_secret,
            algorithm="HS256"
        )
        
        logger.info(f"Token created for user {user_id}")
        return token


# Global auth manager
auth_manager = AuthManager(settings.supabase_jwt_secret or "dev-secret-key")
