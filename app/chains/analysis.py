"""
Chain 04: Analysis Chain
Type: LLMChain + Pydantic output parser
Trigger: pattern_query | data_analysis | structured_request
Model: Cerebras Llama 3.3 70B
Output: Structured JSON stored to Supabase + summary
"""
from typing import Any, Dict, Optional
import time
import json
from pydantic import BaseModel, Field
from langchain.output_parsers import PydanticOutputParser
from langchain.prompts import ChatPromptTemplate
from langchain_cerebras import ChatCerebras
from langchain_groq import ChatGroq

from app.config import settings
from app.chains.base import BaseChain, ChainType
from app.utils.logging import get_logger
from app.utils.database import db

logger = get_logger("analysis_chain")


class AnalysisOutput(BaseModel):
    """Structured output for analysis"""
    summary: str = Field(description="Executive summary of the analysis")
    key_findings: list = Field(description="List of key findings")
    patterns_identified: list = Field(description="Patterns or trends found")
    recommendations: list = Field(description="Recommendations based on analysis")
    confidence_score: float = Field(description="Confidence in analysis (0-1)")


class AnalysisChain(BaseChain):
    """
    Analysis chain for structured data analysis and pattern recognition
    Produces JSON output stored to Supabase
    """
    
    chain_type = ChainType.ANALYSIS
    description = "Structured analysis with JSON output"
    
    def __init__(self):
        super().__init__()
        self.llm = None
        self.parser = PydanticOutputParser(pydantic_object=AnalysisOutput)
        self._initialize()
    
    def _initialize(self):
        """Initialize LLM"""
        if settings.cerebras_api_key:
            try:
                self.llm = ChatCerebras(
                    api_key=settings.cerebras_api_key,
                    model_name="llama-3.3-70b",
                    temperature=0.3  # Lower for structured output
                )
            except Exception as e:
                logger.error(f"Failed to initialize Cerebras: {e}")
        
        # Fallback to Groq
        if not self.llm and settings.groq_api_key:
            self.llm = ChatGroq(
                api_key=settings.groq_api_key,
                model_name="llama-3.1-70b-versatile",
                temperature=0.3
            )
    
    async def execute(
        self,
        input_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute analysis chain
        
        Args:
            input_data: Contains 'text' (analysis query)
            context: Full context with data
            
        Returns:
            Structured analysis results
        """
        start_time = time.time()
        
        if not self.llm:
            return {
                "response": {
                    "type": "text",
                    "content": "Analysis service unavailable. I'll provide a qualitative assessment.",
                    "structured_data": {}
                },
                "personality_mode": "neutral",
                "chain": self.chain_type.value,
                "model": "fallback",
                "latency_ms": int((time.time() - start_time) * 1000),
                "tokens_used": 0,
                "sources": []
            }
        
        query = input_data.get("text", "")
        user_id = context.get("identity", {}).get("user_profile", {}).get("user_id", "unknown")
        
        try:
            # Get relevant data from context
            memory_data = context.get("semantic_memory", {})
            tasks_data = context.get("situational", {})
            
            # Build prompt with format instructions
            format_instructions = self.parser.get_format_instructions()
            
            prompt = ChatPromptTemplate.from_messages([
                ("system", f"""You are an analytical AI. Analyze the user's query and provide structured output.

{format_instructions}

Use the provided context data to inform your analysis. Be objective and data-driven."""),
                ("human", f"""Analyze the following:

Query: {query}

Context Data:
- Knowledge items: {len(memory_data.get('knowledge_items', []))} relevant items
- Tasks: {tasks_data.get('active_goals_count', 0)} active goals
- Pending events: {tasks_data.get('event_count', 0)}

Provide a thorough analysis following the format above.""")
            ])
            
            # Generate analysis
            messages = prompt.format_messages(query=query)
            response = await self.llm.ainvoke(messages)
            
            # Parse output
            try:
                parsed = self.parser.parse(response.content)
                structured_output = parsed.dict()
            except Exception as e:
                logger.error(f"Parse error: {e}")
                # Fallback: extract manually
                structured_output = {
                    "summary": response.content[:500],
                    "key_findings": [],
                    "patterns_identified": [],
                    "recommendations": [],
                    "confidence_score": 0.7
                }
            
            # Store analysis to knowledge base
            analysis_record = {
                "user_id": user_id,
                "content": json.dumps(structured_output, indent=2),
                "content_type": "analysis",
                "category": "data_analysis",
                "source_type": "analysis_chain",
                "confidence_score": structured_output.get("confidence_score", 0.7),
                "quality_score": 0.85
            }
            
            try:
                await db.insert("knowledge_base", analysis_record)
            except Exception as e:
                logger.error(f"Failed to store analysis: {e}")
            
            elapsed_ms = int((time.time() - start_time) * 1000)
            
            return {
                "response": {
                    "type": "analysis",
                    "content": structured_output.get("summary", "Analysis complete."),
                    "structured_data": structured_output
                },
                "personality_mode": "direct",  # Analysis is factual
                "chain": self.chain_type.value,
                "model": "cerebras-70b" if settings.cerebras_api_key else "groq-70b",
                "latency_ms": elapsed_ms,
                "tokens_used": 0,
                "sources": []
            }
            
        except Exception as e:
            logger.error(f"Analysis chain error: {e}")
            return {
                "response": {
                    "type": "text",
                    "content": f"I encountered an error during analysis: {str(e)}",
                    "structured_data": {}
                },
                "personality_mode": "neutral",
                "chain": self.chain_type.value,
                "model": "error",
                "latency_ms": int((time.time() - start_time) * 1000),
                "tokens_used": 0,
                "sources": []
            }
