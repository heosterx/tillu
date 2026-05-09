"""
Pytest configuration and fixtures
"""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def mock_db():
    """Mock database client"""
    mock = MagicMock()
    mock.fetch_one = AsyncMock(return_value=None)
    mock.fetch_many = AsyncMock(return_value=[])
    mock.insert = AsyncMock(return_value=None)
    mock.update = AsyncMock(return_value=None)
    mock.delete = AsyncMock(return_value=True)
    mock.rpc = AsyncMock(return_value=None)
    return mock


@pytest.fixture
def mock_cache():
    """Mock cache client"""
    mock = MagicMock()
    mock.get = AsyncMock(return_value=None)
    mock.set = AsyncMock(return_value=True)
    mock.delete = AsyncMock(return_value=True)
    mock.exists = AsyncMock(return_value=False)
    mock.publish = AsyncMock(return_value=True)
    mock.subscribe = AsyncMock(return_value=None)
    return mock


@pytest.fixture
def sample_user_id():
    """Sample user ID for tests"""
    return "test-user-123"


@pytest.fixture
def sample_session_id():
    """Sample session ID for tests"""
    return "test-session-456"


@pytest.fixture
def sample_interaction_data():
    """Sample interaction data"""
    return {
        "user_id": "test-user-123",
        "session_id": "test-session-456",
        "interaction_type": "text",
        "input_text": "Hello, TILLU!",
        "chain_used": "conversational",
        "response_text": "Hello! How can I help you today?",
        "personality_mode": "warm"
    }
