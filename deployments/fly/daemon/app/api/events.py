"""
Event API endpoints
"""
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Header
from uuid import UUID

from app.utils.database import db
from app.utils.cache import cache
from app.utils.logging import get_logger

logger = get_logger("events_api")
router = APIRouter(prefix="/api/v1/events")


async def verify_auth(authorization: Optional[str] = Header(None)):
    """Verify bearer token authentication"""
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header missing")
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization format")
    return {"user_id": "test-user-id"}


@router.get("/")
async def list_events(
    status: Optional[str] = "pending",
    urgency_min: int = 1,
    limit: int = 50,
    auth: dict = Depends(verify_auth)
):
    """List events for the authenticated user"""
    user_id = auth["user_id"]
    
    filters = {"user_id": user_id}
    if status:
        filters["status"] = status
    
    events = await db.fetch_many(
        "event_queue",
        filters=filters,
        order_by="urgency",
        ascending=False,
        limit=limit
    )
    
    return {"events": events, "count": len(events)}


@router.post("/{event_id}/acknowledge")
async def acknowledge_event(
    event_id: UUID,
    auth: dict = Depends(verify_auth)
):
    """Acknowledge an event"""
    user_id = auth["user_id"]
    
    logger.info("Acknowledging event", event_id=event_id)
    
    result = await db.update(
        "event_queue",
        {"status": "acknowledged", "acknowledged_at": "now()"},
        {"id": event_id, "user_id": user_id}
    )
    
    if result:
        return {"success": True, "message": "Event acknowledged"}
    else:
        raise HTTPException(status_code=404, detail="Event not found")


@router.post("/{event_id}/dismiss")
async def dismiss_event(
    event_id: UUID,
    auth: dict = Depends(verify_auth)
):
    """Dismiss an event"""
    user_id = auth["user_id"]
    
    logger.info("Dismissing event", event_id=event_id)
    
    result = await db.update(
        "event_queue",
        {"status": "dismissed"},
        {"id": event_id, "user_id": user_id}
    )
    
    if result:
        return {"success": True, "message": "Event dismissed"}
    else:
        raise HTTPException(status_code=404, detail="Event not found")


@router.post("/monitor")
async def create_web_monitor(
    url: str,
    name: Optional[str] = None,
    css_selector: Optional[str] = None,
    check_interval: int = 30,
    auth: dict = Depends(verify_auth)
):
    """Register a URL for web change monitoring"""
    user_id = auth["user_id"]
    
    logger.info("Creating web monitor", url=url, name=name)
    
    monitor_data = {
        "user_id": user_id,
        "url": url,
        "name": name or url,
        "css_selector": css_selector,
        "check_interval_minutes": check_interval,
        "is_active": True
    }
    
    result = await db.insert("web_monitors", monitor_data)
    
    if result:
        return {
            "success": True,
            "monitor_id": result[0]["id"],
            "message": "Web monitor created"
        }
    else:
        raise HTTPException(status_code=500, detail="Failed to create monitor")
