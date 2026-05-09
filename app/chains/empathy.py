"""
Chain 06: Empathy Chain
Type: ConversationChain specialized
Trigger: Emotion detector: distress | sadness | high_stress
Model: Groq 70B, temperature 0.9
Override: Sarcasm disabled, warmth max, challenge disabled
Output: Emotionally calibrated response
"""
from typing import Any, Dict, Optional
import time
from langchain_groq import ChatGroq
from langchain.schema import SystemMessage, HumanMessage, AIMessage

from app.config import settings
from app.chains.base import BaseChain, ChainType
from app.utils.logging import get_logger

logger = get_logger("empathy_chain")


class EmpathyChain(BaseChain):
    """
    Specialized chain for emotional support
    Triggered when user shows distress, sadness, or high stress
    """
    
    chain_type = ChainType.EMPATHY
    description = "Emotionally supportive responses for distress/sadness/high stress"
    
    def __init__(self):
        super().__init__()
        self.llm = None
        if settings.groq_api_key:
            self.llm = ChatGroq(
                api_key=settings.groq_api_key,
                model_name="llama-3.1-70b-versatile",
                temperature=0.9,  # Higher for warmth
                max_tokens=1024
            )
    
    async def execute(
        self,
        input_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute empathy chain
        
        Args:
            input_data: Contains 'text' (user message)
            context: Full context with emotional state
            
        Returns:
            Warm, supportive response
        """
        start_time = time.time()
        
        user_input = input_data.get("text", "")
        
        # Extract emotional context
        emotional = context.get("emotional", {}) if context else {}
        dominant_emotion = emotional.get("dominant_emotion", "neutral")
        stress = context.get("stress", {}).get("stress_level", "low")
        
        logger.info("Empathy mode activated", emotion=dominant_emotion, stress=stress)
        
        if not self.llm:
            # Fallback supportive response
            return {
                "response": {
                    "type": "text",
                    "content": "I'm here for you. Take your time, and let me know how I can support you right now.",
                    "structured_data": {"mode": "empathy", "fallback": True}
                },
                "personality_mode": "empathic",
                "chain": self.chain_type.value,
                "model": "fallback",
                "latency_ms": int((time.time() - start_time) * 1000),
                "tokens_used": 0,
                "sources": []
            }
        
        try:
            # Build empathy-focused system prompt
            # Override: sarcasm disabled, warmth max, challenge disabled
            system_prompt = f"""You are TILLU, providing emotional support.

CURRENT MODE: EMPATHIC SUPPORT
- Sarcasm: DISABLED
- Warmth: MAXIMUM
- Challenge style: DISABLED
- Temperature: HIGH (warm and supportive)

User's emotional state:
- Dominant emotion: {dominant_emotion}
- Stress level: {stress}

Guidelines:
- Listen with empathy and validate their feelings
- Offer gentle, non-judgmental support
- Ask how you can help, don't assume
- Be patient and give them space to share
- Don't rush to solutions unless they ask
- Acknowledge that their feelings are valid

Respond as a caring, supportive friend would."""

            # Build conversation history
            messages = [SystemMessage(content=system_prompt)]
            
            # Add recent turns
            immediate_memory = context.get("immediate_memory", {}) if context else {}
            recent_turns = immediate_memory.get("recent_turns", [])
            
            for turn in recent_turns[-5:]:  # Last 5 for emotional continuity
                if turn.get("role") == "user":
                    messages.append(HumanMessage(content=turn.get("content", "")))
                elif turn.get("role") == "assistant":
                    messages.append(AIMessage(content=turn.get("content", "")))
            
            # Add current input
            messages.append(HumanMessage(content=user_input))
            
            # Generate response
            response = await self.llm.ainvoke(messages)
            
            elapsed_ms = int((time.time() - start_time) * 1000)
            
            return {
                "response": {
                    "type": "text",
                    "content": response.content,
                    "structured_data": {
                        "mode": "empathy",
                        "dominant_emotion": dominant_emotion,
                        "stress_level": stress
                    }
                },
                "personality_mode": "empathic",
                "chain": self.chain_type.value,
                "model": "groq-llama-3.1-70b",
                "latency_ms": elapsed_ms,
                "tokens_used": response.response_metadata.get("token_usage", {}).get("total_tokens", 0) if hasattr(response, 'response_metadata') else 0,
                "sources": []
            }
            
        except Exception as e:
            logger.error(f"Empathy chain error: {e}")
            return {
                "response": {
                    "type": "text",
                    "content": "I'm here for you. I'm listening if you want to talk.",
                    "structured_data": {"mode": "empathy", "error": str(e)}
                },
                "personality_mode": "empathic",
                "chain": self.chain_type.value,
                "model": "error",
                "latency_ms": int((time.time() - start_time) * 1000),
                "tokens_used": 0,
                "sources": []
            }
