"""
Base chain class and registry
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from enum import Enum
from app.utils.logging import get_logger

logger = get_logger("chains")


class ChainType(str, Enum):
    """Types of chains in the registry"""
    CONVERSATIONAL = "conversational"
    RESEARCH = "research"
    REACT_AGENT = "react_agent"
    ANALYSIS = "analysis"
    INTELLIGENCE_COMPILER = "intelligence_compiler"
    EMPATHY = "empathy"
    SELF_CRITIQUE = "self_critique"
    MEMORY_CONSOLIDATION = "memory_consolidation"
    PERSONALITY_EVOLUTION = "personality_evolution"
    AMBIENT_MONITORING = "ambient_monitoring"


class BaseChain(ABC):
    """Base class for all TILLU chains"""
    
    chain_type: ChainType
    description: str
    
    def __init__(self):
        self.logger = get_logger(f"chain.{self.chain_type.value}")
    
    @abstractmethod
    async def execute(
        self,
        input_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute the chain with given input and context.
        
        Args:
            input_data: The input to process
            context: Assembled context from ContextAssembler
            
        Returns:
            Dictionary containing response and metadata
        """
        pass
    
    async def pre_process(
        self,
        input_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Pre-process input before execution"""
        return input_data
    
    async def post_process(
        self,
        result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Post-process result after execution"""
        return result


class ChainRegistry:
    """
    Registry for all available chains.
    Provides chain selection based on intent and context.
    """
    
    _chains: Dict[ChainType, BaseChain] = {}
    
    @classmethod
    def register(cls, chain_type: ChainType, chain: BaseChain):
        """Register a chain"""
        cls._chains[chain_type] = chain
        logger.info(f"Registered chain: {chain_type.value}")
    
    @classmethod
    def get(cls, chain_type: ChainType) -> Optional[BaseChain]:
        """Get a chain by type"""
        return cls._chains.get(chain_type)
    
    @classmethod
    def select_chain(
        cls,
        intent_class: str,
        input_text: str,
        context: Optional[Dict[str, Any]] = None
    ) -> ChainType:
        """
        Select appropriate chain based on intent classification.
        
        Args:
            intent_class: Classified intent from HF model
            input_text: Raw input text
            context: Additional context
            
        Returns:
            Selected chain type
        """
        intent_chain_map = {
            # Direct mappings
            "small_talk": ChainType.CONVERSATIONAL,
            "general_query": ChainType.CONVERSATIONAL,
            "follow_up": ChainType.CONVERSATIONAL,
            
            "research_request": ChainType.RESEARCH,
            "deep_analysis": ChainType.RESEARCH,
            
            "action_required": ChainType.REACT_AGENT,
            "real_world_query": ChainType.REACT_AGENT,
            "multi_step_task": ChainType.REACT_AGENT,
            
            "pattern_query": ChainType.ANALYSIS,
            "data_analysis": ChainType.ANALYSIS,
            "structured_request": ChainType.ANALYSIS,
            
            # Emotional states
            "distress": ChainType.EMPATHY,
            "sadness": ChainType.EMPATHY,
            "high_stress": ChainType.EMPATHY,
        }
        
        chain_type = intent_chain_map.get(intent_class, ChainType.CONVERSATIONAL)
        logger.info(f"Selected chain: {chain_type.value} for intent: {intent_class}")
        return chain_type
    
    @classmethod
    async def execute(
        cls,
        chain_type: ChainType,
        input_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute a chain by type.
        
        Args:
            chain_type: Type of chain to execute
            input_data: Input data for the chain
            context: Assembled context
            
        Returns:
            Chain execution result
        """
        chain = cls.get(chain_type)
        if not chain:
            logger.error(f"Chain not found: {chain_type.value}")
            raise ValueError(f"Unknown chain type: {chain_type}")
        
        # Pre-process
        input_data = await chain.pre_process(input_data)
        
        # Execute
        result = await chain.execute(input_data, context)
        
        # Post-process
        result = await chain.post_process(result)
        
        return result
    
    @classmethod
    def register_all(cls):
        """Register all available chains (call at startup)"""
        # Import here to avoid circular imports
        from .conversational import ConversationalChain
        from .research import ResearchChain
        from .react_agent import ReActAgentChain
        from .analysis import AnalysisChain
        from .empathy import EmpathyChain
        from .self_critique import SelfCritiqueChain
        from .memory_consolidation import MemoryConsolidationChain
        from .personality_evolution import PersonalityEvolutionChain
        from .ambient_monitoring import AmbientMonitoringChain
        
        cls.register(ChainType.CONVERSATIONAL, ConversationalChain())
        cls.register(ChainType.RESEARCH, ResearchChain())
        cls.register(ChainType.REACT_AGENT, ReActAgentChain())
        cls.register(ChainType.ANALYSIS, AnalysisChain())
        cls.register(ChainType.EMPATHY, EmpathyChain())
        cls.register(ChainType.SELF_CRITIQUE, SelfCritiqueChain())
        cls.register(ChainType.MEMORY_CONSOLIDATION, MemoryConsolidationChain())
        cls.register(ChainType.PERSONALITY_EVOLUTION, PersonalityEvolutionChain())
        cls.register(ChainType.AMBIENT_MONITORING, AmbientMonitoringChain())
        
        logger.info("All chains registered successfully")
