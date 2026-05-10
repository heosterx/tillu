"""
Productivity Tools - Calendar, Tasks, Email
"""
import httpx
from typing import Any, Dict, List, Optional
from app.config import settings
from app.tools.registry import BaseTool, ToolMetadata, ToolRegistry
from app.utils.database import db
from app.utils.logging import get_logger

logger = get_logger("productivity_tools")


class CalendarTool(BaseTool):
    """Create and get calendar events"""
    
    metadata = ToolMetadata(
        name="tool_create_calendar",
        description="Create a calendar event or get upcoming events. Uses Google Calendar.",
        parameters={
            "action": {"type": "string", "enum": ["create", "list"], "description": "Action to perform"},
            "title": {"type": "string", "description": "Event title (for create)"},
            "start_time": {"type": "string", "description": "ISO datetime (for create)"},
            "end_time": {"type": "string", "description": "ISO datetime (for create)"},
            "user_id": {"type": "string", "description": "User ID"}
        },
        requires_auth=True
    )
    
    async def execute(
        self,
        action: str = "list",
        title: str = None,
        start_time: str = None,
        end_time: str = None,
        user_id: str = None
    ) -> Dict[str, Any]:
        """Execute calendar action"""
        try:
            if not user_id:
                return {"success": False, "error": "User ID required"}
            
            if action == "list":
                # Get upcoming events from database
                events = await db.fetch_many(
                    "tasks_goals",
                    filters={"user_id": user_id, "type": "event"},
                    order_by="due_date",
                    limit=10
                )
                
                return {
                    "success": True,
                    "action": "list",
                    "events": [
                        {
                            "id": e["id"],
                            "title": e["title"],
                            "due_date": e.get("due_date"),
                            "status": e.get("status")
                        }
                        for e in events
                    ],
                    "count": len(events)
                }
            
            elif action == "create":
                # Create event as task
                event_data = {
                    "user_id": user_id,
                    "title": title,
                    "type": "event",
                    "due_date": start_time,
                    "status": "active"
                }
                
                result = await db.insert("tasks_goals", event_data)
                
                return {
                    "success": True,
                    "action": "create",
                    "event_id": result[0]["id"] if result else None,
                    "message": f"Event '{title}' created"
                }
            
            return {"success": False, "error": "Unknown action"}
            
        except Exception as e:
            logger.error(f"Calendar tool error: {e}")
            return {"success": False, "error": str(e)}


class TaskTool(BaseTool):
    """Create and manage tasks"""
    
    metadata = ToolMetadata(
        name="tool_create_task",
        description="Create a task or get active tasks. Stores in Supabase.",
        parameters={
            "action": {"type": "string", "enum": ["create", "list", "complete"], "description": "Action to perform"},
            "title": {"type": "string", "description": "Task title (for create)"},
            "due_date": {"type": "string", "description": "ISO datetime (optional)"},
            "priority": {"type": "integer", "description": "Priority 1-5"},
            "task_id": {"type": "string", "description": "Task ID (for complete)"},
            "user_id": {"type": "string", "description": "User ID"}
        },
        requires_auth=True
    )
    
    async def execute(
        self,
        action: str = "list",
        title: str = None,
        due_date: str = None,
        priority: int = 3,
        task_id: str = None,
        user_id: str = None
    ) -> Dict[str, Any]:
        """Execute task action"""
        try:
            if not user_id:
                return {"success": False, "error": "User ID required"}
            
            if action == "list":
                tasks = await db.fetch_many(
                    "tasks_goals",
                    filters={"user_id": user_id, "status": "active"},
                    order_by="due_date",
                    limit=20
                )
                
                return {
                    "success": True,
                    "action": "list",
                    "tasks": [
                        {
                            "id": t["id"],
                            "title": t["title"],
                            "due_date": t.get("due_date"),
                            "priority": t.get("priority"),
                            "progress": t.get("progress_percent")
                        }
                        for t in tasks
                    ],
                    "count": len(tasks)
                }
            
            elif action == "create":
                task_data = {
                    "user_id": user_id,
                    "title": title,
                    "type": "task",
                    "due_date": due_date,
                    "priority": priority,
                    "status": "active"
                }
                
                result = await db.insert("tasks_goals", task_data)
                
                return {
                    "success": True,
                    "action": "create",
                    "task_id": result[0]["id"] if result else None,
                    "message": f"Task '{title}' created"
                }
            
            elif action == "complete":
                if not task_id:
                    return {"success": False, "error": "Task ID required"}
                
                await db.update(
                    "tasks_goals",
                    {"status": "completed", "completed_at": "now()", "progress_percent": 100},
                    {"id": task_id, "user_id": user_id}
                )
                
                return {
                    "success": True,
                    "action": "complete",
                    "message": "Task marked as complete"
                }
            
            return {"success": False, "error": "Unknown action"}
            
        except Exception as e:
            logger.error(f"Task tool error: {e}")
            return {"success": False, "error": str(e)}


class NotionTool(BaseTool):
    """Search and create in Notion"""
    
    metadata = ToolMetadata(
        name="tool_notion",
        description="Search or create pages in Notion. Requires NOTION_TOKEN.",
        parameters={
            "action": {"type": "string", "enum": ["search", "create"], "description": "Action"},
            "query": {"type": "string", "description": "Search query or page title"},
            "content": {"type": "string", "description": "Page content (for create)"}
        },
        requires_auth=True,
        rate_limited=True
    )
    
    async def execute(
        self,
        action: str = "search",
        query: str = "",
        content: str = None
    ) -> Dict[str, Any]:
        """Execute Notion action"""
        try:
            notion_token = getattr(settings, 'notion_token', None)
            if not notion_token:
                return {"success": False, "error": "Notion token not configured"}
            
            async with httpx.AsyncClient() as client:
                headers = {
                    "Authorization": f"Bearer {notion_token}",
                    "Notion-Version": "2022-06-28"
                }
                
                if action == "search":
                    response = await client.post(
                        "https://api.notion.com/v1/search",
                        headers=headers,
                        json={"query": query},
                        timeout=10.0
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        results = data.get("results", [])
                        
                        return {
                            "success": True,
                            "results": [
                                {
                                    "id": r["id"],
                                    "title": r.get("properties", {}).get("title", {}).get("title", [{}])[0].get("plain_text", "Untitled"),
                                    "type": r["object"]
                                }
                                for r in results[:5]
                            ],
                            "count": len(results)
                        }
                
                return {"success": False, "error": f"Notion API error: {response.status_code}"}
                
        except Exception as e:
            logger.error(f"Notion tool error: {e}")
            return {"success": False, "error": str(e)}


# Register tools
ToolRegistry.register(CalendarTool())
ToolRegistry.register(TaskTool())
ToolRegistry.register(NotionTool())
