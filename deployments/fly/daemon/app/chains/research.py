"""
Chain 02: Research Chain
Type: LangGraph StateGraph
Trigger: research_request | deep_analysis
Nodes: Plan → Search → Scrape → Extract → Synthesize → Critique → Store
Model: Cerebras (synthesis) + Groq (planning/critique)
Output: Structured research object + executive summary
"""
from typing import Any, Dict, Optional
import time
from app.chains.base import BaseChain, ChainType
from app.langgraph.research_agent import create_research_agent
from app.utils.logging import get_logger

logger = get_logger("research_chain")


class ResearchChain(BaseChain):
    """
    Research chain using LangGraph agent
    Executes full 7-node research workflow
    """
    
    chain_type = ChainType.RESEARCH
    description = "Deep research with multi-source analysis and synthesis"
    
    def __init__(self):
        super().__init__()
        self.agent = create_research_agent()
    
    async def execute(
        self,
        input_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute research chain
        
        Args:
            input_data: Contains 'text' (research query)
            context: Full assembled context
            
        Returns:
            Research results with synthesis and sources
        """
        start_time = time.time()
        
        query = input_data.get("text", "")
        user_id = context.get("identity", {}).get("user_profile", {}).get("user_id", "unknown")
        
        logger.info("Starting research", query=query[:100])
        
        try:
            # Execute research agent
            result = await self.agent.execute(task=query, user_id=user_id)
            
            elapsed_ms = int((time.time() - start_time) * 1000)
            
            if result.get("success"):
                return {
                    "response": {
                        "type": "research",
                        "content": result.get("executive_summary", result.get("synthesis", "")[:500]),
                        "structured_data": {
                            "full_synthesis": result.get("synthesis"),
                            "sources": result.get("sources", []),
                            "entities": result.get("entities", []),
                            "iterations": result.get("iterations", 1),
                            "research_id": result.get("research_id")
                        }
                    },
                    "personality_mode": "direct",  # Research is direct/factual
                    "chain": self.chain_type.value,
                    "model": "cerebras-70b+groq-8b",
                    "latency_ms": elapsed_ms,
                    "tokens_used": 0,  # Would track from LLM calls
                    "sources": result.get("sources", [])
                }
            else:
                return {
                    "response": {
                        "type": "text",
                        "content": f"I couldn't complete the research. Error: {result.get('error', 'Unknown error')}",
                        "structured_data": {}
                    },
                    "personality_mode": "neutral",
                    "chain": self.chain_type.value,
                    "model": "error",
                    "latency_ms": elapsed_ms,
                    "tokens_used": 0,
                    "sources": [],
                    "error": result.get("error")
                }
                
        except Exception as e:
            logger.error(f"Research chain error: {e}")
            return {
                "response": {
                    "type": "text",
                    "content": "I encountered an error while researching. Let me try a simpler approach.",
                    "structured_data": {}
                },
                "personality_mode": "neutral",
                "chain": self.chain_type.value,
                "model": "error",
                "latency_ms": int((time.time() - start_time) * 1000),
                "tokens_used": 0,
                "sources": [],
                "error": str(e)
            }
