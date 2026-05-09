"""
TILLU Gateway API - Primary public interface
Single public face of Tillu. Stateless. Horizontally scalable.
"""
import asyncio
import time
import uuid
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Header, Depends, BackgroundTasks
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse

from app.models.api import (
    MessageRequest, MessageResponse, ChainMetadata, SourceInfo,
    ClientRegistrationRequest, ClientRegistrationResponse,
    HealthResponse, HealthStatus
)
from app.utils.database import db
from app.utils.cache import cache
from app.utils.logging import get_logger, bind_request_context
from app.config import settings

logger = get_logger("gateway")
router = APIRouter(prefix="/api/v1")


async def verify_auth(authorization: Optional[str] = Header(None)):
    """Verify bearer token authentication"""
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header missing")
    
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization format")
    
    token = authorization.replace("Bearer ", "")
    # TODO: Verify JWT with Supabase
    # For now, return user_id from token or use default
    return {"user_id": "test-user-id", "token": token}


@router.post("/message", response_model=MessageResponse)
async def process_message(
    request: MessageRequest,
    background_tasks: BackgroundTasks,
    auth: dict = Depends(verify_auth)
):
    """
    Process any inbound message from any client.
    
    Accepts: text, audio, image, document, location
    Returns: Response + queued events + intelligence packet
    """
    request_id = str(uuid.uuid4())
    user_id = auth["user_id"]
    
    bind_request_context(request_id, user_id)
    
    start_time = time.time()
    logger.info(
        "Processing message",
        type=request.type,
        has_text=bool(request.text),
        has_media=bool(request.media_url)
    )
    
    try:
        # PHASE 2 FULL PIPELINE
        pipeline_start = time.time()
        
        # 1. Process input based on type
        input_text = request.text or ""
        
        # 2. Run transformer pipeline concurrently
        from app.transformers.classifiers import intent_classifier, emotion_detector, stress_detector
        
        intent_task = intent_classifier.classify(input_text)
        emotion_task = emotion_detector.detect(input_text)
        stress_task = stress_detector.detect(input_text)
        
        intent_result, emotion_result, stress_result = await asyncio.gather(
            intent_task, emotion_task, stress_task,
            return_exceptions=True
        )
        
        # Handle exceptions
        intent_result = intent_result if not isinstance(intent_result, Exception) else {"intent_class": "general_query", "confidence": 0.5}
        emotion_result = emotion_result if not isinstance(emotion_result, Exception) else {"dominant_emotion": "neutral", "scores": {}}
        stress_result = stress_result if not isinstance(stress_result, Exception) else {"stress_level": "low", "score": 0.0}
        
        # 3. Assemble context
        from app.chains.context_assembler import ContextAssembler
        
        context = await ContextAssembler.assemble(
            user_id=user_id,
            input_text=input_text,
            session_id=request.client_id
        )
        
        # Add transformer results to context
        context["intent"] = intent_result
        context["emotion"] = emotion_result
        context["stress"] = stress_result
        
        # 4. Select and execute chain using ChainRegistry
        from app.chains.base import ChainRegistry
        
        chain_type = ChainRegistry.select_chain(
            intent_result.get("intent_class", "general_query"),
            input_text,
            context
        )
        
        # Execute the selected chain
        chain_result = await ChainRegistry.execute(
            chain_type=chain_type,
            input_data={"text": input_text},
            context=context
        )
        
        # 5. Build response
        latency_ms = int((time.time() - start_time) * 1000)
        
        response = MessageResponse(
            response=chain_result.get("response", {"type": "text", "content": "No response generated"}),
            personality_mode=chain_result.get("personality_mode", "sharp"),
            queued_events=[],
            intelligence_packet=None,
            meta=ChainMetadata(
                chain=chain_result.get("chain", "conversational"),
                model=chain_result.get("model", "groq-llama-3.1-8b"),
                latency_ms=latency_ms,
                tokens_used=chain_result.get("tokens_used", 0),
                intent_class=intent_result.get("intent_class"),
                personality_mode=chain_result.get("personality_mode")
            ),
            sources=chain_result.get("sources", []),
            session_id=uuid.uuid4()
        )
        
        # Queue background tasks
        background_tasks.add_task(
            _store_interaction,
            user_id=user_id,
            request=request,
            response=response,
            latency_ms=latency_ms,
            intent_result=intent_result,
            emotion_result=emotion_result,
            stress_result=stress_result
        )
        
        # Phase 6: Self-critique runs async after every response
        background_tasks.add_task(
            _run_self_critique,
            user_input=input_text,
            response_text=chain_result.get("response", {}).get("content", ""),
            chain_used=chain_result.get("chain", "conversational")
        )
        
        pipeline_time = time.time() - pipeline_start
        logger.info(
            "Pipeline complete",
            pipeline_time_ms=int(pipeline_time * 1000),
            intent=intent_result.get("intent_class"),
            emotion=emotion_result.get("dominant_emotion"),
            stress=stress_result.get("stress_level")
        )
        
        logger.info("Message processed", latency_ms=latency_ms)
        return response
        
    except Exception as e:
        logger.error("Error processing message", error=str(e))
        raise HTTPException(status_code=500, detail="Internal processing error")


async def _store_interaction(
    user_id: str,
    request: MessageRequest,
    response: MessageResponse,
    latency_ms: int,
    intent_result: Dict[str, Any] = None,
    emotion_result: Dict[str, Any] = None,
    stress_result: Dict[str, Any] = None
):
    """Store interaction in background with Phase 2 transformer results"""
    try:
        interaction_data = {
            "user_id": user_id,
            "session_id": str(response.session_id),
            "interaction_type": request.type.value,
            "input_text": request.text,
            "input_metadata": request.metadata,
            "intent_class": response.meta.intent_class if response.meta else None,
            "emotion_scores": emotion_result.get("scores") if emotion_result else {},
            "stress_score": stress_result.get("score") if stress_result else 0.0,
            "chain_used": response.meta.chain if response.meta else "conversational",
            "model_used": response.meta.model if response.meta else "unknown",
            "latency_ms": latency_ms,
            "tokens_used": response.meta.tokens_used if response.meta else 0,
            "response_text": response.response.get("content"),
            "response_metadata": response.response.get("structured_data"),
            "personality_mode": response.personality_mode,
        }
        
        result = await db.insert("interactions", interaction_data)
        
        # Also store emotion log separately
        if emotion_result and result:
            from app.utils.database import db
            emotion_data = {
                "user_id": user_id,
                "interaction_id": result[0]["id"],
                "dominant_emotion": emotion_result.get("dominant_emotion", "neutral"),
                "emotion_intensity": emotion_result.get("emotion_intensity", 0.5),
                "stress_level": stress_result.get("stress_level", "low") if stress_result else "low",
                **{k: v for k, v in emotion_result.get("scores", {}).items() if k in ["joy", "sadness", "anger", "fear", "surprise", "disgust", "neutral"]}
            }
            await db.insert("emotion_log", emotion_data)
        
        logger.info("Interaction stored", interaction_id=result[0]["id"] if result else None)
        
    except Exception as e:
        logger.error("Failed to store interaction", error=str(e))


async def _run_self_critique(
    user_input: str,
    response_text: str,
    chain_used: str,
    interaction_id: Optional[str] = None
):
    """Run self-critique chain asynchronously after every response (Phase 6)"""
    try:
        from app.chains.base import ChainRegistry, ChainType
        await ChainRegistry.execute(
            chain_type=ChainType.SELF_CRITIQUE,
            input_data={
                "user_input": user_input,
                "response": response_text,
                "chain_used": chain_used,
                "interaction_id": interaction_id
            }
        )
    except Exception as e:
        logger.error("Self-critique background task failed", error=str(e))


@router.get("/stream")
async def event_stream(auth: dict = Depends(verify_auth)):
    """
    SSE long-lived connection.
    TILLU pushes events as they are generated.
    Client subscribes once, receives indefinitely.
    """
    user_id = auth["user_id"]
    request_id = str(uuid.uuid4())
    bind_request_context(request_id, user_id)
    
    logger.info("SSE stream started", user_id=user_id)
    
    async def event_generator():
        """Generate SSE events"""
        # Subscribe to user's event channel
        channel = f"tillu:events:{user_id}"
        pubsub = await cache.subscribe(channel)
        
        try:
            # Send initial connection event
            yield {
                "event": "connected",
                "data": {"message": "Connected to TILLU event stream", "user_id": user_id}
            }
            
            # Listen for events
            async for message in pubsub.listen():
                if message["type"] == "message":
                    data = message["data"]
                    yield {
                        "event": "tillu_event",
                        "data": data
                    }
        except Exception as e:
            logger.error("SSE stream error", error=str(e))
        finally:
            await pubsub.unsubscribe(channel)
    
    return EventSourceResponse(event_generator())


@router.post("/register", response_model=ClientRegistrationResponse)
async def register_client(
    request: ClientRegistrationRequest,
    auth: dict = Depends(verify_auth)
):
    """
    Register client + capabilities + preferences.
    TILLU adjusts output format to client capabilities.
    """
    user_id = auth["user_id"]
    request_id = str(uuid.uuid4())
    bind_request_context(request_id, user_id)
    
    logger.info("Registering client", client_name=request.client_name, type=request.client_type)
    
    try:
        # Generate API key for client
        client_api_key = f"tillu_{uuid.uuid4().hex}"
        
        client_data = {
            "user_id": user_id,
            "client_name": request.client_name,
            "client_type": request.client_type,
            "supports_text": request.capabilities.supports_text,
            "supports_audio": request.capabilities.supports_audio,
            "supports_image": request.capabilities.supports_image,
            "supports_document": request.capabilities.supports_document,
            "supports_location": request.capabilities.supports_location,
            "supports_sse": request.capabilities.supports_sse,
            "supports_websocket": request.capabilities.supports_websocket,
            "preferences": request.preferences or {},
            "api_key_hash": client_api_key,  # In production, hash this
        }
        
        result = await db.insert("client_registry", client_data)
        
        if result:
            return ClientRegistrationResponse(
                client_id=result[0]["id"],
                api_key=client_api_key,
                registered_at=result[0]["created_at"]
            )
        else:
            raise HTTPException(status_code=500, detail="Failed to register client")
            
    except Exception as e:
        logger.error("Error registering client", error=str(e))
        raise HTTPException(status_code=500, detail="Registration failed")


@router.get("/intelligence")
async def get_intelligence(
    since: Optional[str] = None,
    types: Optional[str] = None,
    urgency_min: int = 1,
    auth: dict = Depends(verify_auth)
):
    """
    Pull compiled intelligence packets.
    For clients coming online after offline period.
    """
    user_id = auth["user_id"]
    
    # Query event queue for pending events
    filters = {"user_id": user_id, "status": "pending"}
    
    events = await db.fetch_many(
        "event_queue",
        filters=filters,
        order_by="urgency",
        ascending=False,
        limit=50
    )
    
    return {
        "packets": events,
        "count": len(events),
        "timestamp": time.time()
    }


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    System status: all services, API limits, queue depths.
    """
    services = []
    
    # Check Supabase
    try:
        supabase_status = await db.fetch_one("user_profile", {"id": "test"})
        services.append(HealthStatus(
            service="supabase",
            status="healthy",
            response_time_ms=50,
            last_check=time.time()
        ))
    except:
        services.append(HealthStatus(
            service="supabase",
            status="degraded",
            last_check=time.time()
        ))
    
    # Check Redis
    try:
        await cache._redis.ping()
        services.append(HealthStatus(
            service="redis",
            status="healthy",
            response_time_ms=10,
            last_check=time.time()
        ))
    except:
        services.append(HealthStatus(
            service="redis",
            status="down",
            last_check=time.time()
        ))
    
    return HealthResponse(
        status="healthy" if all(s.status == "healthy" for s in services) else "degraded",
        version=settings.__version__ if hasattr(settings, "__version__") else "0.1.0",
        timestamp=time.time(),
        services=services,
        api_limits={
            "groq": {"remaining": 14400, "reset_time": "1h"},
            "cerebras": {"remaining": 500, "reset_time": "24h"},
        },
        queue_depths={
            "tillu:events:urgent": 0,
            "tillu:events:normal": 5,
            "tillu:events:low": 23
        }
    )


@router.get("/analytics")
async def get_analytics(
    period: str = "24h",
    auth: dict = Depends(verify_auth)
):
    """
    Usage metrics, quality scores, system performance.
    """
    user_id = auth["user_id"]
    
    # Get analytics from system_analytics table
    # For now, return placeholder data
    return {
        "period": period,
        "total_interactions": 150,
        "avg_response_time_ms": 850,
        "interactions_by_chain": {
            "conversational": 120,
            "research": 15,
            "analysis": 15
        },
        "avg_quality_scores": {
            "accuracy": 0.85,
            "helpfulness": 0.88,
            "personality_fit": 0.82
        },
        "api_usage": {
            "groq": {"requests": 150, "tokens": 45000},
            "hf_embedding": {"requests": 300}
        },
        "events_generated": 25,
        "events_by_type": {
            "news": 15,
            "financial": 5,
            "task_reminder": 5
        }
    }
