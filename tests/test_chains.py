"""
Tests for LangChain chains
"""
import pytest
from app.chains.base import ChainType, ChainRegistry
from app.chains.conversational import ConversationalChain
from app.chains.context_assembler import ContextAssembler


def test_chain_type_enum():
    """Test chain type enum values"""
    assert ChainType.CONVERSATIONAL.value == "conversational"
    assert ChainType.RESEARCH.value == "research"
    assert ChainType.REACT_AGENT.value == "react_agent"


def test_chain_registry_select():
    """Test chain selection logic"""
    # Test small talk
    chain = ChainRegistry.select_chain("small_talk", "hello")
    assert chain == ChainType.CONVERSATIONAL
    
    # Test research request
    chain = ChainRegistry.select_chain("research_request", "analyze quantum computing")
    assert chain == ChainType.RESEARCH
    
    # Test action required
    chain = ChainRegistry.select_chain("action_required", "book a flight")
    assert chain == ChainType.REACT_AGENT


def test_conversational_chain_init():
    """Test conversational chain initialization"""
    chain = ConversationalChain()
    assert chain.chain_type == ChainType.CONVERSATIONAL
    assert chain.description is not None


@pytest.mark.asyncio
async def test_context_assembler_structure():
    """Test context assembler returns proper structure"""
    context = await ContextAssembler.assemble(
        user_id="test-user",
        input_text="Hello",
        session_id="test-session"
    )
    
    # Check all tiers exist
    assert "identity" in context
    assert "temporal" in context
    assert "emotional" in context
    assert "immediate_memory" in context
    assert "semantic_memory" in context
    assert "situational" in context
    assert "world_state" in context


@pytest.mark.asyncio
async def test_temporal_tier():
    """Test temporal context tier"""
    temporal = await ContextAssembler._tier_2_temporal("test-user")
    
    assert "current_time" in temporal
    assert "hour" in temporal
    assert "period" in temporal
    assert temporal["period"] in ["morning", "afternoon", "evening", "night"]
