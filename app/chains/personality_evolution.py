"""
Chain 09: Personality Evolution Chain
Type: LLMChain
Trigger: Weekly Sunday 22:00 (via daemon / n8n WF-12)
Model: Groq Llama 3.1 70B
Output: Updated personality_params in user_profile
"""
from typing import Any, Dict, Optional
import time
import json
from langchain_groq import ChatGroq
from langchain.schema import HumanMessage, SystemMessage

from app.config import settings
from app.chains.base import BaseChain, ChainType
from app.utils.logging import get_logger
from app.utils.database import db
from app.utils.cache import cache

logger = get_logger("personality_evolution_chain")


class PersonalityEvolutionChain(BaseChain):
    """
    Weekly personality evolution chain.
    Analyzes 7 days of interactions and quality scores to
    evolve TILLU's personality parameters for better fit.

    Parameters evolved:
    - temperature (0-1): Response creativity
    - sarcasm (0-1): Dry humor frequency
    - warmth (0-1): Emotional warmth
    - directness (0-1): Directness vs elaboration
    - humor_frequency (0-1): How often to be funny
    - detail_level (0-1): How detailed responses are
    """

    chain_type = ChainType.PERSONALITY_EVOLUTION
    description = "Weekly personality parameter evolution based on quality feedback"

    def __init__(self):
        super().__init__()
        self.llm = None
        if settings.groq_api_key:
            self.llm = ChatGroq(
                api_key=settings.groq_api_key,
                model_name="llama-3.1-70b-versatile",
                temperature=0.4,
                max_tokens=1024
            )

    async def execute(
        self,
        input_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Evolve personality parameters for a user.

        Args:
            input_data: {'user_id': str}
            context: Optional context

        Returns:
            Updated personality parameters
        """
        start_time = time.time()
        user_id = input_data.get("user_id", "")

        if not user_id:
            return {"error": "user_id required"}

        try:
            # Step 1: Get current personality params
            profile = await db.fetch_one("user_profile", {"user_id": user_id})
            if not profile:
                return {"error": "User profile not found"}

            current_params = profile.get("personality_params", {}).get("base", {
                "temperature": 0.75,
                "sarcasm": 0.70,
                "warmth": 0.65,
                "directness": 0.80,
                "humor_frequency": 0.55,
                "detail_level": 0.60
            })

            # Step 2: Get last 7 days of interactions with quality scores
            interactions = await db.fetch_many(
                "interactions",
                filters={"user_id": user_id},
                order_by="created_at",
                ascending=False,
                limit=200
            )

            # Filter to those with quality scores
            scored = [
                i for i in interactions
                if i.get("quality_accuracy_score") is not None
            ]

            if len(scored) < 5:
                logger.info(f"Not enough scored interactions for evolution: {len(scored)}")
                return {
                    "response": {
                        "type": "text",
                        "content": "Not enough data for personality evolution yet.",
                        "structured_data": {"scored_interactions": len(scored)}
                    },
                    "personality_mode": "neutral",
                    "chain": self.chain_type.value,
                    "model": "skipped",
                    "latency_ms": 0,
                    "tokens_used": 0,
                    "sources": [],
                    "evolved": False
                }

            # Step 3: Calculate average quality scores
            avg_accuracy = sum(i.get("quality_accuracy_score", 0) for i in scored) / len(scored)
            avg_helpfulness = sum(i.get("quality_helpfulness_score", 0) for i in scored) / len(scored)
            avg_personality = sum(i.get("quality_personality_fit_score", 0) for i in scored) / len(scored)

            # Step 4: Analyze patterns to suggest evolution
            new_params = await self._evolve_params(
                current_params, scored, avg_accuracy, avg_helpfulness, avg_personality
            )

            # Step 5: Update user profile
            existing_personality = profile.get("personality_params", {})
            existing_personality["base"] = new_params
            existing_personality["meta"] = {
                "last_evolved": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "evolution_count": existing_personality.get("meta", {}).get("evolution_count", 0) + 1,
                "confidence": avg_personality,
                "adaptation_version": existing_personality.get("meta", {}).get("adaptation_version", 1) + 1
            }

            await db.update(
                "user_profile",
                {"personality_params": existing_personality},
                {"user_id": user_id}
            )

            # Invalidate cache
            await cache.delete(f"user_profile:{user_id}")

            elapsed_ms = int((time.time() - start_time) * 1000)
            logger.info(
                "Personality evolved",
                user_id=user_id,
                avg_quality=avg_personality,
                latency_ms=elapsed_ms
            )

            return {
                "response": {
                    "type": "personality_update",
                    "content": f"Personality evolved based on {len(scored)} interactions.",
                    "structured_data": {
                        "old_params": current_params,
                        "new_params": new_params,
                        "avg_quality_scores": {
                            "accuracy": avg_accuracy,
                            "helpfulness": avg_helpfulness,
                            "personality_fit": avg_personality
                        },
                        "interactions_analyzed": len(scored)
                    }
                },
                "personality_mode": "neutral",
                "chain": self.chain_type.value,
                "model": "groq-llama-3.1-70b",
                "latency_ms": elapsed_ms,
                "tokens_used": 0,
                "sources": [],
                "evolved": True
            }

        except Exception as e:
            logger.error(f"Personality evolution error: {e}")
            return {
                "response": {"type": "text", "content": f"Evolution error: {e}", "structured_data": {}},
                "personality_mode": "neutral",
                "chain": self.chain_type.value,
                "model": "error",
                "latency_ms": int((time.time() - start_time) * 1000),
                "tokens_used": 0,
                "sources": [],
                "evolved": False
            }

    async def _evolve_params(
        self,
        current: Dict,
        interactions: list,
        avg_accuracy: float,
        avg_helpfulness: float,
        avg_personality: float
    ) -> Dict:
        """Evolve personality parameters based on feedback"""
        new_params = dict(current)

        if not self.llm:
            # Simple heuristic evolution without LLM
            return self._heuristic_evolution(current, avg_accuracy, avg_helpfulness, avg_personality)

        try:
            # Sample some interactions for context
            sample = interactions[:10]
            sample_text = "\n".join([
                f"- Intent: {i.get('intent_class', 'unknown')}, "
                f"Personality mode: {i.get('personality_mode', 'unknown')}, "
                f"Quality: acc={i.get('quality_accuracy_score', 0):.2f} "
                f"help={i.get('quality_helpfulness_score', 0):.2f} "
                f"fit={i.get('quality_personality_fit_score', 0):.2f}"
                for i in sample
            ])

            prompt = f"""You are a personality tuning system for an AI assistant called TILLU.

Current personality parameters (all 0.0-1.0):
{json.dumps(current, indent=2)}

Recent interaction quality scores:
- Average accuracy: {avg_accuracy:.2f}
- Average helpfulness: {avg_helpfulness:.2f}
- Average personality fit: {avg_personality:.2f}

Sample interactions:
{sample_text}

Suggest small adjustments (max ±0.10 per parameter) to improve quality.
Focus on personality_fit score - if low, adjust warmth/sarcasm/directness.
If helpfulness is low, increase detail_level.

Return ONLY valid JSON with the same keys as current parameters.
Keep all values between 0.0 and 1.0."""

            response = await self.llm.ainvoke([
                SystemMessage(content="You are a personality tuning system. Return only valid JSON."),
                HumanMessage(content=prompt)
            ])

            text = response.content.strip()
            start = text.find('{')
            end = text.rfind('}') + 1
            if start >= 0 and end > start:
                suggested = json.loads(text[start:end])
                # Validate and clamp all values
                for key in current:
                    if key in suggested:
                        val = float(suggested[key])
                        # Max change of 0.10 per evolution
                        delta = val - current.get(key, 0.5)
                        delta = max(-0.10, min(0.10, delta))
                        new_params[key] = max(0.0, min(1.0, current.get(key, 0.5) + delta))

        except Exception as e:
            logger.error(f"LLM evolution error: {e}")
            return self._heuristic_evolution(current, avg_accuracy, avg_helpfulness, avg_personality)

        return new_params

    def _heuristic_evolution(
        self,
        current: Dict,
        avg_accuracy: float,
        avg_helpfulness: float,
        avg_personality: float
    ) -> Dict:
        """Simple heuristic evolution without LLM"""
        new_params = dict(current)

        # If personality fit is low, adjust warmth and reduce sarcasm
        if avg_personality < 0.7:
            new_params["warmth"] = min(1.0, current.get("warmth", 0.65) + 0.05)
            new_params["sarcasm"] = max(0.0, current.get("sarcasm", 0.70) - 0.05)

        # If helpfulness is low, increase detail
        if avg_helpfulness < 0.7:
            new_params["detail_level"] = min(1.0, current.get("detail_level", 0.60) + 0.05)

        return new_params
