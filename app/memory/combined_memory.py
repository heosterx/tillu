"""
CombinedMemory - Wraps all three memory types

LangChain Memory Stack:
├── ConversationBufferWindowMemory
│   Window: last 20 messages
│   Purpose: Immediate conversation coherence
│
├── VectorStoreRetrieverMemory
│   Store: Supabase pgvector
│   Retriever: similarity threshold 0.75
│   Purpose: Long-term semantic recall
│
└── ConversationSummaryMemory
    Model: Groq Llama 3.1 8B (fast)
    Purpose: Compressed history for old conversations
    Trigger: Conversation > 40 turns
"""
from typing import Any, Dict, List, Optional
from datetime import datetime
from uuid import UUID

from app.utils.database import db
from app.utils.cache import cache
from app.utils.logging import get_logger

logger = get_logger("combined_memory")


class CombinedMemory:
    """
    Combines multiple memory types for comprehensive recall.
    
    1. ConversationBufferWindowMemory: Recent turns (last 20)
    2. VectorStoreRetrieverMemory: Semantic similarity search
    3. ConversationSummaryMemory: Compressed older conversations
    """
    
    def __init__(
        self,
        user_id: str,
        session_id: Optional[str] = None,
        window_size: int = 20,
        similarity_threshold: float = 0.75
    ):
        self.user_id = user_id
        self.session_id = session_id
        self.window_size = window_size
        self.similarity_threshold = similarity_threshold
        self.logger = get_logger("combined_memory")
    
    async def load_memory_variables(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Load all memory variables for the current context.
        
        Returns context with:
        - recent_conversation: Last N turns (from buffer)
        - relevant_memories: Semantic matches (from vector store)
        - conversation_summary: Compressed history (if > 40 turns)
        """
        input_text = inputs.get("input", "")
        
        # Load from all memory types concurrently
        recent_task = self._get_recent_conversation()
        relevant_task = self._get_semantic_memories(input_text)
        summary_task = self._get_conversation_summary()
        
        recent, relevant, summary = await asyncio.gather(
            recent_task, relevant_task, summary_task,
            return_exceptions=True
        )
        
        return {
            "recent_conversation": recent if not isinstance(recent, Exception) else [],
            "relevant_memories": relevant if not isinstance(relevant, Exception) else [],
            "conversation_summary": summary if not isinstance(summary, Exception) else None,
            "total_turns": len(recent) if not isinstance(recent, Exception) else 0
        }
    
    async def _get_recent_conversation(self) -> List[Dict[str, Any]]:
        """
        Get recent conversation turns (ConversationBufferWindowMemory).
        Last 20 messages for immediate coherence.
        """
        cache_key = f"conversation_buffer:{self.user_id}:{self.session_id}"
        
        # Try cache first
        cached = await cache.get(cache_key)
        if cached:
            return cached
        
        # Query database
        filters = {"user_id": self.user_id}
        if self.session_id:
            filters["session_id"] = self.session_id
        
        interactions = await db.fetch_many(
            "interactions",
            filters=filters,
            order_by="created_at",
            ascending=False,
            limit=self.window_size
        )
        
        # Format as conversation turns
        turns = []
        for interaction in reversed(interactions):
            if interaction.get("input_text"):
                turns.append({
                    "role": "user",
                    "content": interaction["input_text"],
                    "timestamp": interaction.get("created_at"),
                    "emotion": interaction.get("emotion_scores")
                })
            if interaction.get("response_text"):
                turns.append({
                    "role": "assistant",
                    "content": interaction["response_text"],
                    "timestamp": interaction.get("created_at"),
                    "personality_mode": interaction.get("personality_mode")
                })
        
        # Cache for 5 minutes
        await cache.set(cache_key, turns, ttl=300)
        
        return turns
    
    async def _get_semantic_memories(self, input_text: str) -> List[Dict[str, Any]]:
        """
        Get semantically relevant memories (VectorStoreRetrieverMemory).
        Uses pgvector similarity search.
        
        NOTE: Full implementation requires embeddings in Phase 2.
        """
        # Placeholder: Return recent knowledge items
        # Phase 2: Generate embedding for input_text and do similarity search
        knowledge = await db.fetch_many(
            "knowledge_base",
            filters={"user_id": self.user_id},
            order_by="last_accessed",
            ascending=False,
            limit=5
        )
        
        return [
            {
                "content": item.get("content"),
                "category": item.get("category"),
                "source_type": item.get("source_type"),
                "confidence": item.get("confidence_score"),
                "retrieval_method": "recent"  # Will be "similarity" in Phase 2
            }
            for item in knowledge
        ]
    
    async def _get_conversation_summary(self) -> Optional[str]:
        """
        Get compressed conversation summary (ConversationSummaryMemory).
        Triggered when conversation > 40 turns.
        """
        # Count total interactions
        count_result = await db.rpc(
            "count_interactions",
            {"user_id": self.user_id, "session_id": self.session_id}
        )
        
        if not count_result or count_result < 40:
            return None
        
        # Phase 3: Use Groq 8B to generate summary
        # For now, return placeholder
        return f"Conversation with {count_result} total interactions. Summary generation coming in Phase 3."
    
    async def save_context(
        self,
        inputs: Dict[str, Any],
        outputs: Dict[str, Any]
    ) -> None:
        """
        Save context from this conversation turn.
        Updates buffer and triggers summary if needed.
        """
        # Invalidate conversation buffer cache
        cache_key = f"conversation_buffer:{self.user_id}:{self.session_id}"
        await cache.delete(cache_key)
        
        # Store in knowledge base if important
        output_text = outputs.get("output", "")
        if self._is_important_content(output_text):
            await self._store_to_knowledge_base(inputs, outputs)
    
    def _is_important_content(self, text: str) -> bool:
        """Determine if content should be stored in long-term memory"""
        # Simple heuristics for importance
        indicators = [
            "remember", "don't forget", "important",
            "preference", "always", "never", "my"
        ]
        text_lower = text.lower()
        return any(ind in text_lower for ind in indicators)
    
    async def _store_to_knowledge_base(
        self,
        inputs: Dict[str, Any],
        outputs: Dict[str, Any]
    ) -> None:
        """Store important information to knowledge base"""
        # This would be called to store facts, preferences, etc.
        # Implementation in Phase 2 with embedding generation
        pass
    
    async def clear(self) -> None:
        """Clear all memory for this session"""
        cache_key = f"conversation_buffer:{self.user_id}:{self.session_id}"
        await cache.delete(cache_key)
        self.logger.info(f"Cleared memory for user {self.user_id}")


# Import asyncio for async operations
import asyncio
