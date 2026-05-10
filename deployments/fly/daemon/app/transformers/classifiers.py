"""
Classification models for intent, emotion, and stress
Uses Hugging Face Inference API
"""
import httpx
from typing import Dict, Any, Optional
from app.config import settings
from app.utils.logging import get_logger

logger = get_logger("classifiers")


class IntentClassifier:
    """
    Intent Classification
    Model: distilbert-base-uncased (fine-tuned)
    Output: Intent class from 14 categories
    """
    
    INTENT_CLASSES = [
        "small_talk",
        "general_query",
        "follow_up",
        "research_request",
        "deep_analysis",
        "action_required",
        "real_world_query",
        "multi_step_task",
        "pattern_query",
        "data_analysis",
        "structured_request",
        "distress",
        "sadness",
        "high_stress",
    ]
    
    def __init__(self):
        self.model = settings.hf_classifier_model
        self.api_url = settings.hf_inference_api_url
        self.token = settings.hf_token
        self.logger = get_logger("intent_classifier")
    
    async def classify(self, text: str) -> Dict[str, Any]:
        """
        Classify user intent
        
        Args:
            text: User input text
            
        Returns:
            Dict with intent_class, confidence, all_scores
        """
        if not text or not text.strip():
            return {
                "intent_class": "general_query",
                "confidence": 1.0,
                "all_scores": {}
            }
        
        try:
            # Use HF Inference API
            result = await self._classify_hf_api(text)
            if result:
                return result
        except Exception as e:
            self.logger.error(f"Intent classification error: {e}")
        
        # Fallback: Simple keyword-based classification
        return self._classify_heuristic(text)
    
    async def _classify_hf_api(self, text: str) -> Optional[Dict[str, Any]]:
        """Classify via HF Inference API"""
        if not self.token:
            return None
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.api_url}/models/{self.model}",
                headers={"Authorization": f"Bearer {self.token}"},
                json={"inputs": text},
                timeout=10.0
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # Parse HF zero-shot or classification output
                if isinstance(data, list) and len(data) > 0:
                    predictions = data[0]
                    
                    # Get top prediction
                    if isinstance(predictions, list):
                        top = max(predictions, key=lambda x: x.get('score', 0))
                        return {
                            "intent_class": top.get('label', 'general_query').lower().replace(' ', '_'),
                            "confidence": top.get('score', 0.5),
                            "all_scores": {p.get('label', '').lower().replace(' ', '_'): p.get('score', 0) for p in predictions}
                        }
            
            return None
    
    def _classify_heuristic(self, text: str) -> Dict[str, Any]:
        """Fallback heuristic classification"""
        text_lower = text.lower()
        
        # Research indicators
        if any(word in text_lower for word in ['research', 'analyze', 'study', 'investigate', 'deep dive']):
            return {"intent_class": "research_request", "confidence": 0.7, "all_scores": {}}
        
        # Action indicators
        if any(word in text_lower for word in ['book', 'schedule', 'set up', 'create', 'buy', 'order']):
            return {"intent_class": "action_required", "confidence": 0.7, "all_scores": {}}
        
        # Distress indicators
        if any(word in text_lower for word in ['stressed', 'worried', 'anxious', 'overwhelmed', 'help']):
            return {"intent_class": "distress", "confidence": 0.6, "all_scores": {}}
        
        # Question indicators
        if '?' in text or any(word in text_lower for word in ['what', 'how', 'why', 'when', 'where']):
            return {"intent_class": "general_query", "confidence": 0.8, "all_scores": {}}
        
        # Default
        return {"intent_class": "small_talk", "confidence": 0.6, "all_scores": {}}


class EmotionDetector:
    """
    Emotion Detection
    Model: j-hartmann/emotion-english-distilroberta-base
    Output: {joy, sadness, anger, fear, surprise, disgust, neutral} scores
    """
    
    EMOTIONS = ["joy", "sadness", "anger", "fear", "surprise", "disgust", "neutral"]
    
    def __init__(self):
        self.model = settings.hf_emotion_model
        self.api_url = settings.hf_inference_api_url
        self.token = settings.hf_token
        self.logger = get_logger("emotion_detector")
    
    async def detect(self, text: str) -> Dict[str, Any]:
        """
        Detect emotions in text
        
        Args:
            text: Input text
            
        Returns:
            Dict with emotion scores and dominant emotion
        """
        if not text or not text.strip():
            return {
                "dominant_emotion": "neutral",
                "scores": {e: 0.0 for e in self.EMOTIONS},
                "emotion_intensity": 0.0
            }
        
        try:
            result = await self._detect_hf_api(text)
            if result:
                return result
        except Exception as e:
            self.logger.error(f"Emotion detection error: {e}")
        
        # Fallback: neutral
        return {
            "dominant_emotion": "neutral",
            "scores": {e: 0.0 for e in self.EMOTIONS},
            "emotion_intensity": 0.0
        }
    
    async def _detect_hf_api(self, text: str) -> Optional[Dict[str, Any]]:
        """Detect emotions via HF Inference API"""
        if not self.token:
            return None
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.api_url}/models/{self.model}",
                headers={"Authorization": f"Bearer {self.token}"},
                json={"inputs": text},
                timeout=10.0
            )
            
            if response.status_code == 200:
                data = response.json()
                
                if isinstance(data, list) and len(data) > 0:
                    predictions = data[0]
                    
                    # Build scores dict
                    scores = {}
                    for pred in predictions:
                        label = pred.get('label', '').lower()
                        score = pred.get('score', 0.0)
                        scores[label] = score
                    
                    # Fill missing emotions with 0
                    for emotion in self.EMOTIONS:
                        if emotion not in scores:
                            scores[emotion] = 0.0
                    
                    # Determine dominant
                    dominant = max(scores, key=scores.get)
                    intensity = scores[dominant]
                    
                    return {
                        "dominant_emotion": dominant,
                        "scores": scores,
                        "emotion_intensity": intensity
                    }
            
            return None


class StressDetector:
    """
    Stress/Toxicity Detection
    Model: martin-ha/toxic-comment-model
    Output: Stress/distress probability score
    """
    
    def __init__(self):
        self.model = "martin-ha/toxic-comment-model"
        self.api_url = settings.hf_inference_api_url
        self.token = settings.hf_token
        self.logger = get_logger("stress_detector")
    
    async def detect(self, text: str) -> Dict[str, Any]:
        """
        Detect stress level
        
        Args:
            text: Input text
            
        Returns:
            Dict with stress_level, score, is_stressed
        """
        if not text or not text.strip():
            return {
                "stress_level": "low",
                "score": 0.0,
                "is_stressed": False
            }
        
        try:
            result = await self._detect_hf_api(text)
            if result:
                return result
        except Exception as e:
            self.logger.error(f"Stress detection error: {e}")
        
        # Fallback: Heuristic
        return self._detect_heuristic(text)
    
    async def _detect_hf_api(self, text: str) -> Optional[Dict[str, Any]]:
        """Detect stress via HF Inference API"""
        if not self.token:
            return None
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.api_url}/models/{self.model}",
                headers={"Authorization": f"Bearer {self.token}"},
                json={"inputs": text},
                timeout=10.0
            )
            
            if response.status_code == 200:
                data = response.json()
                
                if isinstance(data, list) and len(data) > 0:
                    predictions = data[0]
                    
                    # Calculate toxic score
                    toxic_score = 0.0
                    for pred in predictions:
                        if pred.get('label') == 'toxic' or pred.get('label') == 'LABEL_1':
                            toxic_score = pred.get('score', 0.0)
                    
                    # Map to stress levels
                    if toxic_score > 0.7:
                        level = "high"
                    elif toxic_score > 0.3:
                        level = "medium"
                    else:
                        level = "low"
                    
                    return {
                        "stress_level": level,
                        "score": toxic_score,
                        "is_stressed": toxic_score > 0.5
                    }
            
            return None
    
    def _detect_heuristic(self, text: str) -> Dict[str, Any]:
        """Heuristic stress detection"""
        text_lower = text.lower()
        
        stress_words = [
            'stressed', 'overwhelmed', 'anxious', 'worried', 'panic',
            'urgent', 'emergency', 'help', 'desperate', 'exhausted'
        ]
        
        count = sum(1 for word in stress_words if word in text_lower)
        intensity = min(count / 3, 1.0)  # Cap at 1.0
        
        if intensity > 0.6:
            level = "high"
        elif intensity > 0.3:
            level = "medium"
        else:
            level = "low"
        
        return {
            "stress_level": level,
            "score": intensity,
            "is_stressed": intensity > 0.5
        }


# Global instances
intent_classifier = IntentClassifier()
emotion_detector = EmotionDetector()
stress_detector = StressDetector()
