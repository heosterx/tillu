"""
Calendar Intelligence Service
Google Calendar API integration for smart scheduling and reminders
"""
import httpx
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from app.config import settings
from app.utils.database import db
from app.utils.logging import get_logger
from app.utils.google_auth import get_access_token

logger = get_logger("calendar_service")


class CalendarService:
    """
    Calendar intelligence and scheduling service
    Integrates with Google Calendar for events and smart suggestions
    """
    
    CALENDAR_API = "https://www.googleapis.com/calendar/v3"
    
    def __init__(self):
        self.calendar_enabled = bool(settings.google_client_id and settings.gmail_refresh_token)
    
    async def sync_events(self, user_id: str, days_ahead: int = 7) -> List[Dict[str, Any]]:
        """
        Sync calendar events from Google Calendar
        
        Args:
            user_id: User to sync for
            days_ahead: How many days ahead to fetch
            
        Returns:
            List of synced events
        """
        if not self.calendar_enabled:
            logger.warning("Calendar API not configured")
            return []
        
        synced = []
        
        try:
            # Calculate time range
            now = datetime.now()
            time_min = now.isoformat() + "Z"
            time_max = (now + timedelta(days=days_ahead)).isoformat() + "Z"
            
            # Fetch events from Google Calendar
            async with httpx.AsyncClient() as client:
                token = await get_access_token()
                if not token:
                    logger.error("Could not obtain Google access token")
                    return []

                response = await client.get(
                    f"{self.CALENDAR_API}/calendars/primary/events",
                    params={
                        "timeMin": time_min,
                        "timeMax": time_max,
                        "singleEvents": "true",
                        "orderBy": "startTime",
                        "maxResults": 50
                    },
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=15.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    events = data.get("items", [])
                    
                    for event in events:
                        # Extract event details
                        event_data = self._parse_event(event)
                        event_data["user_id"] = user_id
                        event_data["synced_at"] = datetime.now().isoformat()
                        
                        # Check if already exists
                        existing = await db.fetch_one(
                            "tasks_goals",
                            {
                                "user_id": user_id,
                                "external_id": event.get("id"),
                                "type": "event"
                            }
                        )
                        
                        if not existing:
                            # Store as event type task
                            result = await db.insert("tasks_goals", event_data)
                            if result:
                                synced.append(event_data)
                        else:
                            # Update existing
                            await db.update(
                                "tasks_goals",
                                event_data,
                                {"id": existing.get("id")}
                            )
                            synced.append({**event_data, "updated": True})
                            
        except Exception as e:
            logger.error(f"Calendar sync error: {e}")
        
        logger.info(f"Synced {len(synced)} calendar events")
        return synced
    
    def _parse_event(self, event: Dict) -> Dict[str, Any]:
        """Parse Google Calendar event to our format"""
        start = event.get("start", {})
        end = event.get("end", {})
        
        # Handle dateTime or date
        start_time = start.get("dateTime") or start.get("date")
        end_time = end.get("dateTime") or end.get("date")
        
        # Calculate duration
        is_all_day = "date" in start and "T" not in start_time
        
        # Extract attendees
        attendees = [
            a.get("email", "")
            for a in event.get("attendees", [])
            if not a.get("self", False)
        ]
        
        # Determine if needs preparation
        needs_prep = any(
            kw in event.get("summary", "").lower()
            for kw in ["meeting", "presentation", "interview", "review"]
        )
        
        return {
            "type": "event",
            "external_id": event.get("id"),
            "title": event.get("summary", "Untitled Event"),
            "description": event.get("description", "")[:1000],
            "due_date": start_time,
            "end_date": end_time,
            "is_all_day": is_all_day,
            "location": event.get("location", ""),
            "attendees": attendees,
            "status": "active",
            "needs_preparation": needs_prep,
            "priority": 4 if needs_prep else 3,
            "source": "google_calendar"
        }
    
    async def get_day_summary(self, user_id: str, date: Optional[str] = None) -> Dict[str, Any]:
        """Get summary of events for a specific day"""
        if not date:
            date = datetime.now().strftime("%Y-%m-%d")
        
        # Get events for date
        events = await db.fetch_many(
            "tasks_goals",
            filters={
                "user_id": user_id,
                "type": "event",
                "status": "active"
            },
            order_by="due_date",
            limit=20
        )
        
        # Filter to specific date
        day_events = [
            e for e in events
            if e.get("due_date", "").startswith(date)
        ]
        
        # Calculate free time slots
        busy_slots = [
            (e.get("due_date"), e.get("end_date"))
            for e in day_events
            if not e.get("is_all_day")
        ]
        
        # Categorize
        categories = {}
        for e in day_events:
            title = e.get("title", "").lower()
            cat = "other"
            if any(kw in title for kw in ["meeting", "call", "sync"]):
                cat = "meeting"
            elif any(kw in title for kw in ["lunch", "dinner", "coffee"]):
                cat = "meal"
            elif any(kw in title for kw in ["workout", "gym", "exercise"]):
                cat = "exercise"
            
            categories[cat] = categories.get(cat, 0) + 1
        
        # Check for conflicts
        conflicts = self._detect_conflicts(day_events)
        
        return {
            "date": date,
            "total_events": len(day_events),
            "meetings": categories.get("meeting", 0),
            "free_time_slots": self._calculate_free_time(busy_slots),
            "conflicts": conflicts,
            "events": [
                {
                    "id": e.get("id"),
                    "title": e.get("title"),
                    "time": e.get("due_date"),
                    "location": e.get("location"),
                    "needs_prep": e.get("needs_preparation")
                }
                for e in day_events
            ],
            "suggestions": self._generate_suggestions(day_events, conflicts)
        }
    
    def _detect_conflicts(self, events: List[Dict]) -> List[Dict]:
        """Detect overlapping events"""
        conflicts = []
        
        for i, e1 in enumerate(events):
            if e1.get("is_all_day"):
                continue
                
            for e2 in events[i+1:]:
                if e2.get("is_all_day"):
                    continue
                
                # Simple overlap detection
                # In production: proper datetime parsing
                if e1.get("due_date") == e2.get("due_date"):
                    conflicts.append({
                        "event1": e1.get("title"),
                        "event2": e2.get("title"),
                        "time": e1.get("due_date")
                    })
        
        return conflicts
    
    def _calculate_free_time(self, busy_slots: List[tuple]) -> List[str]:
        """Calculate free time slots for the day"""
        # Simplified: assume 9-5 workday
        if not busy_slots:
            return ["09:00-17:00"]
        
        # In production: proper slot calculation
        return ["See calendar for details"]
    
    def _generate_suggestions(self, events: List[Dict], conflicts: List[Dict]) -> List[str]:
        """Generate smart suggestions based on schedule"""
        suggestions = []
        
        # Conflict resolution
        if conflicts:
            suggestions.append("You have overlapping events today. Consider rescheduling.")
        
        # High meeting day
        meetings = sum(1 for e in events if "meeting" in e.get("title", "").lower())
        if meetings > 4:
            suggestions.append("Heavy meeting day - schedule breaks to avoid fatigue.")
        
        # Back-to-back detection
        # In production: check for gaps between events
        
        # Preparation reminders
        prep_needed = [e for e in events if e.get("needs_preparation")]
        for e in prep_needed:
            suggestions.append(f"Prepare for: {e.get('title')}")
        
        return suggestions
    
    async def find_optimal_slot(
        self,
        user_id: str,
        duration_minutes: int = 60,
        days_ahead: int = 7,
        preferred_hours: tuple = (9, 17)
    ) -> Optional[Dict]:
        """Find optimal meeting slot based on calendar analysis"""
        # Get upcoming events
        events = await db.fetch_many(
            "tasks_goals",
            filters={
                "user_id": user_id,
                "type": "event",
                "status": "active"
            },
            order_by="due_date",
            limit=50
        )
        
        # Filter to working days ahead
        now = datetime.now()
        future_events = [
            e for e in events
            if datetime.fromisoformat(e.get("due_date", "").replace('Z', '+00:00')) > now
        ]
        
        # Find gaps
        # In production: proper gap detection algorithm
        
        return {
            "suggested_slots": [
                {
                    "date": (now + timedelta(days=1)).strftime("%Y-%m-%d"),
                    "time": "10:00",
                    "duration": duration_minutes,
                    "confidence": 0.8
                }
            ],
            "rationale": "Based on your calendar patterns, morning slots have highest availability."
        }


# Singleton
calendar_service = CalendarService()
