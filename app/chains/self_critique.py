"""
Chain 07: Self-Critique Chain
Type: LLMChain
Trigger: After every response (async background task)
Model: Groq Llama 3.1 8B (fast, cheap)
Output: Quality scores stored to interactions table
"""
from typing import Any, Dict, Optional
import time
from langchain_groq import ChatGroq
from langchain.schema import HumanMessage

from app.config import settings
from app.chains.base import BaseChain, ChainType
from app.utils.logging import get_logger
from app.utils.database import db

logger = get_logger("self_critique_chain")


class SelfCritiqueChain(BaseChain):
    """
    Self-critique chain that evaluates every response for quality.
    Runs asynchronously after each interaction.
    Stores quality scores back to the interactions table.
    """

    chain_type = ChainType.SELF_CRITIQUE
    description = "Async quality evaluation of every response"

    def __init__(self):
        super().__init__()
        self.llm = None
        if settings.groq_api_key:
            self.llm = ChatGroq(
                api_key=settings.groq_api_key,
                model_name="llama-3.1-8b-instant",
                temperature=0.2,  # Low for consistent scoring
                max_tokens=512
            )

    async def execute(
        self,
        input_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Evaluate a response for quality.

        Args:
            input_data: {
                'user_input': original user message,
                'response': TILLU's response,
                'chain_used': which chain generated it,
                'interaction_id': UUID to update scores
            }
            context: Full assembled context

        Returns:
            Quality scores dict
        """
        start_time = time.time()

        user_input = input_data.get("user_input", "")
        response_text = input_data.get("response", "")
        interaction_id = input_data.get("interaction_id")

        if not self.llm or not response_text:
            return {
                "accuracy": 0.8,
                "helpfulness": 0.8,
                "personality_fit": 0.8,
                "skipped": True
            }

        try:
            prompt = f"""You are a quality evaluator for an AI assistant called TILLU.
Evaluate the following response on three dimensions. Score each 0.0 to 1.0.

User Input: {user_input[:300]}

TILLU Response: {response_text[:500]}

Score these dimensions:
1. Accuracy (0-1): Is the response factually correct and relevant?
2. Helpfulness (0-1): Does it actually help the user?
3. Personality Fit (0-1): Is the tone appropriate and consistent with a warm, direct AI?

Respond ONLY in this exact format:
accuracy: 0.XX
helpfulness: 0.XX
personality_fit: 0.XX
"""

            response = await self.llm.ainvoke([HumanMessage(content=prompt)])
            scores = self._parse_scores(response.content)

            # Store scores back to interaction
            if interaction_id:
                await db.update(
                    "interactions",
                    {
                        "quality_accuracy_score": scores["accuracy"],
                        "quality_helpfulness_score": scores["helpfulness"],
                        "quality_personality_fit_score": scores["personality_fit"]
                    },
                    {"id": interaction_id}
                )

            elapsed_ms = int((time.time() - start_time) * 1000)
            logger.info(
                "Self-critique complete",
                accuracy=scores["accuracy"],
                helpfulness=scores["helpfulness"],
                latency_ms=elapsed_ms
            )

            return {
                "response": {
                    "type": "quality_scores",
                    "content": f"Quality evaluated: accuracy={scores['accuracy']:.2f}",
                    "structured_data": scores
                },
                "personality_mode": "neutral",
                "chain": self.chain_type.value,
                "model": "groq-llama-3.1-8b",
                "latency_ms": elapsed_ms,
                "tokens_used": 0,
                "sources": [],
                **scores
            }

        except Exception as e:
            logger.error(f"Self-critique error: {e}")
            return {
                "accuracy": 0.75,
                "helpfulness": 0.75,
                "personality_fit": 0.75,
                "error": str(e)
            }

    def _parse_scores(self, text: str) -> Dict[str, float]:
        """Parse quality scores from LLM response"""
        import re
        scores = {"accuracy": 0.8, "helpfulness": 0.8, "personality_fit": 0.8}

        patterns = {
            "accuracy": r"accuracy:\s*([\d.]+)",
            "helpfulness": r"helpfulness:\s*([\d.]+)",
            "personality_fit": r"personality_fit:\s*([\d.]+)"
        }

        for key, pattern in patterns.items():
            match = re.search(pattern, text.lower())
            if match:
                try:
                    val = float(match.group(1))
                    scores[key] = max(0.0, min(1.0, val))
                except ValueError:
                    pass

        return scores
