"""
LangChain Chain Registry — lazy imports to avoid loading all providers at startup.
"""
from .base import ChainRegistry, BaseChain, ChainType
from app.utils.logging import get_logger

logger = get_logger("chains")

__all__ = [
    "ChainRegistry",
    "BaseChain", 
    "ChainType",
    "ConversationalChain",
    "ResearchChain",
    "ReActAgentChain",
    "AnalysisChain",
    "ContextAssembler",
    "EmpathyChain",
    "SelfCritiqueChain",
    "MemoryConsolidationChain",
    "PersonalityEvolutionChain",
    "AmbientMonitoringChain",
]


def __getattr__(name: str):
    try:
        if name == "ConversationalChain":
            from .conversational import ConversationalChain
            return ConversationalChain
        if name == "ResearchChain":
            from .research import ResearchChain
            return ResearchChain
        if name == "ReActAgentChain":
            from .react_agent import ReActAgentChain
            return ReActAgentChain
        if name == "AnalysisChain":
            from .analysis import AnalysisChain
            return AnalysisChain
        if name == "ContextAssembler":
            from .context_assembler import ContextAssembler
            return ContextAssembler
        if name == "EmpathyChain":
            from .empathy import EmpathyChain
            return EmpathyChain
        if name == "SelfCritiqueChain":
            from .self_critique import SelfCritiqueChain
            return SelfCritiqueChain
        if name == "MemoryConsolidationChain":
            from .memory_consolidation import MemoryConsolidationChain
            return MemoryConsolidationChain
        if name == "PersonalityEvolutionChain":
            from .personality_evolution import PersonalityEvolutionChain
            return PersonalityEvolutionChain
        if name == "AmbientMonitoringChain":
            from .ambient_monitoring import AmbientMonitoringChain
            return AmbientMonitoringChain
        raise AttributeError(f"module 'app.chains' has no attribute {name!r}")
    except ImportError as e:
        logger.error(f"Failed to import chain {name}: {str(e)}")
        raise AttributeError(f"Failed to import chain {name}: {str(e)}")
