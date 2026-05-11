"""
Chain 03: ReAct Tool Agent (Simplified)
Type: LLM-based reasoning with tool descriptions
Trigger: action_required | real_world_query | multi-step task
Model: Groq / Cerebras fallback
Tools: Tool registry (read-only for now)
Output: Reasoning + natural language explanation
"""
from typing import Any, Dict, List, Optional
import time
from langchain_core.prompts import PromptTemplate

from app.config import settings
from app.chains.base import BaseChain, ChainType
from app.tools.registry import ToolRegistry
from app.utils.logging import get_logger

logger = get_logger("react_agent_chain")


class ReActAgentChain(BaseChain):
    """
    Simplified ReAct-style chain for multi-step reasoning
    Uses LLM to reason about tasks (tool execution handled separately)
    """
    
    chain_type = ChainType.REACT_AGENT
    description = "Multi-step reasoning with tool awareness"
    
    REASONING_PROMPT = """You are TILLU, a helpful AI assistant with access to various tools.

Available tools:
{tools_description}

For the user's query, provide:
1. Your reasoning about what needs to be done
2. Which tools would be helpful (if any)
3. Your answer or recommendation

Query: {input}

Provide a clear, helpful response."""
    
    def __init__(self):
        super().__init__()
        self.llm = None
        self._initialize()
    
    def _initialize(self):
        """Initialize LLM"""
        # Try Groq first (most reliable)
        if settings.groq_api_key:
            try:
                from langchain_groq import ChatGroq
                self.llm = ChatGroq(
                    api_key=settings.groq_api_key,
                    model_name="llama-3.1-70b-versatile",
                    temperature=0.7
                )
                logger.info("Groq LLM initialized for ReAct chain")
                return
            except Exception as e:
                logger.warning(f"Failed to initialize Groq: {e}")
        
        # Try Cerebras as fallback
        if settings.cerebras_api_key:
            try:
                from langchain_cerebras import ChatCerebras
                self.llm = ChatCerebras(
                    api_key=settings.cerebras_api_key,
                    model_name="llama-3.3-70b",
                    temperature=0.7
                )
                logger.info("Cerebras LLM initialized for ReAct chain")
                return
            except Exception as e:
                logger.warning(f"Failed to initialize Cerebras: {e}")
        
        logger.warning("No LLM available for ReAct chain - will use fallback")
    
    async def execute(
        self,
        input_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute reasoning chain
        
        Args:
            input_data: Contains 'text' (task/query)
            context: Full context
            
        Returns:
            Results with reasoning and explanation
        """
        start_time = time.time()
        
        if not self.llm:
            return {
                "response": {
                    "type": "text",
                    "content": "I'm unable to process your request right now.",
                    "structured_data": {}
                },
                "personality_mode": "neutral",
                "chain": self.chain_type.value,
                "model": "unavailable",
                "latency_ms": int((time.time() - start_time) * 1000),
                "tokens_used": 0,
                "sources": []
            }
        
        query = input_data.get("text", "")
        
        try:
            # Get tool descriptions
            tools = ToolRegistry.get_all()
            tools_description = "\n".join([
                f"- {tool.metadata.name}: {tool.metadata.description}"
                for tool in tools[:10]  # Limit to first 10 tools
            ])
            
            # Create prompt
            prompt = PromptTemplate.from_template(self.REASONING_PROMPT)
            formatted_prompt = prompt.format(
                tools_description=tools_description,
                input=query
            )
            
            # Get response from LLM
            response = await self.llm.ainvoke([
                ("human", formatted_prompt)
            ])
            
            elapsed_ms = int((time.time() - start_time) * 1000)
            
            return {
                "response": {
                    "type": "reasoning",
                    "content": response.content,
                    "structured_data": {
                        "tools_available": len(tools),
                        "reasoning_type": "multi_step"
                    }
                },
                "personality_mode": "analytical",
                "chain": self.chain_type.value,
                "model": "groq-70b",
                "latency_ms": elapsed_ms,
                "tokens_used": 0,
                "sources": []
            }
            
        except Exception as e:
            logger.error(f"ReAct chain error: {e}")
            
            # Fallback to direct LLM
            try:
                response = await self.llm.ainvoke([("human", query)])
                
                return {
                    "response": {
                        "type": "text",
                        "content": response.content,
                        "structured_data": {"fallback": True}
                    },
                    "personality_mode": "neutral",
                    "chain": self.chain_type.value,
                    "model": "fallback",
                    "latency_ms": int((time.time() - start_time) * 1000),
                    "tokens_used": 0,
                    "sources": []
                }
            except Exception as fallback_error:
                logger.error(f"Fallback error: {fallback_error}")
                return {
                    "response": {
                        "type": "text",
                        "content": "I encountered an error while processing your request.",
                        "structured_data": {"error": str(e)}
                    },
                    "personality_mode": "neutral",
                    "chain": self.chain_type.value,
                    "model": "error",
                    "latency_ms": int((time.time() - start_time) * 1000),
                    "tokens_used": 0,
                    "sources": []
                }
