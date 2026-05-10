"""
Database Model Schemas (for reference and validation)
These mirror the Supabase schema for type safety.
"""
from typing import Any, Dict, List, Optional
from datetime import datetime, date, time
from uuid import UUID
from pydantic import BaseModel, Field


class UserProfile(BaseModel):
    """User profile with personality parameters"""
    id: UUID
    user_id: UUID
    email: Optional[str] = None
    name: Optional[str] = None
    timezone: str = "UTC"
    active_hours_start: time = Field(default_factory=lambda: time(8, 0))
    active_hours_end: time = Field(default_factory=lambda: time(22, 0))
    dnd_enabled: bool = False
    dnd_start: time = Field(default_factory=lambda: time(22, 0))
    dnd_end: time = Field(default_factory=lambda: time(8, 0))
    interests: List[str] = Field(default_factory=list)
    behavioral_patterns: Dict[str, Any] = Field(default_factory=dict)
    personality_params: Dict[str, Any] = Field(default_factory=dict)
    preference_history: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class Interaction(BaseModel):
    """Interaction record with quality scores"""
    id: UUID
    user_id: UUID
    session_id: Optional[UUID] = None
    interaction_type: str
    input_text: Optional[str] = None
    input_metadata: Dict[str, Any] = Field(default_factory=dict)
    intent_class: Optional[str] = None
    emotion_scores: Dict[str, float] = Field(default_factory=dict)
    stress_score: float = 0.0
    chain_used: str
    model_used: Optional[str] = None
    latency_ms: Optional[int] = None
    tokens_used: Optional[int] = None
    response_text: Optional[str] = None
    response_metadata: Dict[str, Any] = Field(default_factory=dict)
    personality_mode: Optional[str] = None
    quality_accuracy_score: Optional[float] = None
    quality_helpfulness_score: Optional[float] = None
    quality_personality_fit_score: Optional[float] = None
    sources_used: List[Dict[str, Any]] = Field(default_factory=list)
    context_tiers: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class KnowledgeBase(BaseModel):
    """Semantic knowledge store"""
    id: UUID
    user_id: UUID
    content: str
    content_type: str  # fact, preference, insight, pattern
    category: Optional[str] = None
    source_interaction_id: Optional[UUID] = None
    source_type: Optional[str] = None
    source_metadata: Dict[str, Any] = Field(default_factory=dict)
    # embedding: List[float]  # 768-dim vector, handled separately
    access_count: int = 0
    last_accessed: Optional[datetime] = None
    confidence_score: float = 0.8
    quality_score: float = 0.8
    created_at: datetime
    updated_at: datetime
    expires_at: Optional[datetime] = None


class NewsArticle(BaseModel):
    """Processed news article"""
    id: UUID
    user_id: UUID
    title: str
    summary: Optional[str] = None
    content_hash: Optional[str] = None
    url: Optional[str] = None
    source_name: Optional[str] = None
    source_type: Optional[str] = None
    original_text: Optional[str] = None
    bart_summary: Optional[str] = None
    entities: List[Dict[str, Any]] = Field(default_factory=list)
    topics: List[str] = Field(default_factory=list)
    # embedding: List[float]
    urgency_score: Optional[int] = None
    relevance_score: Optional[float] = None
    interest_match: Dict[str, Any] = Field(default_factory=dict)
    processed: bool = False
    delivered: bool = False
    delivery_method: Optional[str] = None
    published_at: Optional[datetime] = None
    fetched_at: datetime
    processed_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None


class EventQueue(BaseModel):
    """Proactive event queue"""
    id: UUID
    user_id: UUID
    event_type: str
    urgency: int
    source_agent: str
    title: str
    body: Optional[str] = None
    tillu_message: Optional[str] = None
    structured_data: Dict[str, Any] = Field(default_factory=dict)
    sources: List[Dict[str, Any]] = Field(default_factory=list)
    actions: List[str] = Field(default_factory=list)
    personality_mode: Optional[str] = None
    deliver_after: datetime
    expires_at: Optional[datetime] = None
    require_ack: bool = False
    target_client_id: Optional[UUID] = None
    status: str = "pending"
    delivered_at: Optional[datetime] = None
    acknowledged_at: Optional[datetime] = None
    dedup_key: Optional[str] = None
    generated_at: datetime


class ResearchSession(BaseModel):
    """Research session record"""
    id: UUID
    user_id: UUID
    query: str
    research_plan: Dict[str, Any] = Field(default_factory=dict)
    search_results: List[Dict[str, Any]] = Field(default_factory=list)
    scraped_content: List[Dict[str, Any]] = Field(default_factory=list)
    synthesis: Optional[str] = None
    critique: Dict[str, Any] = Field(default_factory=dict)
    iteration_count: int = 0
    full_synthesis: Dict[str, Any] = Field(default_factory=dict)
    executive_summary: Optional[str] = None
    citations: List[Dict[str, Any]] = Field(default_factory=list)
    # embedding: List[float]
    status: str = "pending"
    created_at: datetime
    completed_at: Optional[datetime] = None


class TaskGoal(BaseModel):
    """Task or goal with probability scoring"""
    id: UUID
    user_id: UUID
    title: str
    description: Optional[str] = None
    type: str  # task, goal, habit, project
    category: Optional[str] = None
    due_date: Optional[datetime] = None
    start_date: Optional[datetime] = None
    recurrence: Optional[str] = None
    status: str = "active"
    priority: int = 3
    progress_percent: int = 0
    completed_at: Optional[datetime] = None
    probability_of_completion: float = 0.5
    estimated_effort_hours: Optional[int] = None
    days_at_current_rate: Optional[int] = None
    last_nudge_at: Optional[datetime] = None
    nudge_count: int = 0
    nudge_next_at: Optional[datetime] = None
    related_knowledge_ids: List[UUID] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class EmotionLog(BaseModel):
    """Emotional state record"""
    id: UUID
    user_id: UUID
    joy: float = 0.0
    sadness: float = 0.0
    anger: float = 0.0
    fear: float = 0.0
    surprise: float = 0.0
    disgust: float = 0.0
    neutral: float = 0.0
    dominant_emotion: Optional[str] = None
    emotion_intensity: Optional[float] = None
    stress_level: Optional[str] = None
    interaction_id: Optional[UUID] = None
    context: Optional[str] = None
    recorded_at: datetime


class FinancialTracking(BaseModel):
    """Financial asset tracking"""
    id: UUID
    user_id: UUID
    asset_type: str  # crypto, stock, forex, commodity
    symbol: str
    name: Optional[str] = None
    current_price: Optional[float] = None
    price_currency: str = "USD"
    price_history: List[Dict[str, Any]] = Field(default_factory=list)
    alert_threshold_pct: float = 2.0
    last_alert_at: Optional[datetime] = None
    alert_count: int = 0
    quantity_held: float = 0.0
    cost_basis: Optional[float] = None
    source: str = "coingecko"
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class WebMonitor(BaseModel):
    """Web change monitor"""
    id: UUID
    user_id: UUID
    url: str
    name: Optional[str] = None
    description: Optional[str] = None
    check_interval_minutes: int = 30
    css_selector: Optional[str] = None
    content_type: str = "text"
    last_content: Optional[str] = None
    last_content_hash: Optional[str] = None
    last_checked_at: Optional[datetime] = None
    last_changed_at: Optional[datetime] = None
    change_count: int = 0
    alert_threshold: float = 0.1
    notify_on_change: bool = True
    is_active: bool = True
    last_error: Optional[str] = None
    consecutive_errors: int = 0
    created_at: datetime
    updated_at: datetime


class PeopleKnowledge(BaseModel):
    """Relationship intelligence"""
    id: UUID
    user_id: UUID
    name: str
    relationship_type: Optional[str] = None
    contact_info: Dict[str, Any] = Field(default_factory=dict)
    notes: Optional[str] = None
    preferences: Dict[str, Any] = Field(default_factory=dict)
    conversation_history: List[Dict[str, Any]] = Field(default_factory=list)
    last_interaction_at: Optional[datetime] = None
    interaction_frequency: Optional[str] = None
    relationship_health_score: float = 0.8
    birthday: Optional[date] = None
    anniversary: Optional[date] = None
    other_dates: List[Dict[str, Any]] = Field(default_factory=list)
    # embedding: List[float]
    needs_attention: bool = False
    suggested_actions: List[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class ClientRegistry(BaseModel):
    """Registered client"""
    id: UUID
    user_id: UUID
    client_name: str
    client_type: str
    supports_text: bool = True
    supports_audio: bool = False
    supports_image: bool = False
    supports_document: bool = False
    supports_location: bool = False
    supports_sse: bool = False
    supports_websocket: bool = False
    preferences: Dict[str, Any] = Field(default_factory=dict)
    is_connected: bool = False
    last_connected_at: Optional[datetime] = None
    connection_metadata: Dict[str, Any] = Field(default_factory=dict)
    api_key_hash: Optional[str] = None
    created_at: datetime
    updated_at: datetime
