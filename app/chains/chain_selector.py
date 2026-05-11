"""
Intelligent Chain Selector
Scores and selects best chain with confidence
"""
from typing import Dict, Tuple, Any, Optional
from enum import Enum
from app.chains.base import ChainType
from app.utils.logging import get_logger

logger = get_logger("chain_selector")


class ChainSelector:
    """Intelligent chain selection with confidence scoring"""
    
    # Intent to chain mappings
    INTENT_CHAIN_MAP = {
        # Conversational
        "small_talk": ChainType.CONVERSATIONAL,
        "general_query": ChainType.CONVERSATIONAL,
        "follow_up": ChainType.CONVERSATIONAL,
        "greeting": ChainType.CONVERSATIONAL,
        
        # Research
        "research_request": ChainType.RESEARCH,
        "deep_analysis": ChainType.RESEARCH,
        "investigation": ChainType.RESEARCH,
        
        # ReAct Agent
        "action_required": ChainType.REACT_AGENT,
        "real_world_query": ChainType.REACT_AGENT,
        "multi_step_task": ChainType.REACT_AGENT,
        "tool_use": ChainType.REACT_AGENT,
        
        # Analysis
        "pattern_query": ChainType.ANALYSIS,
        "data_analysis": ChainType.ANALYSIS,
        "structured_request": ChainType.ANALYSIS,
        
        # Empathy
        "distress": ChainType.EMPATHY,
        "sadness": ChainType.EMPATHY,
        "high_stress": ChainType.EMPATHY,
        "emotional_support": ChainType.EMPATHY,
    }
    
    @classmethod
    async def select_best_chain(
        cls,
        intent: str,
        context: Dict[str, Any],
        input_text: str
    ) -> Tuple[ChainType, float]:
        """
        Select best chain with confidence score
        
        Args:
            intent: Classified intent
            context: Assembled context
            input_text: User input
            
        Returns:
            Tuple of (chain_type, confidence_score)
        """
        
        scores = {}
        
        # Score each chain
        for chain_type in ChainType:
            score = await cls._score_chain(
                chain_type,
                intent,
                context,
                input_text
            )
            scores[chain_type] = score
        
        # Get best chain
        best_chain = max(scores, key=scores.get)
        confidence = scores[best_chain]
        
        logger.info(
            f"Selected chain: {best_chain.value} "
            f"(confidence: {confidence:.2f}) for intent: {intent}"
        )
        
        return best_chain, confidence
    
    @classmethod
    async def _score_chain(
        cls,
        chain_type: ChainType,
        intent: str,
        context: Dict[str, Any],
        input_text: str
    ) -> float:
        """Score chain suitability"""
        
        score = 0.5  # Base score
        
        # 1. Intent matching (0.3 points)
        intent_scores = {
            ChainType.CONVERSATIONAL: [
                "small_talk", "general_query", "follow_up", "greeting"
            ],
            ChainType.RESEARCH: [
                "research_request", "deep_analysis", "investigation"
            ],
            ChainType.REACT_AGENT: [
                "action_required", "real_world_query", "multi_step_task", "tool_use"
            ],
            ChainType.ANALYSIS: [
                "pattern_query", "data_analysis", "structured_request"
            ],
            ChainType.EMPATHY: [
                "distress", "sadness", "high_stress", "emotional_support"
            ],
        }
        
        if intent in intent_scores.get(chain_type, []):
            score += 0.3
        
        # 2. Context matching (0.2 points)
        emotional = context.get("emotional", {})
        
        if chain_type == ChainType.EMPATHY:
            stress_level = emotional.get("stress_level", "low")
            if stress_level in ["high", "critical"]:
                score += 0.2
        
        if chain_type == ChainType.RESEARCH:
            semantic_results = context.get("semantic_memory", {})
            if semantic_results.get("total_results", 0) > 5:
                score += 0.1
        
        # 3. Input complexity (0.2 points)
        input_length = len(input_text)
        
        if chain_type == ChainType.RESEARCH and input_length > 500:
            score += 0.15
        
        if chain_type == ChainType.ANALYSIS and input_length > 300:
            score += 0.1
        
        # 4. Situational context (0.2 points)
        situational = context.get("situational", {})
        
        if chain_type == ChainType.REACT_AGENT:
            if situational.get("pending_events", []):
                score += 0.1
        
        if chain_type == ChainType.ANALYSIS:
            if situational.get("active_goals_count", 0) > 0:
                score += 0.1
        
        # 5. Temporal context (0.1 points)
        temporal = context.get("temporal", {})
        
        if chain_type == ChainType.CONVERSATIONAL:
            period = temporal.get("period", "")
            if period == "morning":
                score += 0.05
        
        # Normalize to 0-1
        return min(max(score, 0.0), 1.0)
    
    @classmethod
    def get_fallback_chain(cls, intent: str) -> ChainType:
        """Get fallback chain for intent"""
        return cls.INTENT_CHAIN_MAP.get(intent, ChainType.CONVERSATIONAL)
