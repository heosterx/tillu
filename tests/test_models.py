"""
Tests for Pydantic models
"""
import pytest
from uuid import uuid4
from datetime import datetime
from app.models.api import (
    MessageRequest, MessageResponse, ChainMetadata,
    MemorySearchRequest, MemoryItem, HealthResponse
)
from app.models.database import UserProfile, Interaction


def test_message_request_validation():
    """Test message request validation"""
    # Valid text message
    request = MessageRequest(type="text", text="Hello")
    assert request.type.value == "text"
    assert request.text == "Hello"
    
    # Valid audio message
    request = MessageRequest(type="audio", media_url="https://example.com/audio.mp3")
    assert request.type.value == "audio"


def test_memory_search_request():
    """Test memory search request"""
    request = MemorySearchRequest(
        query="my preferences",
        limit=10,
        similarity_threshold=0.8
    )
    assert request.query == "my preferences"
    assert request.limit == 10
    assert request.similarity_threshold == 0.8


def test_memory_item():
    """Test memory item model"""
    item = MemoryItem(
        id=uuid4(),
        content="Test memory content",
        content_type="fact",
        category="preferences",
        confidence_score=0.9,
        similarity=0.85,
        created_at=datetime.now()
    )
    assert item.content == "Test memory content"
    assert item.confidence_score == 0.9


def test_user_profile_model():
    """Test user profile model"""
    profile = UserProfile(
        id=uuid4(),
        user_id=uuid4(),
        email="test@example.com",
        name="Test User",
        timezone="UTC",
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    assert profile.email == "test@example.com"
    assert profile.timezone == "UTC"


def test_interaction_model():
    """Test interaction model"""
    interaction = Interaction(
        id=uuid4(),
        user_id=uuid4(),
        interaction_type="text",
        input_text="Hello",
        chain_used="conversational",
        created_at=datetime.now()
    )
    assert interaction.chain_used == "conversational"
    assert interaction.interaction_type == "text"
