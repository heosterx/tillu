"""
NER and Summarization
"""
import httpx
from typing import List, Dict, Any, Optional
from app.config import settings
from app.utils.logging import get_logger

logger = get_logger("extractors")


class NERExtractor:
    """
    Named Entity Recognition
    Model: dbmdz/bert-large-cased-finetuned-conll03-english
    Output: Structured entities {persons, orgs, locations, dates}
    """
    
    def __init__(self):
        self.model = settings.hf_ner_model
        self.api_url = settings.hf_inference_api_url
        self.token = settings.hf_token
        self.logger = get_logger("ner_extractor")
    
    async def extract(self, text: str) -> List[Dict[str, Any]]:
        """
        Extract named entities from text
        
        Args:
            text: Input text
            
        Returns:
            List of entities with type, word, score
        """
        if not text or not text.strip():
            return []
        
        try:
            result = await self._extract_hf_api(text)
            if result:
                return result
        except Exception as e:
            self.logger.error(f"NER extraction error: {e}")
        
        return []
    
    async def _extract_hf_api(self, text: str) -> Optional[List[Dict[str, Any]]]:
        """Extract entities via HF Inference API"""
        if not self.token:
            return None
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.api_url}/models/{self.model}",
                headers={"Authorization": f"Bearer {self.token}"},
                json={"inputs": text},
                timeout=15.0
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # Group consecutive tokens of same entity
                entities = []
                current_entity = None
                
                for item in data:
                    word = item.get('word', '')
                    entity_type = item.get('entity_group', item.get('entity', ''))
                    score = item.get('score', 0.0)
                    
                    # Clean entity type
                    entity_type = entity_type.replace('B-', '').replace('I-', '')
                    
                    # Map to standard types
                    type_mapping = {
                        'PER': 'person',
                        'PERSON': 'person',
                        'ORG': 'organization',
                        'LOC': 'location',
                        'GPE': 'location',
                        'DATE': 'date',
                        'TIME': 'time',
                        'MONEY': 'money',
                        'PERCENT': 'percent'
                    }
                    
                    entity_type = type_mapping.get(entity_type, entity_type.lower())
                    
                    entities.append({
                        "word": word,
                        "type": entity_type,
                        "score": score
                    })
                
                return entities
            
            return None


class Summarizer:
    """
    Text Summarization
    Model: facebook/bart-large-cnn
    Output: 200-word summaries
    """
    
    def __init__(self):
        self.model = settings.hf_summarizer_model
        self.api_url = settings.hf_inference_api_url
        self.token = settings.hf_token
        self.logger = get_logger("summarizer")
    
    async def summarize(
        self,
        text: str,
        max_length: int = 200,
        min_length: int = 50
    ) -> Optional[str]:
        """
        Summarize text
        
        Args:
            text: Long text to summarize
            max_length: Maximum summary length
            min_length: Minimum summary length
            
        Returns:
            Summarized text
        """
        if not text or len(text) < min_length * 2:
            return text
        
        try:
            result = await self._summarize_hf_api(text, max_length, min_length)
            if result:
                return result
        except Exception as e:
            self.logger.error(f"Summarization error: {e}")
        
        # Fallback: Extract first sentences
        sentences = text.split('.')
        summary = '. '.join(sentences[:3]) + '.'
        return summary[:max_length]
    
    async def _summarize_hf_api(
        self,
        text: str,
        max_length: int,
        min_length: int
    ) -> Optional[str]:
        """Summarize via HF Inference API"""
        if not self.token:
            return None
        
        # Truncate if too long (BART limit)
        if len(text) > 1024:
            text = text[:1024]
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.api_url}/models/{self.model}",
                headers={"Authorization": f"Bearer {self.token}"},
                json={
                    "inputs": text,
                    "parameters": {
                        "max_length": max_length,
                        "min_length": min_length,
                        "do_sample": False
                    }
                },
                timeout=30.0
            )
            
            if response.status_code == 200:
                data = response.json()
                
                if isinstance(data, list) and len(data) > 0:
                    return data[0].get('summary_text', '')
            
            return None


# Global instances
ner_extractor = NERExtractor()
summarizer = Summarizer()
