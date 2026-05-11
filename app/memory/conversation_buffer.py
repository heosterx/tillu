"""
ConversationBuffer - In-memory conversation buffer for active sessions
"""
from typing import List, Dict, Any, Optional
from collections import deque
from datetime import datetime
from app.utils.logging import get_logger

logger = get_logger("conversation_buffer")


class ConversationBuffer:
    """
    In-memory buffer for active conversation sessions.
    Provides O(1) access to recent messages.
    """
    
    _buffers: Dict[str, deque] = {}  # session_id -> deque of messages
    _max_size: int = 100
    
    @classmethod
    def add_message(
        cls,
        session_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Add a message to the buffer.
        
        Args:
            session_id: Unique session identifier
            role: "user" or "assistant"
            content: Message content
            metadata: Optional metadata (emotion, timestamp, etc.)
        """
        if session_id not in cls._buffers:
            cls._buffers[session_id] = deque(maxlen=cls._max_size)
        
        message = {
            "role": role,
            "content": content,
            "timestamp": metadata.get("timestamp") if metadata else datetime.now().isoformat(),
            "metadata": metadata or {}
        }
        
        cls._buffers[session_id].append(message)
        logger.debug(f"Added message to buffer", session_id=session_id, role=role)
    
    @classmethod
    def get_recent(
        cls,
        session_id: str,
        n: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Get n most recent messages from buffer.
        
        Args:
            session_id: Session identifier
            n: Number of messages to retrieve
            
        Returns:
            List of recent messages (oldest first)
        """
        if session_id not in cls._buffers:
            return []
        
        buffer = cls._buffers[session_id]
        # Get last n messages, reversed to get oldest first
        recent = list(buffer)[-n:] if len(buffer) > n else list(buffer)
        return recent
    
    @classmethod
    def get_all(cls, session_id: str) -> List[Dict[str, Any]]:
        """Get all messages in buffer"""
        if session_id not in cls._buffers:
            return []
        return list(cls._buffers[session_id])
    
    @classmethod
    def clear(cls, session_id: str) -> None:
        """Clear buffer for a session"""
        if session_id in cls._buffers:
            del cls._buffers[session_id]
            logger.info(f"Cleared buffer for session {session_id}")
    
    @classmethod
    def get_buffer_size(cls, session_id: str) -> int:
        """Get number of messages in buffer"""
        if session_id not in cls._buffers:
            return 0
        return len(cls._buffers[session_id])
    
    @classmethod
    def get_formatted_history(
        cls,
        session_id: str,
        n: int = 20,
        format_type: str = "langchain"
    ) -> Any:
        """
        Get formatted conversation history.
        
        Args:
            session_id: Session identifier
            n: Number of messages
            format_type: "langchain", "openai", or "raw"
            
        Returns:
            Formatted history in requested format
        """
        messages = cls.get_recent(session_id, n)
        
        if format_type == "raw":
            return messages
        
        elif format_type == "langchain":
            from langchain_core.messages import HumanMessage, AIMessage
            formatted = []
            for msg in messages:
                if msg["role"] == "user":
                    formatted.append(HumanMessage(content=msg["content"]))
                else:
                    formatted.append(AIMessage(content=msg["content"]))
            return formatted
        
        elif format_type == "openai":
            return [
                {
                    "role": msg["role"],
                    "content": msg["content"]
                }
                for msg in messages
            ]
        
        return messages
