"""
Memory Tools - Knowledge base operations
"""
from typing import Any, Dict, Optional, List
from app.tools.registry import BaseTool, ToolMetadata, ToolRegistry
from app.utils.database import db
from app.utils.cache import cache
from app.utils.logging import get_logger

logger = get_logger("memory_tools")


class RememberFactTool(BaseTool):
    """Store a fact in the knowledge base"""
    
    metadata = ToolMetadata(
        name="tool_remember_fact",
        description="Store a fact or preference about the user in the knowledge base. Use this to remember important information.",
        parameters={
            "content": {"type": "string", "description": "The fact or information to remember"},
            "category": {"type": "string", "description": "Category (e.g., preference, fact, insight)", "default": "fact"},
            "user_id": {"type": "string", "description": "User ID (usually auto-populated)"}
        },
        rate_limited=False
    )
    
    async def execute(
        self,
        content: str,
        category: str = "fact",
        user_id: str = None
    ) -> Dict[str, Any]:
        """Store fact in knowledge base"""
        try:
            if not user_id:
                return {
                    "success": False,
                    "error": "User ID required"
                }
            
            knowledge_data = {
                "user_id": user_id,
                "content": content,
                "content_type": category,
                "source_type": "tool",
                "confidence_score": 0.9,
                "quality_score": 0.9
            }
            
            result = await db.insert("knowledge_base", knowledge_data)
            
            if result:
                # Invalidate cache
                await cache.delete(f"knowledge_base:{user_id}")
                
                return {
                    "success": True,
                    "memory_id": result[0]["id"],
                    "message": f"Remembered: {content[:100]}..."
                }
            else:
                return {
                    "success": False,
                    "error": "Failed to store in database"
                }
                
        except Exception as e:
            logger.error(f"Remember fact error: {e}")
            return {
                "success": False,
                "error": str(e)
            }


class RecallMemoryTool(BaseTool):
    """Search and recall memories from knowledge base"""
    
    metadata = ToolMetadata(
        name="tool_recall_memory",
        description="Search the knowledge base for relevant information. Use this to recall facts about the user.",
        parameters={
            "query": {"type": "string", "description": "What to search for"},
            "limit": {"type": "integer", "description": "Max results", "default": 5},
            "user_id": {"type": "string", "description": "User ID (usually auto-populated)"}
        },
        rate_limited=False
    )
    
    async def execute(
        self,
        query: str,
        limit: int = 5,
        user_id: str = None
    ) -> Dict[str, Any]:
        """Search knowledge base"""
        try:
            if not user_id:
                return {
                    "success": False,
                    "error": "User ID required"
                }
            
            # For now, do text-based search (semantic search with embeddings in Phase 2)
            results = await db.fetch_many(
                "knowledge_base",
                filters={"user_id": user_id},
                order_by="created_at",
                ascending=False,
                limit=limit
            )
            
            # Filter results that contain query terms (simple text match)
            query_lower = query.lower()
            filtered = [
                r for r in results
                if query_lower in r.get("content", "").lower()
            ]
            
            return {
                "success": True,
                "query": query,
                "results": [
                    {
                        "id": r["id"],
                        "content": r["content"],
                        "category": r.get("category"),
                        "created_at": r["created_at"]
                    }
                    for r in filtered
                ],
                "result_count": len(filtered)
            }
                
        except Exception as e:
            logger.error(f"Recall memory error: {e}")
            return {
                "success": False,
                "error": str(e)
            }


# Register tools
ToolRegistry.register(RememberFactTool())
ToolRegistry.register(RecallMemoryTool())
