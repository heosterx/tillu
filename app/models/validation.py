"""
Input Validation Models
Pydantic models with comprehensive validation
"""
from pydantic import BaseModel, validator, Field
from typing import Optional, Dict, Any
from urllib.parse import urlparse
import re

logger_name = "validation"


class MessageRequest(BaseModel):
    """Validated message request"""
    
    type: str = Field(..., min_length=1, max_length=20)
    text: Optional[str] = Field(None, max_length=10000)
    media_url: Optional[str] = None
    client_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    
    class Config:
        schema_extra = {
            "example": {
                "type": "text",
                "text": "What's the weather today?",
                "client_id": "web-app-1"
            }
        }
    
    @validator("type")
    def validate_type(cls, v):
        """Validate message type"""
        allowed = ["text", "audio", "image", "document", "location"]
        if v not in allowed:
            raise ValueError(f"Type must be one of {allowed}")
        return v
    
    @validator("text")
    def validate_text(cls, v):
        """Validate text content"""
        if v is None:
            return v
        
        if len(v) > 10000:
            raise ValueError("Text too long (max 10000 chars)")
        
        if not isinstance(v, str):
            raise ValueError("Text must be string")
        
        # Check for injection patterns
        dangerous_patterns = [
            "<script", "javascript:", "onerror=", "onclick=",
            "eval(", "exec(", "import ", "__import__"
        ]
        
        v_lower = v.lower()
        for pattern in dangerous_patterns:
            if pattern in v_lower:
                raise ValueError("Potentially malicious content detected")
        
        return v
    
    @validator("media_url")
    def validate_media_url(cls, v):
        """Validate media URL"""
        if v is None:
            return v
        
        try:
            result = urlparse(v)
            
            # Check URL structure
            if not all([result.scheme, result.netloc]):
                raise ValueError("Invalid URL format")
            
            # Whitelist schemes
            if result.scheme not in ["http", "https"]:
                raise ValueError("Only HTTP/HTTPS URLs allowed")
            
            # Check for suspicious patterns
            if any(x in v.lower() for x in ["localhost", "127.0.0.1", "192.168", "10.0"]):
                raise ValueError("Internal URLs not allowed")
            
            return v
            
        except Exception as e:
            raise ValueError(f"Invalid URL: {str(e)}")
    
    @validator("metadata")
    def validate_metadata(cls, v):
        """Validate metadata"""
        if v is None:
            return v
        
        if len(str(v)) > 5000:
            raise ValueError("Metadata too large (max 5000 chars)")
        
        return v


class ClientRegistrationRequest(BaseModel):
    """Client registration request"""
    
    client_name: str = Field(..., min_length=1, max_length=100)
    client_type: str = Field(..., min_length=1, max_length=50)
    capabilities: Dict[str, bool] = Field(default_factory=dict)
    preferences: Optional[Dict[str, Any]] = None
    
    @validator("client_name")
    def validate_client_name(cls, v):
        """Validate client name"""
        if not re.match(r"^[a-zA-Z0-9\-_\s]+$", v):
            raise ValueError("Client name contains invalid characters")
        return v
    
    @validator("client_type")
    def validate_client_type(cls, v):
        """Validate client type"""
        allowed = ["web", "mobile", "desktop", "api", "bot"]
        if v not in allowed:
            raise ValueError(f"Client type must be one of {allowed}")
        return v


class MemorySearchRequest(BaseModel):
    """Memory search request"""
    
    query: str = Field(..., min_length=1, max_length=1000)
    limit: int = Field(default=10, ge=1, le=100)
    similarity_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    
    @validator("query")
    def validate_query(cls, v):
        """Validate search query"""
        if len(v) > 1000:
            raise ValueError("Query too long (max 1000 chars)")
        return v


class MemoryStoreRequest(BaseModel):
    """Memory store request"""
    
    content: str = Field(..., min_length=1, max_length=5000)
    content_type: str = Field(default="fact")
    category: Optional[str] = None
    
    @validator("content_type")
    def validate_content_type(cls, v):
        """Validate content type"""
        allowed = ["fact", "preference", "goal", "memory", "note"]
        if v not in allowed:
            raise ValueError(f"Content type must be one of {allowed}")
        return v
