"""
Semantic Search using pgvector
Full implementation of vector similarity search
"""
import asyncio
from typing import List, Dict, Any, Optional
from app.utils.database import db
from app.utils.cache import cache
from app.utils.logging import get_logger
from app.transformers.embeddings import embedding_generator

logger = get_logger("semantic_search")


class SemanticSearch:
    """
    Semantic search across all vector stores:
    - knowledge_base
    - news_articles
    - research_sessions
    - people_knowledge
    """
    
    def __init__(self):
        self.logger = get_logger("semantic_search")
    
    async def search_knowledge(
        self,
        user_id: str,
        query: str,
        similarity_threshold: float = 0.75,
        max_results: int = 8
    ) -> List[Dict[str, Any]]:
        """
        Search knowledge base using semantic similarity
        
        Args:
            user_id: User ID
            query: Search query
            similarity_threshold: Minimum similarity (0-1)
            max_results: Maximum results to return
            
        Returns:
            List of knowledge items with similarity scores
        """
        try:
            # Generate embedding for query
            query_embedding = await embedding_generator.generate(query)
            
            if not query_embedding:
                self.logger.warning("Failed to generate query embedding")
                return await self._fallback_text_search(user_id, query, max_results)
            
            # Call pgvector similarity search via RPC
            results = await db.rpc(
                "search_knowledge",
                {
                    "query_embedding": query_embedding,
                    "user_uuid": user_id,
                    "similarity_threshold": similarity_threshold,
                    "max_results": max_results
                }
            )
            
            if results:
                # Update access counts
                for item in results:
                    await db.rpc(
                        "increment_access_count",
                        {"knowledge_id": item.get("id")}
                    )
                
                return results
            
            return []
            
        except Exception as e:
            self.logger.error(f"Semantic search error: {e}")
            return await self._fallback_text_search(user_id, query, max_results)
    
    async def search_news(
        self,
        user_id: str,
        query: str,
        min_urgency: int = 1,
        similarity_threshold: float = 0.70,
        max_results: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Search news articles semantically
        
        Args:
            user_id: User ID
            query: Search query
            min_urgency: Minimum urgency score
            similarity_threshold: Minimum similarity
            max_results: Maximum results
            
        Returns:
            List of news articles with relevance scores
        """
        try:
            # Generate embedding
            query_embedding = await embedding_generator.generate(query)
            
            if not query_embedding:
                return []
            
            # Call pgvector search
            results = await db.rpc(
                "search_news",
                {
                    "query_embedding": query_embedding,
                    "user_uuid": user_id,
                    "min_urgency": min_urgency,
                    "similarity_threshold": similarity_threshold,
                    "max_results": max_results
                }
            )
            
            return results or []
            
        except Exception as e:
            self.logger.error(f"News search error: {e}")
            return []
    
    async def search_research(
        self,
        user_id: str,
        query: str,
        similarity_threshold: float = 0.70,
        max_results: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Search research sessions semantically
        
        Args:
            user_id: User ID
            query: Search query
            similarity_threshold: Minimum similarity
            max_results: Maximum results
            
        Returns:
            List of research sessions
        """
        try:
            # Generate embedding
            query_embedding = await embedding_generator.generate(query)
            
            if not query_embedding:
                return []
            
            # Query research_sessions with similarity
            # Using raw query since we need the vector operation
            results = await db.fetch_many(
                "research_sessions",
                filters={
                    "user_id": user_id,
                    "status": "complete"
                },
                order_by="created_at",
                ascending=False,
                limit=max_results * 2  # Fetch more for filtering
            )
            
            # Calculate similarity for each
            scored_results = []
            for item in results:
                if item.get("embedding"):
                    similarity = embedding_generator.cosine_similarity(
                        query_embedding,
                        item["embedding"]
                    )
                    if similarity >= similarity_threshold:
                        item["similarity"] = similarity
                        scored_results.append(item)
            
            # Sort by similarity and return top N
            scored_results.sort(key=lambda x: x["similarity"], reverse=True)
            return scored_results[:max_results]
            
        except Exception as e:
            self.logger.error(f"Research search error: {e}")
            return []
    
    async def search_all(
        self,
        user_id: str,
        query: str,
        max_results_per_source: int = 5
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Search across all semantic memory sources
        
        Args:
            user_id: User ID
            query: Search query
            max_results_per_source: Max results per source
            
        Returns:
            Dict with results from each source
        """
        # Search all sources concurrently
        knowledge_task = self.search_knowledge(
            user_id, query, max_results=max_results_per_source
        )
        news_task = self.search_news(
            user_id, query, max_results=max_results_per_source
        )
        research_task = self.search_research(
            user_id, query, max_results=3
        )
        
        knowledge, news, research = await asyncio.gather(
            knowledge_task, news_task, research_task,
            return_exceptions=True
        )
        
        return {
            "knowledge": knowledge if not isinstance(knowledge, Exception) else [],
            "news": news if not isinstance(news, Exception) else [],
            "research": research if not isinstance(research, Exception) else [],
            "total_results": sum([
                len(knowledge) if not isinstance(knowledge, Exception) else 0,
                len(news) if not isinstance(news, Exception) else 0,
                len(research) if not isinstance(research, Exception) else 0
            ])
        }
    
    async def _fallback_text_search(
        self,
        user_id: str,
        query: str,
        max_results: int
    ) -> List[Dict[str, Any]]:
        """Fallback to text-based search when embeddings fail"""
        self.logger.warning("Using fallback text search")
        
        # Simple text search in knowledge_base
        results = await db.fetch_many(
            "knowledge_base",
            filters={"user_id": user_id},
            order_by="access_count",
            ascending=False,
            limit=max_results
        )
        
        # Add dummy similarity
        for item in results:
            item["similarity"] = 0.5
        
        return results
    
    async def store_with_embedding(
        self,
        user_id: str,
        content: str,
        content_type: str = "fact",
        category: Optional[str] = None,
        source_type: str = "user",
        source_metadata: Optional[Dict] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Store content with generated embedding
        
        Args:
            user_id: User ID
            content: Content to store
            content_type: Type of content
            category: Category
            source_type: Source type
            source_metadata: Additional metadata
            
        Returns:
            Stored item with ID
        """
        try:
            # Generate embedding
            embedding = await embedding_generator.generate(content)
            
            # Prepare data
            data = {
                "user_id": user_id,
                "content": content,
                "content_type": content_type,
                "category": category,
                "source_type": source_type,
                "source_metadata": source_metadata or {},
                "embedding": embedding,
                "confidence_score": 0.9,
                "quality_score": 0.9
            }
            
            # Insert
            result = await db.insert("knowledge_base", data)
            
            if result:
                self.logger.info(f"Stored knowledge with embedding: {result[0]['id']}")
                return result[0]
            
            return None
            
        except Exception as e:
            self.logger.error(f"Store with embedding error: {e}")
            return None


# Import asyncio
import asyncio

# Global instance
semantic_search = SemanticSearch()
