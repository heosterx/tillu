"""
TILLU Gateway - FastAPI Application Entry Point
Single public face of Tillu. Stateless. Horizontally scalable.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from prometheus_client import make_asgi_app

from app.config import settings
from app.utils.logging import configure_logging, get_logger
from app.utils.cache import cache
from app.utils.database import db
from app.api import gateway_router, memory_router, health_router, events_router
from app.api.triggers import router as triggers_router

# Configure logging
configure_logging()
logger = get_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    logger.info("Starting TILLU Gateway...")
    
    # Connect to Redis
    try:
        await cache.connect()
        logger.info("Redis connected")
    except Exception as e:
        logger.error("Failed to connect to Redis", error=str(e))
        # Continue without Redis - service can still function
    
    # Connect to Supabase
    try:
        db.connect()
        logger.info("Supabase client initialized")
    except Exception as e:
        logger.error("Failed to initialize Supabase", error=str(e))
        raise
    
    # Register all chains (Phase 3)
    from app.chains.base import ChainRegistry
    ChainRegistry.register_all()
    logger.info("All chains registered")
    
    logger.info("TILLU Gateway started successfully")
    
    yield  # Application runs here
    
    # Shutdown
    logger.info("Shutting down TILLU Gateway...")
    await cache.disconnect()
    logger.info("TILLU Gateway stopped")


# Create FastAPI application
app = FastAPI(
    title="TILLU - Personal AI Backend",
    description="""
    Perpetually-active, self-adaptive, event-driven personal AI backend.
    
    ## Architecture
    - **Gateway**: Single public face (this API)
    - **Engine**: Scheduled intelligence (n8n workflows)
    - **Daemon**: Always-watching ambient intelligence
    
    ## Features
    - Multi-modal input (text, audio, image, document, location)
    - Semantic memory with pgvector
    - Real-time event streaming (SSE)
    - Proactive intelligence delivery
    - Multi-provider LLM routing
    """,
    version="0.1.0",
    docs_url="/docs" if not settings.is_production else None,
    redoc_url="/redoc" if not settings.is_production else None,
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add compression middleware
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Include routers
app.include_router(gateway_router)
app.include_router(memory_router)
app.include_router(events_router)
app.include_router(health_router)
app.include_router(triggers_router)  # Auto-trigger endpoints (cron-job.org)

# Add Prometheus metrics endpoint
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": "TILLU",
        "version": "0.1.0",
        "status": "running",
        "docs": "/docs"
    }


@app.get("/version")
async def version():
    """Get API version"""
    return {
        "version": "0.1.0",
        "build": "phase-1-foundation"
    }
