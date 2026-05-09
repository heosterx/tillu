"""
API Request/Response Models
"""
from typing import Any, Dict, List, Optional
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field, validator
from enum import Enum


class MessageType(str, Enum):
    TEXT = "text"
    AUDIO = "audio"
    IMAGE = "image"
    DOCUMENT = "document"
    LOCATION = "location"


class MessageRequest(BaseModel):
    """Request model for /api/v1/message endpoint"""
    type: MessageType = Field(default=MessageType.TEXT)
    text: Optional[str] = None
    media_url: Optional[str] = None
    location: Optional[Dict[str, float]] = None  # {lat, lng}
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)
    client_id: Optional[UUID] = None
    
    @validator("text")
    def validate_text_for_text_type(cls, v, values):
        if values.get("type") == MessageType.TEXT and not v:
            raise ValueError("text is required for text message type")
        return v


class ChainMetadata(BaseModel):
    """Metadata about the chain execution"""
    chain: str
    model: str
    latency_ms: int
    tokens_used: int
    intent_class: Optional[str] = None
    personality_mode: Optional[str] = None


class SourceInfo(BaseModel):
    """Source information for responses"""
    name: str
    url: Optional[str] = None
    type: str = "general"


class MessageResponse(BaseModel):
    """Response model for /api/v1/message endpoint"""
    response: Dict[str, Any] = Field(..., description="Response content with type and structured data")
    personality_mode: str = "sharp"
    queued_events: List[Dict[str, Any]] = Field(default_factory=list)
    intelligence_packet: Optional[Dict[str, Any]] = None
    meta: ChainMetadata
    sources: List[SourceInfo] = Field(default_factory=list)
    session_id: Optional[UUID] = None


class IntelligencePacket(BaseModel):
    """Compiled intelligence for client consumption"""
    packet_type: str  # morning_brief, news_digest, etc.
    generated_at: datetime
    expires_at: Optional[datetime] = None
    content: Dict[str, Any]
    sources: List[SourceInfo]


class EventResponse(BaseModel):
    """Event in the response queue"""
    event_id: UUID
    event_type: str
    urgency: int = Field(..., ge=1, le=10)
    title: str
    body: str
    tillu_message: str
    actions: List[str]
    generated_at: datetime
    requires_ack: bool = False


class HealthStatus(BaseModel):
    """Health status of a service"""
    service: str
    status: str  # healthy, degraded, down
    response_time_ms: Optional[int] = None
    last_check: datetime
    details: Optional[Dict[str, Any]] = None


class HealthResponse(BaseModel):
    """System health status"""
    status: str = "healthy"
    version: str
    timestamp: datetime
    services: List[HealthStatus]
    api_limits: Dict[str, Dict[str, Any]]  # Provider -> {remaining, reset_time}
    queue_depths: Dict[str, int]  # Queue name -> count


class MemorySearchRequest(BaseModel):
    """Request for semantic memory search"""
    query: str
    types: Optional[List[str]] = None  # Filter by content type
    date_range_start: Optional[datetime] = None
    date_range_end: Optional[datetime] = None
    limit: int = Field(default=10, ge=1, le=50)
    similarity_threshold: float = Field(default=0.75, ge=0.0, le=1.0)


class MemoryItem(BaseModel):
    """Single memory item in search results"""
    id: UUID
    content: str
    content_type: str
    category: Optional[str] = None
    source_type: Optional[str] = None
    confidence_score: float
    similarity: float
    created_at: datetime


class MemorySearchResponse(BaseModel):
    """Response for memory search"""
    query: str
    results: List[MemoryItem]
    total_found: int
    search_time_ms: int


class ClientCapabilities(BaseModel):
    """Client capabilities for registration"""
    supports_text: bool = True
    supports_audio: bool = False
    supports_image: bool = False
    supports_document: bool = False
    supports_location: bool = False
    supports_sse: bool = False
    supports_websocket: bool = False


class ClientRegistrationRequest(BaseModel):
    """Request to register a new client"""
    client_name: str
    client_type: str  # whatsapp, web, mobile, api
    capabilities: ClientCapabilities = Field(default_factory=ClientCapabilities)
    preferences: Optional[Dict[str, Any]] = None


class ClientRegistrationResponse(BaseModel):
    """Response for client registration"""
    client_id: UUID
    api_key: str
    registered_at: datetime
    message: str = "Client registered successfully"


class StreamEvent(BaseModel):
    """Event sent via SSE/WebSocket stream"""
    event_id: UUID
    event_type: str
    urgency: int
    source_agent: str
    content: Dict[str, Any]
    personality_mode: str
    generated_at: datetime
    
    
class AnalyticsResponse(BaseModel):
    """System analytics data"""
    period_start: datetime
    period_end: datetime
    
    # Interactions
    total_interactions: int
    avg_response_time_ms: float
    interactions_by_chain: Dict[str, int]
    
    # Quality
    avg_quality_scores: Dict[str, float]
    
    # API Usage
    api_usage: Dict[str, Dict[str, int]]
    
    # Events
    events_generated: int
    events_by_type: Dict[str, int]
    
    # Memory
    knowledge_items: int
    memory_searches: int
