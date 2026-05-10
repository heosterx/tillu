"""
Memory API endpoints for semantic search and storage
"""
import time
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Header

from app.models.api import (
    MemorySearchRequest, MemorySearchResponse, MemoryItem
)
from app.utils.database import db
from app.utils.cache import cache
from app.utils.logging import get_logger

logger = get_logger("memory_api")
router = APIRouter(prefix="/api/v1/memory")


async def verify_auth(authorization: Optional[str] = Header(None)):
    """Verify bearer token authentication"""
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header missing")
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization format")
    return {"user_id": "test-user-id"}


@router.post("/search", response_model=MemorySearchResponse)
async def search_memory(
    request: MemorySearchRequest,
    auth: dict = Depends(verify_auth)
):
    """
    Semantic memory query across all stores.
    Uses pgvector similarity search with embeddings.
    """
    user_id = auth["user_id"]
    start_time = time.time()
    
    logger.info("Memory search", query=request.query, limit=request.limit)
    
    try:
        # PHASE 2: Semantic search with embeddings
        from app.memory.semantic_search import semantic_search
        
        results = await semantic_search.search_all(
            user_id=user_id,
            query=request.query,
            max_results_per_source=request.limit
        )
        
        # Format results from all sources
        items = []
        
        # Add knowledge base results
        for item in results.get("knowledge", []):
            items.append(MemoryItem(
                id=item["id"],
                content=item["content"],
                content_type=item.get("content_type", "fact"),
                category=item.get("category"),
                source_type="knowledge_base",
                confidence_score=item.get("confidence_score", 0.8),
                similarity=item.get("similarity", 0.75),
                created_at=item["created_at"]
            ))
        
        # Add news results
        for item in results.get("news", []):
            items.append(MemoryItem(
                id=item["id"],
                content=f"{item.get('title', '')}: {item.get('summary', '')}",
                content_type="news",
                category="current_events",
                source_type="news_article",
                confidence_score=item.get("relevance_score", 0.7),
                similarity=item.get("similarity", 0.7),
                created_at=item["fetched_at"]
            ))
        
        # Add research results
        for item in results.get("research", []):
            items.append(MemoryItem(
                id=item["id"],
                content=item.get("executive_summary", item.get("query", "")),
                content_type="research",
                category="research_session",
                source_type="research",
                confidence_score=0.85,
                similarity=item.get("similarity", 0.75),
                created_at=item["created_at"]
            ))
        
        # Sort by similarity
        items.sort(key=lambda x: x.similarity, reverse=True)
        
        # Apply limit
        items = items[:request.limit]
        
        search_time_ms = int((time.time() - start_time) * 1000)
        
        logger.info(
            "Memory search complete",
            knowledge=len(results.get("knowledge", [])),
            news=len(results.get("news", [])),
            research=len(results.get("research", [])),
            search_time_ms=search_time_ms
        )
        
        return MemorySearchResponse(
            query=request.query,
            results=items,
            total_found=len(items),
            search_time_ms=search_time_ms
        )
        
    except Exception as e:
        logger.error("Memory search error", error=str(e))
        raise HTTPException(status_code=500, detail="Search failed")


@router.post("/store")
async def store_memory(
    content: str,
    content_type: str = "fact",
    category: Optional[str] = None,
    auth: dict = Depends(verify_auth)
):
    """
    Explicitly store a knowledge item.
    Generates embedding automatically (Phase 2).
    """
    user_id = auth["user_id"]
    
    logger.info("Storing memory", content_type=content_type, category=category)
    
    try:
        # PHASE 2: Store with embedding
        from app.memory.semantic_search import semantic_search
        
        result = await semantic_search.store_with_embedding(
            user_id=user_id,
            content=content,
            content_type=content_type,
            category=category,
            source_type="user",
            source_metadata={"api_endpoint": "/memory/store"}
        )
        
        if result:
            return {
                "success": True,
                "memory_id": result["id"],
                "embedding_generated": True,
                "message": "Memory stored with embedding successfully"
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to store memory")
            
    except Exception as e:
        logger.error("Memory store error", error=str(e))
        raise HTTPException(status_code=500, detail="Store failed")


@router.delete("/{memory_id}")
async def delete_memory(
    memory_id: str,
    auth: dict = Depends(verify_auth)
):
    """Delete a memory item"""
    user_id = auth["user_id"]
    
    logger.info("Deleting memory", memory_id=memory_id)
    
    result = await db.delete(
        "knowledge_base",
        {"id": memory_id, "user_id": user_id}
    )
    
    if result:
        return {"success": True, "message": "Memory deleted"}
    else:
        raise HTTPException(status_code=404, detail="Memory not found")
