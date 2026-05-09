"""
Chain 01: Conversational Chain
Type: ConversationChain + CombinedMemory
Trigger: small_talk | general_query | follow_up
Model: Groq Llama 3.1 70B (quality) / 8B (simple)
Post: Personality Compiler mandatory
Output: Natural language + personality applied
"""
from typing import Any, Dict, Optional
import time
from langchain_groq import ChatGroq
from langchain.memory import ConversationBufferWindowMemory
from langchain.chains import ConversationChain
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.schema import SystemMessage, HumanMessage, AIMessage

from app.config import settings
from app.utils.logging import get_logger
from app.chains.base import BaseChain, ChainType
from app.core.indian_rules import apply_all_rules, get_rules_prompt, get_current_ist_context

logger = get_logger("conversational_chain")


class ConversationalChain(BaseChain):
    """Conversational chain with personality compilation"""
    
    chain_type = ChainType.CONVERSATIONAL
    description = "General conversation with adaptive personality"
    
    def __init__(self):
        super().__init__()
        self._llm = None
        self._chain = None
    
    def _get_llm(self, use_quality_model: bool = False):
        """Get Groq LLM instance"""
        if not settings.groq_api_key:
            raise ValueError("GROQ_API_KEY not configured")
        
        model = "llama-3.1-70b-versatile" if use_quality_model else "llama-3.1-8b-instant"
        
        if self._llm is None:
            self._llm = ChatGroq(
                api_key=settings.groq_api_key,
                model_name=model,
                temperature=0.75,
                max_tokens=1024,
                streaming=False
            )
        return self._llm
    
    def _build_personality_prompt(
        self,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Build personality prompt from context parameters.
        This implements the Personality Compiler.
        """
        if not context:
            return self._default_personality()
        
        # Extract personality parameters
        identity = context.get("identity", {})
        personality_params = identity.get("personality_params", {})
        base = personality_params.get("base", {})
        
        # Get effective parameters considering time and stress
        temporal = context.get("temporal", {})
        emotional = context.get("emotional", {})
        
        effective_temp = base.get("temperature", 0.75)
        effective_sarcasm = base.get("sarcasm", 0.70)
        effective_warmth = base.get("warmth", 0.65)
        effective_directness = base.get("directness", 0.80)
        
        # Apply time modifiers
        period = temporal.get("period", "day")
        if period == "morning":
            effective_directness += 0.15
            effective_warmth += 0.10
        elif period == "evening":
            effective_warmth += 0.10
        
        # Apply stress modifiers
        stress = emotional.get("stress_level", "low")
        if stress == "high":
            effective_sarcasm -= 0.50
            effective_warmth += 0.30
        
        # Clamp values
        effective_temp = max(0.1, min(1.0, effective_temp))
        effective_sarcasm = max(0.0, min(1.0, effective_sarcasm))
        effective_warmth = max(0.0, min(1.0, effective_warmth))
        effective_directness = max(0.0, min(1.0, effective_directness))
        
        # Build personality instruction
        traits = []
        
        if effective_warmth > 0.7:
            traits.append("warm and supportive")
        elif effective_warmth < 0.4:
            traits.append("professional and concise")
        
        if effective_sarcasm > 0.6:
            traits.append("witty with occasional dry humor")
        
        if effective_directness > 0.7:
            traits.append("direct and to-the-point")
        else:
            traits.append("thorough and detailed")
        
        trait_str = ", ".join(traits) if traits else "balanced and adaptive"

        # Get current IST time context
        ist_ctx = get_current_ist_context()

        prompt = f"""{get_rules_prompt()}

---

You are TILLU, a perpetually-active personal AI assistant.
Your personality is {trait_str}.

Key traits:
- You maintain continuity across conversations (you have access to previous context)
- You adapt your tone to the user's current emotional state and time of day
- You are proactive but respectful of boundaries
- You remember facts about the user and reference them naturally

Current context:
- Time (IST): {ist_ctx['current_time_ist']}
- Date: {ist_ctx['current_date_indian']}
- Day: {ist_ctx['day_of_week_hindi']}
- Time of day: {temporal.get('period', 'unknown')}
- User's dominant emotion (7-day): {emotional.get('dominant_emotion', 'neutral')}
- Stress level: {emotional.get('stress_level', 'low')}

Respond as TILLU, with the personality traits described above.
Keep responses concise unless asked for detail."""

        return prompt
    
    def _default_personality(self) -> str:
        """Default personality when no context available"""
        ist_ctx = get_current_ist_context()
        return f"""{get_rules_prompt()}

---

You are TILLU, a perpetually-active personal AI assistant for an Indian user in NCR.
You are warm, slightly witty, and direct. You speak NCR Hinglish naturally.
Current time: {ist_ctx['current_datetime_full']}"""
    
    async def execute(
        self,
        input_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute conversational chain.
        
        Args:
            input_data: Contains 'text' (user input)
            context: Full assembled context from ContextAssembler
            
        Returns:
            Response with personality-applied content
        """
        start_time = time.time()
        
        user_input = input_data.get("text", "")
        if not user_input:
            raise ValueError("No input text provided")
        
        # Determine model based on complexity
        word_count = len(user_input.split())
        use_quality = word_count > 50 or "?" in user_input

        # ── Try Cloudflare AI Gateway first (gpt-5.5-pro) ────────────────────
        if (settings.cf_api_token and settings.cf_account_id
                and not settings.cf_account_id.startswith("YOUR_")):
            try:
                from app.providers.cloudflare_ai import CloudflareAI
                cf_llm = CloudflareAI(model="openai/gpt-5.5-pro", max_tokens=1024, temperature=0.75)
                system_prompt = self._build_personality_prompt(context)
                cf_messages = [{"role": "system", "content": system_prompt}]
                immediate_memory = context.get("immediate_memory", {}) if context else {}
                for turn in immediate_memory.get("recent_turns", [])[-10:]:
                    if turn.get("role") in ("user", "assistant"):
                        cf_messages.append({"role": turn["role"], "content": turn.get("content", "")})
                cf_messages.append({"role": "user", "content": user_input})
                cf_response = await cf_llm.ainvoke(cf_messages)
                latency_ms = int((time.time() - start_time) * 1000)
                return {
                    "response": {
                        "type": "text",
                        "content": apply_all_rules(cf_response.content),
                        "structured_data": {},
                    },
                    "personality_mode": "sharp",
                    "chain": self.chain_type.value,
                    "model": "cf/openai/gpt-5.5-pro",
                    "latency_ms": latency_ms,
                    "tokens_used": 0,
                    "sources": [],
                }
            except Exception as cf_err:
                logger.warning(f"CF AI Gateway failed, falling back to Groq: {cf_err}")

        try:
            # Build personality-compiled system prompt
            system_prompt = self._build_personality_prompt(context)
            
            # Build conversation history from context
            messages = [SystemMessage(content=system_prompt)]
            
            # Add recent conversation turns
            immediate_memory = context.get("immediate_memory", {}) if context else {}
            recent_turns = immediate_memory.get("recent_turns", [])
            
            for turn in recent_turns[-10:]:  # Last 10 turns
                if turn.get("role") == "user":
                    messages.append(HumanMessage(content=turn.get("content", "")))
                elif turn.get("role") == "assistant":
                    messages.append(AIMessage(content=turn.get("content", "")))
            
            # Add current input
            messages.append(HumanMessage(content=user_input))
            
            # Get LLM
            llm = self._get_llm(use_quality_model=use_quality)
            
            # Generate response
            response = await llm.ainvoke(messages)
            
            latency_ms = int((time.time() - start_time) * 1000)

            # Apply Indian rules to response (currency, units, dialect)
            clean_response = apply_all_rules(response.content)

            return {
                "response": {
                    "type": "text",
                    "content": clean_response,
                    "structured_data": {}
                },
                "personality_mode": "warm" if context and context.get("emotional", {}).get("stress_level") == "high" else "sharp",
                "chain": self.chain_type.value,
                "model": "groq-llama-3.1-70b" if use_quality else "groq-llama-3.1-8b",
                "latency_ms": latency_ms,
                "tokens_used": response.response_metadata.get("token_usage", {}).get("total_tokens", 0) if hasattr(response, 'response_metadata') else 0,
                "sources": []
            }
            
        except Exception as e:
            logger.error(f"Conversational chain error: {e}")
            
            # Fallback response
            return {
                "response": {
                    "type": "text",
                    "content": "I'm processing that. Let me get back to you in a moment.",
                    "structured_data": {}
                },
                "personality_mode": "neutral",
                "chain": self.chain_type.value,
                "model": "fallback",
                "latency_ms": int((time.time() - start_time) * 1000),
                "tokens_used": 0,
                "sources": [],
                "error": str(e)
            }
