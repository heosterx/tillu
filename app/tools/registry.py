"""
Tool Registry
Central registry for all available tools.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Type
from dataclasses import dataclass
from app.utils.logging import get_logger

logger = get_logger("tools")


@dataclass
class ToolMetadata:
    """Metadata for a tool"""
    name: str
    description: str
    parameters: Dict[str, Any]
    requires_auth: bool = False
    rate_limited: bool = True


class BaseTool(ABC):
    """Base class for all tools"""
    
    metadata: ToolMetadata
    
    def __init__(self):
        self.logger = get_logger(f"tool.{self.metadata.name}")
    
    @abstractmethod
    async def execute(self, **kwargs) -> Dict[str, Any]:
        """Execute the tool with given parameters"""
        pass
    
    def to_langchain_tool(self):
        """Convert to LangChain tool format"""
        from langchain.tools import Tool
        
        return Tool(
            name=self.metadata.name,
            description=self.metadata.description,
            func=lambda **kwargs: self.execute(**kwargs),
            coroutine=self.execute
        )


class ToolRegistry:
    """Registry for all available tools"""
    
    _tools: Dict[str, BaseTool] = {}
    
    @classmethod
    def register(cls, tool_instance: BaseTool):
        """Register a tool instance"""
        name = tool_instance.metadata.name
        cls._tools[name] = tool_instance
        logger.info(f"Registered tool: {name}")
    
    @classmethod
    def get(cls, name: str) -> Optional[BaseTool]:
        """Get a tool by name"""
        return cls._tools.get(name)
    
    @classmethod
    def list_tools(cls) -> List[ToolMetadata]:
        """List all registered tools"""
        return [tool.metadata for tool in cls._tools.values()]
    
    @classmethod
    def get_all_tools(cls) -> List[BaseTool]:
        """Get all tool instances"""
        return list(cls._tools.values())
    
    @classmethod
    def get_langchain_tools(cls) -> List[Any]:
        """Get all tools as LangChain Tool objects"""
        return [tool.to_langchain_tool() for tool in cls._tools.values()]
