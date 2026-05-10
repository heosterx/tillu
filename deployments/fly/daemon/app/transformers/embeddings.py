"""
Embedding Generation Pipeline
Model: sentence-transformers/all-mpnet-base-v2
"""
import httpx
import numpy as np
from typing import List, Dict, Any, Optional
from app.config import settings
from app.utils.logging import get_logger
from app.utils.cache import cache

logger = get_logger("embeddings")


class EmbeddingGenerator:
    """
    Generate embeddings using Hugging Face Inference API
    Falls back to local model if HF API is unavailable
    """
    
    def __init__(self):
        self.model = settings.hf_embedding_model
        self.api_url = settings.hf_inference_api_url
        self.token = settings.hf_token
        self.dimension = 768  # all-mpnet-base-v2 output dimension
        self.logger = get_logger("embedding_generator")
    
    async def generate(
        self,
        text: str,
        use_cache: bool = True
    ) -> Optional[List[float]]:
        """
        Generate embedding for a single text
        
        Args:
            text: Input text to embed
            use_cache: Whether to use Redis cache
            
        Returns:
            768-dimensional embedding vector or None on error
        """
        if not text or not text.strip():
            return None
        
        # Check cache
        if use_cache:
            cache_key = f"embedding:{hash(text) % 10000000}"
            cached = await cache.get(cache_key)
            if cached:
                self.logger.debug("Embedding cache hit")
                return cached
        
        try:
            # Try HF Inference API first
            embedding = await self._generate_hf_api(text)
            
            if embedding is None:
                # Fallback to local computation if available
                embedding = await self._generate_local(text)
            
            # Cache result
            if use_cache and embedding:
                await cache.set(cache_key, embedding, ttl=86400)  # 24 hours
            
            return embedding
            
        except Exception as e:
            self.logger.error(f"Embedding generation failed: {e}")
            return None
    
    async def generate_batch(
        self,
        texts: List[str],
        batch_size: int = 32
    ) -> List[Optional[List[float]]]:
        """
        Generate embeddings for multiple texts
        
        Args:
            texts: List of input texts
            batch_size: Batch size for API calls
            
        Returns:
            List of embedding vectors
        """
        results = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            batch_embeddings = await self._generate_batch_hf_api(batch)
            results.extend(batch_embeddings)
        
        return results
    
    async def _generate_hf_api(self, text: str) -> Optional[List[float]]:
        """Generate embedding via Hugging Face Inference API"""
        if not self.token:
            return None
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_url}/pipeline/feature-extraction/{self.model}",
                    headers={"Authorization": f"Bearer {self.token}"},
                    json={"inputs": text},
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    # HF API returns list of embeddings (one per token), take mean
                    if isinstance(data, list) and len(data) > 0:
                        if isinstance(data[0], list):
                            # Mean pooling across tokens
                            embeddings = np.array(data)
                            embedding = np.mean(embeddings, axis=0).tolist()
                            return embedding
                        else:
                            return data
                else:
                    self.logger.warning(f"HF API error: {response.status_code}")
                    
        except Exception as e:
            self.logger.error(f"HF API call failed: {e}")
        
        return None
    
    async def _generate_batch_hf_api(
        self,
        texts: List[str]
    ) -> List[Optional[List[float]]]:
        """Generate embeddings for batch via HF API"""
        if not self.token:
            return [None] * len(texts)
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_url}/pipeline/feature-extraction/{self.model}",
                    headers={"Authorization": f"Bearer {self.token}"},
                    json={"inputs": texts},
                    timeout=60.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    results = []
                    
                    for item in data:
                        if isinstance(item, list) and len(item) > 0:
                            if isinstance(item[0], list):
                                # Mean pooling
                                embeddings = np.array(item)
                                embedding = np.mean(embeddings, axis=0).tolist()
                                results.append(embedding)
                            else:
                                results.append(item)
                        else:
                            results.append(None)
                    
                    return results
                else:
                    self.logger.warning(f"HF API batch error: {response.status_code}")
                    
        except Exception as e:
            self.logger.error(f"HF API batch call failed: {e}")
        
        return [None] * len(texts)
    
    async def _generate_local(self, text: str) -> Optional[List[float]]:
        """
        Generate embedding locally using sentence-transformers
        Fallback when HF API is unavailable
        """
        try:
            # Import here to avoid loading at startup
            from sentence_transformers import SentenceTransformer
            
            # Load model (cached after first load)
            model = SentenceTransformer(self.model)
            embedding = model.encode(text, convert_to_numpy=True)
            
            return embedding.tolist()
            
        except Exception as e:
            self.logger.error(f"Local embedding failed: {e}")
            return None
    
    def cosine_similarity(
        self,
        embedding1: List[float],
        embedding2: List[float]
    ) -> float:
        """Calculate cosine similarity between two embeddings"""
        vec1 = np.array(embedding1)
        vec2 = np.array(embedding2)
        
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return float(np.dot(vec1, vec2) / (norm1 * norm2))


# Global instance
embedding_generator = EmbeddingGenerator()
