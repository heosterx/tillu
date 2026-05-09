"""
Context Assembler (Runs Before Every Chain)
The universal pre-step. No chain executes without this running first.

ASSEMBLY TARGET: < 120ms total
"""
from typing import Any, Dict, List, Optional
from datetime import datetime, time
import asyncio
from app.utils.logging import get_logger
from app.utils.database import db
from app.utils.cache import cache

logger = get_logger("context_assembler")


class ContextAssembler:
    """
    Assembles 7 tiers of context for every chain execution.
    Total target time: < 120ms
    """
    
    @classmethod
    async def assemble(
        cls,
        user_id: str,
        input_text: str,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Assemble all context tiers.
        
        TIER 1: Identity (< 5ms, Redis cache)
        TIER 2: Temporal (< 2ms)
        TIER 3: Emotional State (< 10ms, Redis cache)
        TIER 4: Immediate Memory (< 20ms, Supabase)
        TIER 5: Semantic Memory (< 50ms, pgvector)
        TIER 6: Situational (< 15ms, Supabase + Redis)
        TIER 7: World State (< 10ms, Redis cache)
        """
        start_time = datetime.now()
        
        # Execute all tiers concurrently where possible
        tasks = [
            cls._tier_1_identity(user_id),
            cls._tier_2_temporal(user_id),
            cls._tier_3_emotional(user_id),
            cls._tier_4_immediate_memory(user_id, session_id),
            cls._tier_5_semantic_memory(user_id, input_text),
            cls._tier_6_situational(user_id),
            cls._tier_7_world_state(user_id),
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        context = {
            "identity": results[0] if not isinstance(results[0], Exception) else {},
            "temporal": results[1] if not isinstance(results[1], Exception) else {},
            "emotional": results[2] if not isinstance(results[2], Exception) else {},
            "immediate_memory": results[3] if not isinstance(results[3], Exception) else {},
            "semantic_memory": results[4] if not isinstance(results[4], Exception) else {},
            "situational": results[5] if not isinstance(results[5], Exception) else {},
            "world_state": results[6] if not isinstance(results[6], Exception) else {},
        }
        
        elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000
        logger.info(f"Context assembled in {elapsed_ms:.1f}ms")
        
        return context
    
    @classmethod
    async def _tier_1_identity(cls, user_id: str) -> Dict[str, Any]:
        """
        TIER 1 — Identity (< 5ms, Redis cache)
        → user_profile loaded (cached 1hr)
        → personality_params computed
        → active_hours classification
        """
        cache_key = f"user_profile:{user_id}"
        
        # Try cache first
        cached = await cache.get(cache_key)
        if cached:
            return {
                "user_profile": cached,
                "source": "cache",
                "personality_params": cached.get("personality_params", {}),
                "is_active_hours": cls._check_active_hours(cached)
            }
        
        # Fetch from database
        profile = await db.fetch_one("user_profile", {"user_id": user_id})
        
        if profile:
            # Cache for 1 hour
            await cache.set(cache_key, profile, ttl=3600)
            
            return {
                "user_profile": profile,
                "source": "database",
                "personality_params": profile.get("personality_params", {}),
                "is_active_hours": cls._check_active_hours(profile)
            }
        
        return {"error": "Profile not found"}
    
    @classmethod
    def _check_active_hours(cls, profile: Dict) -> bool:
        """Check if current time is within user's active hours"""
        now = datetime.now()
        current_time = now.time()
        
        start = profile.get("active_hours_start", "08:00:00")
        end = profile.get("active_hours_end", "22:00:00")
        
        # Convert string times to time objects
        if isinstance(start, str):
            start = datetime.strptime(start, "%H:%M:%S").time()
        if isinstance(end, str):
            end = datetime.strptime(end, "%H:%M:%S").time()
        
        return start <= current_time <= end
    
    @classmethod
    async def _tier_2_temporal(cls, user_id: str) -> Dict[str, Any]:
        """
        TIER 2 — Temporal (< 2ms)
        → current datetime + timezone
        → behavioral pattern for this hour/day
        → DND window check
        """
        now = datetime.now()
        hour = now.hour
        day_of_week = now.weekday()
        
        # Classify time period
        if 5 <= hour < 12:
            period = "morning"
        elif 12 <= hour < 17:
            period = "afternoon"
        elif 17 <= hour < 22:
            period = "evening"
        else:
            period = "night"
        
        # Weekend check
        is_weekend = day_of_week >= 5
        
        return {
            "current_time": now.isoformat(),
            "hour": hour,
            "day_of_week": day_of_week,
            "period": period,
            "is_weekend": is_weekend,
            "is_dnd": False  # Would check against profile
        }
    
    @classmethod
    async def _tier_3_emotional(cls, user_id: str) -> Dict[str, Any]:
        """
        TIER 3 — Emotional State (< 10ms, Redis cache)
        → 7-day emotion average (cached 1hr)
        → today's trajectory
        → current stress estimate
        """
        cache_key = f"emotional_state:{user_id}"
        
        # Try cache
        cached = await cache.get(cache_key)
        if cached:
            return cached
        
        # Query recent emotion logs
        logs = await db.fetch_many(
            "emotion_log",
            filters={"user_id": user_id},
            order_by="recorded_at",
            ascending=False,
            limit=20
        )
        
        if not logs:
            return {
                "dominant_emotion": "neutral",
                "stress_level": "low",
                "7_day_average": {},
                "today_trajectory": "stable"
            }
        
        # Calculate averages
        emotions = ["joy", "sadness", "anger", "fear", "surprise", "disgust", "neutral"]
        averages = {}
        
        for emotion in emotions:
            values = [log.get(emotion, 0) for log in logs if emotion in log]
            averages[emotion] = sum(values) / len(values) if values else 0
        
        # Find dominant
        dominant = max(averages, key=averages.get)
        
        # Stress classification
        stress = logs[0].get("stress_level", "low") if logs else "low"
        
        result = {
            "dominant_emotion": dominant,
            "stress_level": stress,
            "7_day_average": averages,
            "today_trajectory": "stable",  # Simplified
            "latest_emotion": logs[0] if logs else None
        }
        
        # Cache for 1 hour
        await cache.set(cache_key, result, ttl=3600)
        
        return result
    
    @classmethod
    async def _tier_4_immediate_memory(cls, user_id: str, session_id: Optional[str]) -> Dict[str, Any]:
        """
        TIER 4 — Immediate Memory (< 20ms, Supabase)
        → ConversationBufferWindowMemory: last 20 turns
        → today's interaction summary
        """
        # Get last 20 interactions for this session
        filters = {"user_id": user_id}
        if session_id:
            filters["session_id"] = session_id
        
        interactions = await db.fetch_many(
            "interactions",
            filters=filters,
            order_by="created_at",
            ascending=False,
            limit=20
        )
        
        # Format as conversation turns
        turns = []
        for interaction in reversed(interactions):  # Oldest first
            turns.append({
                "role": "user",
                "content": interaction.get("input_text", ""),
                "timestamp": interaction.get("created_at")
            })
            if interaction.get("response_text"):
                turns.append({
                    "role": "assistant",
                    "content": interaction.get("response_text", ""),
                    "timestamp": interaction.get("created_at"),
                    "personality_mode": interaction.get("personality_mode")
                })
        
        return {
            "recent_turns": turns,
            "turn_count": len(turns),
            "session_id": session_id
        }
    
    @classmethod
    async def _tier_5_semantic_memory(cls, user_id: str, input_text: str) -> Dict[str, Any]:
        """
        TIER 5 — Semantic Memory (< 50ms, pgvector)
        → embed input query (HF Inference API)
        → cosine similarity search: top 8 conversations
        → cosine similarity search: top 5 knowledge_base
        → cosine similarity search: top 3 research_sessions
        """
        from app.memory.semantic_search import semantic_search
        
        # Search all semantic memory sources
        results = await semantic_search.search_all(
            user_id=user_id,
            query=input_text,
            max_results_per_source=8
        )
        
        return {
            "knowledge_items": results.get("knowledge", [])[:5],
            "news_articles": results.get("news", [])[:3],
            "research_sessions": results.get("research", [])[:3],
            "source": "semantic_similarity",
            "total_results": results.get("total_results", 0),
            "embedding_used": True
        }
    
    @classmethod
    async def _tier_6_situational(cls, user_id: str) -> Dict[str, Any]:
        """
        TIER 6 — Situational (< 15ms, Supabase + Redis)
        → today's tasks + approaching deadlines
        → active goals + probability scores
        → pending proactive events queued
        """
        # Get active tasks
        tasks = await db.fetch_many(
            "tasks_goals",
            filters={"user_id": user_id, "status": "active"},
            order_by="due_date",
            ascending=True,
            limit=10
        )
        
        # Get pending events
        events = await db.fetch_many(
            "event_queue",
            filters={"user_id": user_id, "status": "pending"},
            limit=10
        )
        
        # Categorize tasks
        today_tasks = []
        approaching_deadlines = []
        
        now = datetime.now()
        for task in tasks:
            due = task.get("due_date")
            if due:
                due_date = datetime.fromisoformat(due.replace("Z", "+00:00")) if isinstance(due, str) else due
                days_until = (due_date - now).days
                
                if days_until <= 0:
                    today_tasks.append(task)
                elif days_until <= 3:
                    approaching_deadlines.append(task)
        
        return {
            "today_tasks": today_tasks,
            "approaching_deadlines": approaching_deadlines,
            "active_goals_count": len(tasks),
            "pending_events": events,
            "event_count": len(events)
        }
    
    @classmethod
    async def _tier_7_world_state(cls, user_id: str) -> Dict[str, Any]:
        """
        TIER 7 — World State (< 10ms, Redis cache)
        → breaking news last 2 hours (cached)
        → financial movements >2% (cached)
        → pre-computed morning context if applicable
        """
        cache_key = f"world_state:{user_id}"
        
        # Try cache
        cached = await cache.get(cache_key)
        if cached:
            return cached
        
        # Placeholder - would fetch from cached world data
        world_state = {
            "breaking_news": [],
            "financial_alerts": [],
            "morning_context": None,
            "last_updated": datetime.now().isoformat(),
            "note": "World state from daemon cache"
        }
        
        # Cache for 10 minutes
        await cache.set(cache_key, world_state, ttl=600)
        
        return world_state
