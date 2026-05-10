"""
Chain 10: Ambient Monitoring Chain
Type: LLMChain
Trigger: Every 30 minutes (via daemon loop)
Model: Groq Llama 3.1 8B (fast, cheap)
Output: Proactive intelligence events published to Redis
"""
from typing import Any, Dict, Optional
import time
import json
from datetime import datetime, timedelta
from langchain_groq import ChatGroq
from langchain.schema import HumanMessage, SystemMessage

from app.config import settings
from app.chains.base import BaseChain, ChainType
from app.utils.logging import get_logger
from app.utils.database import db
from app.utils.cache import cache

logger = get_logger("ambient_monitoring_chain")


class AmbientMonitoringChain(BaseChain):
    """
    Ambient monitoring chain that runs every 30 minutes.
    Synthesizes world state + user context to generate
    proactive intelligence events.

    Monitors:
    - Pending tasks approaching deadlines
    - Unread high-urgency news
    - Financial alerts
    - Relationship check-ins due
    - Goal progress stalls
    """

    chain_type = ChainType.AMBIENT_MONITORING
    description = "Proactive intelligence synthesis every 30 minutes"

    def __init__(self):
        super().__init__()
        self.llm = None
        if settings.groq_api_key:
            self.llm = ChatGroq(
                api_key=settings.groq_api_key,
                model_name="llama-3.1-8b-instant",
                temperature=0.5,
                max_tokens=512
            )

    async def execute(
        self,
        input_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Run ambient monitoring scan.

        Args:
            input_data: {'user_id': str} or empty for all users
            context: Optional context

        Returns:
            Events generated
        """
        start_time = time.time()
        user_id = input_data.get("user_id")

        events_generated = []

        try:
            # Get users to monitor
            if user_id:
                users = [{"user_id": user_id}]
            else:
                users = await db.fetch_many("user_profile", limit=100)

            for user in users:
                uid = user.get("user_id")
                if not uid:
                    continue

                user_events = await self._scan_user(uid)
                events_generated.extend(user_events)

            elapsed_ms = int((time.time() - start_time) * 1000)
            logger.info(
                "Ambient monitoring complete",
                users_scanned=len(users),
                events_generated=len(events_generated),
                latency_ms=elapsed_ms
            )

            return {
                "response": {
                    "type": "ambient_report",
                    "content": f"Generated {len(events_generated)} proactive events.",
                    "structured_data": {
                        "events_generated": len(events_generated),
                        "users_scanned": len(users),
                        "events": events_generated[:5]  # Sample
                    }
                },
                "personality_mode": "neutral",
                "chain": self.chain_type.value,
                "model": "groq-llama-3.1-8b",
                "latency_ms": elapsed_ms,
                "tokens_used": 0,
                "sources": [],
                "events_count": len(events_generated)
            }

        except Exception as e:
            logger.error(f"Ambient monitoring error: {e}")
            return {
                "response": {"type": "text", "content": f"Monitoring error: {e}", "structured_data": {}},
                "personality_mode": "neutral",
                "chain": self.chain_type.value,
                "model": "error",
                "latency_ms": int((time.time() - start_time) * 1000),
                "tokens_used": 0,
                "sources": [],
                "events_count": 0
            }

    async def _scan_user(self, user_id: str) -> list:
        """Scan all monitoring dimensions for a user"""
        events = []

        # 1. Check overdue tasks
        task_events = await self._check_tasks(user_id)
        events.extend(task_events)

        # 2. Check undelivered urgent news
        news_events = await self._check_urgent_news(user_id)
        events.extend(news_events)

        # 3. Check financial alerts
        financial_events = await self._check_financial_alerts(user_id)
        events.extend(financial_events)

        # 4. Check relationship check-ins
        relationship_events = await self._check_relationships(user_id)
        events.extend(relationship_events)

        return events

    async def _check_tasks(self, user_id: str) -> list:
        """Check for overdue or approaching deadline tasks"""
        events = []
        now = datetime.now()

        tasks = await db.fetch_many(
            "tasks_goals",
            filters={"user_id": user_id, "status": "active"},
            order_by="due_date",
            ascending=True,
            limit=20
        )

        for task in tasks:
            due_str = task.get("due_date")
            if not due_str:
                continue

            try:
                due = datetime.fromisoformat(due_str.replace("Z", "+00:00").replace("+00:00", ""))
                days_until = (due - now).days

                if days_until < 0:
                    # Overdue
                    event = await self._create_event(
                        user_id=user_id,
                        event_type="task_overdue",
                        title=f"Overdue: {task.get('title', 'Task')}",
                        body=f"This task was due {abs(days_until)} days ago.",
                        urgency=7,
                        structured_data={"task_id": task.get("id"), "days_overdue": abs(days_until)}
                    )
                    if event:
                        events.append(event)

                elif days_until <= 1:
                    # Due today or tomorrow
                    event = await self._create_event(
                        user_id=user_id,
                        event_type="task_due_soon",
                        title=f"Due {'today' if days_until == 0 else 'tomorrow'}: {task.get('title', 'Task')}",
                        body=f"Don't forget: {task.get('title')} is due {'today' if days_until == 0 else 'tomorrow'}.",
                        urgency=6,
                        structured_data={"task_id": task.get("id"), "days_until": days_until}
                    )
                    if event:
                        events.append(event)

            except Exception as e:
                logger.debug(f"Task date parse error: {e}")

        return events

    async def _check_urgent_news(self, user_id: str) -> list:
        """Check for undelivered urgent news"""
        events = []

        news = await db.fetch_many(
            "news_articles",
            filters={"user_id": user_id, "delivered": False},
            order_by="urgency_score",
            ascending=False,
            limit=5
        )

        for article in news:
            urgency = article.get("urgency_score", 3)
            if urgency >= 7:
                event = await self._create_event(
                    user_id=user_id,
                    event_type="urgent_news",
                    title=article.get("title", "Breaking News"),
                    body=article.get("summary", "")[:300],
                    urgency=urgency,
                    structured_data={
                        "news_id": article.get("id"),
                        "url": article.get("url"),
                        "source": article.get("source_name")
                    }
                )
                if event:
                    events.append(event)
                    # Mark as delivered
                    await db.update(
                        "news_articles",
                        {"delivered": True},
                        {"id": article.get("id")}
                    )

        return events

    async def _check_financial_alerts(self, user_id: str) -> list:
        """Check for triggered financial alerts"""
        events = []

        assets = await db.fetch_many(
            "financial_tracking",
            filters={"user_id": user_id, "is_active": True, "alert_triggered": True},
            limit=10
        )

        for asset in assets:
            change = asset.get("price_change_24h", 0)
            event = await self._create_event(
                user_id=user_id,
                event_type="financial_alert",
                title=f"{asset.get('symbol')} moved {change:+.1f}%",
                body=f"{asset.get('symbol')} is at ${asset.get('current_price', 0):.2f} ({change:+.1f}% in 24h).",
                urgency=6,
                structured_data={
                    "symbol": asset.get("symbol"),
                    "price": asset.get("current_price"),
                    "change_24h": change
                }
            )
            if event:
                events.append(event)
                # Reset alert
                await db.update(
                    "financial_tracking",
                    {"alert_triggered": False},
                    {"id": asset.get("id")}
                )

        return events

    async def _check_relationships(self, user_id: str) -> list:
        """Check for relationship check-ins due"""
        events = []
        now = datetime.now()

        people = await db.fetch_many(
            "people_knowledge",
            filters={"user_id": user_id, "needs_attention": True},
            limit=5
        )

        for person in people:
            last_interaction = person.get("last_interaction_at")
            if last_interaction:
                try:
                    last = datetime.fromisoformat(last_interaction.replace("Z", ""))
                    days_since = (now - last).days

                    if days_since >= 30:
                        event = await self._create_event(
                            user_id=user_id,
                            event_type="relationship_checkin",
                            title=f"Check in with {person.get('name')}",
                            body=f"You haven't connected with {person.get('name')} in {days_since} days.",
                            urgency=4,
                            structured_data={
                                "person_id": person.get("id"),
                                "name": person.get("name"),
                                "days_since": days_since
                            }
                        )
                        if event:
                            events.append(event)
                except Exception:
                    pass

        return events

    async def _create_event(
        self,
        user_id: str,
        event_type: str,
        title: str,
        body: str,
        urgency: int,
        structured_data: Dict = None
    ) -> Optional[Dict]:
        """Create and store an event, publish to Redis"""
        try:
            # Check for duplicate (dedup_key)
            dedup_key = f"{event_type}:{user_id}:{title[:50]}"
            existing = await db.fetch_one("event_queue", {"dedup_key": dedup_key, "status": "pending"})
            if existing:
                return None  # Already queued

            # Generate personality-applied message
            tillu_message = await self._apply_personality(title, body, urgency)

            event_data = {
                "user_id": user_id,
                "event_type": event_type,
                "urgency": urgency,
                "source_agent": "ambient_monitoring",
                "title": title,
                "body": body,
                "tillu_message": tillu_message,
                "structured_data": structured_data or {},
                "actions": ["acknowledge", "dismiss"],
                "status": "pending",
                "dedup_key": dedup_key,
                "generated_at": datetime.now().isoformat()
            }

            result = await db.insert("event_queue", event_data)

            # Publish to Redis
            channel = "tillu:events:urgent" if urgency >= 8 else (
                "tillu:events:normal" if urgency >= 4 else "tillu:events:low"
            )
            await cache.publish(channel, {**event_data, "id": result[0]["id"] if result else None})

            return event_data

        except Exception as e:
            logger.error(f"Event creation error: {e}")
            return None

    async def _apply_personality(self, title: str, body: str, urgency: int) -> str:
        """Apply personality to event message"""
        if not self.llm or urgency >= 9:
            return f"{title}. {body}"

        try:
            prompt = f"""Rewrite this notification in TILLU's voice: warm, direct, slightly witty.
Keep it under 2 sentences.

Title: {title}
Body: {body}

Rewritten:"""

            response = await self.llm.ainvoke([HumanMessage(content=prompt)])
            return response.content.strip()

        except Exception:
            return f"{title}. {body}"
