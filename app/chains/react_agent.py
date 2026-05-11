"""
Chain 03: ReAct Tool Agent
Type: LangChain ReAct Agent
Trigger: action_required | real_world_query | multi-step task
Model: Gemini Pro (best tool-use) / OpenRouter fallback
Tools: Full tool registry (32 tools)
Output: Action results + natural language explanation
"""
from typing import Any, Dict, List, Optional
import time
from langchain.agents import AgentExecutor, create_react_agent
from langchain_core.prompts import PromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI

from app.config import settings
from app.chains.base import BaseChain, ChainType
from app.tools.registry import ToolRegistry
from app.utils.logging import get_logger

logger = get_logger("react_agent_chain")


class ReActAgentChain(BaseChain):
    """
    ReAct agent chain for multi-step tasks with tool use
    """
    
    chain_type = ChainType.REACT_AGENT
    description = "Multi-step reasoning with tool execution"
    
    REACT_PROMPT = """You are TILLU, a helpful AI assistant. Answer the following question as best you can.

You have access to the following tools:
{tools}

Use the following format:

Question: the input question you must answer
Thought: you should always think about what to do
Action: the action to take, should be one of [{tool_names}]
Action Input: the input to the action
Observation: the result of the action
... (this Thought/Action/Action Input/Observation can repeat N times)
Thought: I now know the final answer
Final Answer: the final answer to the original input question

Begin!

Question: {input}
Thought:{agent_scratchpad}"""
    
    def __init__(self):
        super().__init__()
        self.llm = None
        self.agent = None
        self._initialize()
    
    def _initialize(self):
        """Initialize LLM and agent"""
        if settings.google_api_key:
            try:
                self.llm = ChatGoogleGenerativeAI(
                    model="gemini-pro",
                    google_api_key=settings.google_api_key,
                    temperature=0.7
                )
            except Exception as e:
                logger.error(f"Failed to initialize Gemini: {e}")
        
        # Fallback to Groq if Gemini not available
        if not self.llm and settings.groq_api_key:
            from langchain_groq import ChatGroq
            self.llm = ChatGroq(
                api_key=settings.groq_api_key,
                model_name="llama-3.1-70b-versatile",
                temperature=0.7
            )
    
    async def execute(
        self,
        input_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute ReAct agent
        
        Args:
            input_data: Contains 'text' (task/query)
            context: Full context with available tools
            
        Returns:
            Results with tool outputs and explanation
        """
        start_time = time.time()
        
        if not self.llm:
            return {
                "response": {
                    "type": "text",
                    "content": "I'm unable to execute tools right now. Let me answer based on my knowledge.",
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
        
        try:
            # Get tools
            tools = ToolRegistry.get_langchain_tools()
            
            if not tools:
                # No tools available, direct answer
                response = await self.llm.ainvoke([
                    ("human", query)
                ])
                
                return {
                    "response": {
                        "type": "text",
                        "content": response.content,
                        "structured_data": {}
                    },
                    "personality_mode": "sharp",
                    "chain": self.chain_type.value,
                    "model": "groq-70b",
                    "latency_ms": int((time.time() - start_time) * 1000),
                    "tokens_used": 0,
                    "sources": []
                }
            
            # Create ReAct agent
            prompt = PromptTemplate.from_template(self.REACT_PROMPT)
            agent = create_react_agent(self.llm, tools, prompt)
            
            # Execute
            agent_executor = AgentExecutor(
                agent=agent,
                tools=tools,
                verbose=False,
                handle_parsing_errors=True,
                max_iterations=5
            )
            
            result = await agent_executor.ainvoke({"input": query})
            
            elapsed_ms = int((time.time() - start_time) * 1000)
            
            # Extract tool outputs
            intermediate_steps = result.get("intermediate_steps", [])
            tool_outputs = []
            for step in intermediate_steps:
                if len(step) >= 2:
                    action, observation = step[0], step[1]
                    tool_outputs.append({
                        "tool": action.tool if hasattr(action, 'tool') else str(action),
                        "input": action.tool_input if hasattr(action, 'tool_input') else str(action),
                        "output": str(observation)[:500]  # Truncate
                    })
            
            return {
                "response": {
                    "type": "action_result",
                    "content": result.get("output", "Task completed."),
                    "structured_data": {
                        "tools_used": len(tool_outputs),
                        "tool_outputs": tool_outputs,
                        "steps_taken": len(intermediate_steps)
                    }
                },
                "personality_mode": "direct",
                "chain": self.chain_type.value,
                "model": "gemini-pro" if settings.google_api_key else "groq-70b",
                "latency_ms": elapsed_ms,
                "tokens_used": 0,
                "sources": []
            }
            
        except Exception as e:
            logger.error(f"ReAct agent error: {e}")
            
            # Fallback to direct LLM
            try:
                response = await self.llm.ainvoke([("human", query)])
                
                return {
                    "response": {
                        "type": "text",
                        "content": response.content,
                        "structured_data": {"error": str(e), "fallback": True}
                    },
                    "personality_mode": "neutral",
                    "chain": self.chain_type.value,
                    "model": "fallback",
                    "latency_ms": int((time.time() - start_time) * 1000),
                    "tokens_used": 0,
                    "sources": []
                }
            except:
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
