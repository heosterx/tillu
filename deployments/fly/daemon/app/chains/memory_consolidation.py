"""
Chain 08: Memory Consolidation Chain
Type: Sequential LLMChain
Trigger: Daily at 00:00 (via daemon / n8n WF-09)
Model: Groq Llama 3.1 70B
Output: Consolidated knowledge items, updated user profile
"""
from typing import Any, Dict, List, Optional
import time
import json
from langchain_groq import ChatGroq
from langchain.schema import HumanMessage, SystemMessage

from app.config import settings
from app.chains.base import BaseChain, ChainType
from app.utils.logging import get_logger
from app.utils.database import db
from app.utils.cache import cache

logger = get_logger("memory_consolidation_chain")


class MemoryConsolidationChain(BaseChain):
    """
    Nightly memory consolidation chain.
    Runs at 00:00 to:
    1. Summarize the day's interactions
    2. Extract durable facts and preferences
    3. Update user profile with new patterns
    4. Prune low-quality or expired memories
    """

    chain_type = ChainType.MEMORY_CONSOLIDATION
    description = "Nightly memory consolidation and knowledge extraction"

    def __init__(self):
        super().__init__()
        self.llm = None
        if settings.groq_api_key:
            self.llm = ChatGroq(
                api_key=settings.groq_api_key,
                model_name="llama-3.1-70b-versatile",
                temperature=0.3,
                max_tokens=2048
            )

    async def execute(
        self,
        input_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute memory consolidation for a user.

        Args:
            input_data: {'user_id': str, 'date': str (YYYY-MM-DD)}
            context: Optional context

        Returns:
            Consolidation results
        """
        start_time = time.time()
        user_id = input_data.get("user_id", "")

        if not user_id:
            return {"error": "user_id required", "consolidated": 0}

        try:
            # Step 1: Fetch today's interactions
            interactions = await db.fetch_many(
                "interactions",
                filters={"user_id": user_id},
                order_by="created_at",
                ascending=False,
                limit=50
            )

            if not interactions:
                return {
                    "response": {"type": "text", "content": "No interactions to consolidate.", "structured_data": {}},
                    "personality_mode": "neutral",
                    "chain": self.chain_type.value,
                    "model": "skipped",
                    "latency_ms": 0,
                    "tokens_used": 0,
                    "sources": [],
                    "consolidated": 0
                }

            # Step 2: Extract facts and preferences using LLM
            facts = await self._extract_facts(interactions)

            # Step 3: Store extracted facts to knowledge base
            stored_count = 0
            for fact in facts:
                try:
                    from app.memory.semantic_search import semantic_search
                    result = await semantic_search.store_with_embedding(
                        user_id=user_id,
                        content=fact["content"],
                        content_type=fact.get("type", "fact"),
                        category=fact.get("category"),
                        source_type="memory_consolidation"
                    )
                    if result:
                        stored_count += 1
                except Exception as e:
                    logger.error(f"Failed to store fact: {e}")

            # Step 4: Update behavioral patterns in user profile
            await self._update_behavioral_patterns(user_id, interactions)

            # Step 5: Prune expired/low-quality memories
            pruned = await self._prune_old_memories(user_id)

            # Step 6: Invalidate caches
            await cache.delete(f"user_profile:{user_id}")
            await cache.delete(f"emotional_state:{user_id}")

            elapsed_ms = int((time.time() - start_time) * 1000)
            logger.info(
                "Memory consolidation complete",
                user_id=user_id,
                facts_extracted=len(facts),
                stored=stored_count,
                pruned=pruned,
                latency_ms=elapsed_ms
            )

            return {
                "response": {
                    "type": "consolidation_report",
                    "content": f"Consolidated {stored_count} facts from {len(interactions)} interactions.",
                    "structured_data": {
                        "interactions_processed": len(interactions),
                        "facts_extracted": len(facts),
                        "facts_stored": stored_count,
                        "memories_pruned": pruned
                    }
                },
                "personality_mode": "neutral",
                "chain": self.chain_type.value,
                "model": "groq-llama-3.1-70b",
                "latency_ms": elapsed_ms,
                "tokens_used": 0,
                "sources": [],
                "consolidated": stored_count
            }

        except Exception as e:
            logger.error(f"Memory consolidation error: {e}")
            return {
                "response": {"type": "text", "content": f"Consolidation error: {e}", "structured_data": {}},
                "personality_mode": "neutral",
                "chain": self.chain_type.value,
                "model": "error",
                "latency_ms": int((time.time() - start_time) * 1000),
                "tokens_used": 0,
                "sources": [],
                "consolidated": 0
            }

    async def _extract_facts(self, interactions: List[Dict]) -> List[Dict]:
        """Extract durable facts and preferences from interactions"""
        if not self.llm:
            return []

        # Build interaction summary
        interaction_text = "\n".join([
            f"User: {i.get('input_text', '')[:200]}\nTILLU: {i.get('response_text', '')[:200]}"
            for i in interactions[:20]
        ])

        try:
            prompt = f"""Analyze these conversations and extract durable facts, preferences, and insights about the user.

Conversations:
{interaction_text[:3000]}

Extract facts in JSON format. Return a JSON array of objects with:
- content: the fact/preference (string)
- type: "fact" | "preference" | "insight" | "pattern"
- category: "work" | "health" | "relationships" | "finance" | "general" | "personality"
- confidence: 0.0-1.0

Only extract clear, durable information. Skip small talk.
Return ONLY valid JSON array, no other text."""

            response = await self.llm.ainvoke([
                SystemMessage(content="You are a memory extraction system. Return only valid JSON."),
                HumanMessage(content=prompt)
            ])

            # Parse JSON
            text = response.content.strip()
            # Find JSON array
            start = text.find('[')
            end = text.rfind(']') + 1
            if start >= 0 and end > start:
                facts = json.loads(text[start:end])
                return [f for f in facts if isinstance(f, dict) and f.get("content")]

        except Exception as e:
            logger.error(f"Fact extraction error: {e}")

        return []

    async def _update_behavioral_patterns(self, user_id: str, interactions: List[Dict]) -> None:
        """Update user profile with behavioral patterns from interactions"""
        try:
            # Calculate patterns
            hour_counts = {}
            chain_counts = {}
            emotion_counts = {}

            for i in interactions:
                # Time patterns
                created = i.get("created_at", "")
                if created and "T" in created:
                    hour = int(created.split("T")[1][:2])
                    hour_counts[str(hour)] = hour_counts.get(str(hour), 0) + 1

                # Chain usage
                chain = i.get("chain_used", "conversational")
                chain_counts[chain] = chain_counts.get(chain, 0) + 1

                # Emotion patterns
                emotion = i.get("emotion_scores", {})
                if isinstance(emotion, dict):
                    dominant = max(emotion, key=emotion.get) if emotion else "neutral"
                    emotion_counts[dominant] = emotion_counts.get(dominant, 0) + 1

            patterns = {
                "peak_hours": hour_counts,
                "chain_preferences": chain_counts,
                "emotion_distribution": emotion_counts,
                "total_interactions": len(interactions)
            }

            await db.update(
                "user_profile",
                {"behavioral_patterns": patterns},
                {"user_id": user_id}
            )

        except Exception as e:
            logger.error(f"Behavioral pattern update error: {e}")

    async def _prune_old_memories(self, user_id: str) -> int:
        """Remove expired or very low quality memories"""
        try:
            # Get low-quality memories (confidence < 0.3, never accessed)
            old_memories = await db.fetch_many(
                "knowledge_base",
                filters={"user_id": user_id},
                order_by="created_at",
                ascending=True,
                limit=200
            )

            pruned = 0
            for mem in old_memories:
                should_prune = (
                    mem.get("confidence_score", 1.0) < 0.3 and
                    mem.get("access_count", 0) == 0
                )
                if should_prune:
                    await db.delete("knowledge_base", {"id": mem["id"]})
                    pruned += 1

            return pruned

        except Exception as e:
            logger.error(f"Memory pruning error: {e}")
            return 0
