"""
Health check endpoints
"""
from fastapi import APIRouter
from app.utils.database import db
from app.utils.cache import cache
from app.utils.logging import get_logger
import time

logger = get_logger("health")
router = APIRouter()


@router.get("/health")
async def basic_health():
    """Basic health check endpoint"""
    return {"status": "healthy", "timestamp": time.time()}


@router.get("/ready")
async def readiness_check():
    """Readiness check for Kubernetes/container orchestration"""
    checks = {}
    healthy = True
    
    # Check database
    try:
        result = db.client.table("user_profile").select("id").limit(1).execute()
        checks["database"] = "healthy"
    except Exception as e:
        checks["database"] = f"unhealthy: {str(e)}"
        healthy = False
    
    # Check cache
    try:
        if cache._redis:
            await cache._redis.ping()
            checks["cache"] = "healthy"
        else:
            checks["cache"] = "not connected"
            # Cache is optional - don't fail readiness
    except Exception as e:
        checks["cache"] = f"unhealthy: {str(e)}"
        healthy = False
    
    status = "ready" if healthy else "not ready"
    
    return {
        "status": status,
        "checks": checks,
        "timestamp": time.time()
    }


@router.get("/live")
async def liveness_check():
    """Liveness check for Kubernetes/container orchestration"""
    return {"status": "alive", "timestamp": time.time()}
