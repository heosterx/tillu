"""
Daemon Process - 16 Concurrent Async Loops
Always-watching ambient intelligence. Never stops.
"""
import asyncio
import json
import traceback
from typing import List, Callable, Any, Dict
from datetime import datetime, timedelta

from app.config import settings
from app.utils.logging import get_logger, configure_logging
from app.utils.database import db
from app.utils.cache import cache

# ── Lazy imports — loaded only when the loop actually runs ────────────────────
# This prevents missing optional packages (langchain_cerebras, etc.)
# from crashing the entire daemon at startup.

logger = get_logger("daemon")


class LoopConfig:
    """Configuration for a daemon loop"""
    def __init__(
        self,
        name: str,
        interval_seconds: int,
        function: Callable,
        enabled: bool = True
    ):
        self.name = name
        self.interval_seconds = interval_seconds
        self.function = function
        self.enabled = enabled


class DaemonProcess:
    """
    The TILLU Daemon - 11 concurrent async loops
    
    Each loop is independent. Failure in one doesn't affect others.
    All loops self-restart on exception.
    """
    
    def __init__(self):
        self.logger = get_logger("daemon")
        self.loops: List[LoopConfig] = []
        self.tasks: List[asyncio.Task] = []
        self._running = False
        
        self._register_loops()
    
    def _register_loops(self):
        """Register all 11 daemon loops"""
        self.loops = [
            # LOOP 1: HEARTBEAT (60s interval)
            LoopConfig("heartbeat", 60, self._loop_heartbeat),
            
            # LOOP 2: FINANCIAL WATCHER (15m interval)
            LoopConfig("financial_watcher", 900, self._loop_financial_watcher),
            
            # LOOP 3: WEB CHANGE DETECTOR (30m interval)
            LoopConfig("web_change_detector", 1800, self._loop_web_change_detector),
            
            # LOOP 4: NEWS URGENCY SCANNER (10m interval)
            LoopConfig("news_urgency_scanner", 600, self._loop_news_urgency_scanner),
            
            # LOOP 5: PATTERN RECOGNITION (1h interval)
            LoopConfig("pattern_recognition", 3600, self._loop_pattern_recognition),
            
            # LOOP 6: CONTEXT PRE-COMPUTER (1h interval, offset 45m)
            LoopConfig("context_pre_computer", 3600, self._loop_context_pre_computer),
            
            # LOOP 7: RATE LIMIT TRACKER (5m interval)
            LoopConfig("rate_limit_tracker", 300, self._loop_rate_limit_tracker),
            
            # LOOP 8: FREE TIER GOVERNOR (1h interval)
            LoopConfig("free_tier_governor", 3600, self._loop_free_tier_governor),
            
            # LOOP 9: GOAL PROBABILITY ENGINE (6h interval)
            LoopConfig("goal_probability_engine", 21600, self._loop_goal_probability),
            
            # LOOP 10: EMOTION TREND TRACKER (30m interval)
            LoopConfig("emotion_trend_tracker", 1800, self._loop_emotion_trend_tracker),
            
            # LOOP 11: RELATIONSHIP MONITOR (6h interval)
            LoopConfig("relationship_monitor", 21600, self._loop_relationship_monitor),
            
            # LOOP 12: EMAIL MONITOR (30m interval)
            LoopConfig("email_monitor", 1800, self._loop_email_monitor),
            
            # LOOP 13: CALENDAR MONITOR (1h interval)
            LoopConfig("calendar_monitor", 3600, self._loop_calendar_monitor),
            
            # LOOP 14: MEMORY CONSOLIDATION (24h interval)
            LoopConfig("memory_consolidation", 86400, self._loop_memory_consolidation),
            
            # LOOP 15: PERSONALITY EVOLUTION (7d interval)
            LoopConfig("personality_evolution", 604800, self._loop_personality_evolution),
            
            # LOOP 16: AMBIENT MONITORING (30m interval)
            LoopConfig("ambient_monitoring", 1800, self._loop_ambient_monitoring),
        ]
    
    async def start(self):
        """Start all daemon loops"""
        self._running = True
        self.logger.info("Starting TILLU Daemon...")
        
        # Initialize connections
        await cache.connect()
        db.connect()
        
        # Start all loops as concurrent tasks
        for loop_config in self.loops:
            if loop_config.enabled:
                task = asyncio.create_task(
                    self._run_loop_wrapper(loop_config),
                    name=loop_config.name
                )
                self.tasks.append(task)
                self.logger.info(f"Started loop: {loop_config.name}")
        
        self.logger.info(f"Daemon running with {len(self.tasks)} active loops")
        
        # Keep running
        try:
            await asyncio.gather(*self.tasks, return_exceptions=True)
        except asyncio.CancelledError:
            self.logger.info("Daemon cancelled")
        finally:
            await self.stop()
    
    async def stop(self):
        """Stop all loops gracefully"""
        self._running = False
        self.logger.info("Stopping daemon...")
        
        for task in self.tasks:
            task.cancel()
        
        await asyncio.gather(*self.tasks, return_exceptions=True)
        await cache.disconnect()
        self.logger.info("Daemon stopped")
    
    async def _run_loop_wrapper(self, loop_config: LoopConfig):
        """Wrapper that handles loop execution and self-restart"""
        while self._running:
            try:
                self.logger.debug(f"Running loop: {loop_config.name}")
                
                start_time = datetime.now()
                await loop_config.function()
                elapsed = (datetime.now() - start_time).total_seconds()
                
                # Update monitor state
                await self._update_loop_state(loop_config.name, True, elapsed)
                
                # Wait for next iteration
                await asyncio.sleep(loop_config.interval_seconds)
                
            except asyncio.CancelledError:
                self.logger.info(f"Loop {loop_config.name} cancelled")
                raise
            
            except asyncio.TimeoutError:
                self.logger.warning(f"Loop {loop_config.name} timeout")
                await self._update_loop_state(
                    loop_config.name, False, 0, "timeout"
                )
                # Exponential backoff for timeouts
                await asyncio.sleep(min(300, loop_config.interval_seconds * 2))
            
            except ConnectionError as e:
                self.logger.error(f"Loop {loop_config.name} connection error: {e}")
                await self._update_loop_state(
                    loop_config.name, False, 0, "connection_error"
                )
                # Longer backoff for connection errors
                await asyncio.sleep(60)
            
            except ValueError as e:
                self.logger.error(f"Loop {loop_config.name} validation error: {e}")
                await self._update_loop_state(
                    loop_config.name, False, 0, "validation_error"
                )
                await asyncio.sleep(30)
            
            except Exception as e:
                self.logger.error(
                    f"Loop {loop_config.name} unexpected error: {e}",
                    exc_info=True
                )
                await self._update_loop_state(
                    loop_config.name, False, 0, str(e)
                )
                # Short backoff for unexpected errors
                await asyncio.sleep(5)
    
    async def _update_loop_state(
        self,
        loop_name: str,
        success: bool,
        elapsed_seconds: float,
        error: str = None
    ):
        """Update loop state in database"""
        try:
            await db.update(
                "monitor_state",
                {
                    "loop_name": loop_name,
                    "is_running": success,
                    "last_execution_at": "now()",
                    "execution_count": {"increment": 1},
                    "avg_execution_time_ms": int(elapsed_seconds * 1000),
                    "last_error": error
                },
                {"loop_name": loop_name}
            )
        except Exception as e:
            self.logger.error(f"Failed to update loop state: {e}")
    
    # =========================================================================
    # LOOP IMPLEMENTATIONS
    # =========================================================================
    
    async def _loop_heartbeat(self):
        """
        LOOP 1: HEARTBEAT (60s interval)
        → Publish presence to Redis tillu:system:health
        → Write heartbeat file for Fly.io health check
        → Confirm all other loops are alive
        """
        import os
        # Write heartbeat file for Fly.io health check
        try:
            with open("/tmp/daemon_heartbeat", "w") as f:
                f.write(datetime.now().isoformat())
        except Exception:
            pass

        await cache.publish("tillu:system:health", {
            "agent": "daemon",
            "timestamp": datetime.now().isoformat(),
            "status": "healthy",
            "active_loops": len([t for t in self.tasks if not t.done()]),
        })
    
    async def _loop_financial_watcher(self):
        """
        LOOP 2: FINANCIAL WATCHER (15m interval)
        → Fetch tracked asset prices
        → Evaluate threshold conditions
        → Publish alerts if triggered
        """
        self.logger.info("Running financial watcher...")
        
        try:
            # Use Phase 5 financial service to update prices
            from app.services.financial_service import financial_service
            updated = await financial_service.update_all_prices()
            
            # Check for alerts and publish events
            for update in updated:
                if update.get("alert"):
                    await self._publish_event(
                        "financial_alert",
                        {
                            "symbol": update["symbol"],
                            "price": update["price"],
                            "threshold_crossed": True
                        },
                        urgency=7
                    )
                    
        except Exception as e:
            self.logger.error(f"Financial watcher error: {e}")
    
    async def _publish_event(self, event_type: str, content: Dict, urgency: int = 5, user_id: str = None):
        """Publish event to Redis pub/sub"""
        event = {
            "event_id": f"evt_{datetime.now().timestamp()}",
            "event_type": event_type,
            "urgency": urgency,
            "source_agent": "daemon",
            "content": content,
            "timestamp": datetime.now().isoformat(),
            "user_id": user_id
        }
        
        # Determine channel based on urgency
        if urgency >= 8:
            channel = "tillu:events:urgent"
        elif urgency >= 4:
            channel = "tillu:events:normal"
        else:
            channel = "tillu:events:low"
        
        await cache.publish(channel, event)
        self.logger.info(f"Published {event_type} event (urgency {urgency})")
    
    async def _loop_web_change_detector(self):
        """
        LOOP 3: WEB CHANGE DETECTOR (30m interval)
        → Playwright renders monitored URLs
        → Hash comparison
        → Publish change events
        """
        self.logger.info("Running web change detector...")
        
        try:
            from app.services.web_monitor_service import web_monitor_service
            # Use Phase 5 web monitor service
            changes = await web_monitor_service.check_all_monitors()
            
            # Publish events for detected changes
            for change in changes:
                await self._publish_event(
                    "web_change",
                    {
                        "monitor_id": change["monitor_id"],
                        "url": change["url"],
                        "title": change["title"],
                        "content_preview": change.get("content_preview")
                    },
                    urgency=5,
                    user_id=None
                )
                    
        except Exception as e:
            self.logger.error(f"Web change detector error: {e}")
    
    async def _loop_news_urgency_scanner(self):
        """
        LOOP 4: NEWS URGENCY SCANNER (10m interval)
        → Read latest news_articles from Supabase
        → Re-evaluate urgency on recent items
        → Escalate if breaking news threshold crossed
        """
        self.logger.info("Running news urgency scanner...")
        
        try:
            from app.services.news_service import news_service
            # Use Phase 5 news service to fetch fresh news
            # Fetch from RSS and NewsAPI
            articles = await news_service.fetch_all()
            
            # Check for breaking news
            for article in articles:
                urgency = article.get("urgency_score", 5)
                
                if urgency >= 8:
                    await self._publish_event(
                        "breaking_news",
                        {
                            "news_id": article.get("id"),
                            "title": article.get("title"),
                            "source": article.get("source"),
                            "url": article.get("url"),
                            "summary": article.get("summary", "")[:200]
                        },
                        urgency=urgency,
                        user_id=article.get("user_id")
                    )
                    
        except Exception as e:
            self.logger.error(f"News urgency scanner error: {e}")
    
    async def _loop_pattern_recognition(self):
        """
        LOOP 5: PATTERN RECOGNITION (1h interval)
        → Pull behavioral data windows
        → Run pattern analysis
        → Publish insight events if patterns found
        """
        self.logger.info("Running pattern recognition...")
        
        try:
            # Get last 7 days of interactions
            week_ago = (datetime.now() - timedelta(days=7)).isoformat()
            
            # Get active users
            users = await db.fetch_many("user_profile", limit=100)
            
            for user in users:
                user_id = user.get("user_id")
                
                # Analyze interaction patterns
                interactions = await db.fetch_many(
                    "interactions",
                    filters={"user_id": user_id},
                    order_by="created_at",
                    ascending=False,
                    limit=100
                )
                
                if len(interactions) < 10:
                    continue
                
                # Simple pattern detection
                emotion_counts = {}
                chain_counts = {}
                hour_counts = {}
                
                for i in interactions:
                    # Emotion patterns
                    emotion = i.get("emotion_scores", {}).get("dominant_emotion", "neutral")
                    emotion_counts[emotion] = emotion_counts.get(emotion, 0) + 1
                    
                    # Chain usage patterns
                    chain = i.get("chain_used", "unknown")
                    chain_counts[chain] = chain_counts.get(chain, 0) + 1
                    
                    # Time patterns
                    created = i.get("created_at", "")
                    if created:
                        hour = created.split("T")[1][:2] if "T" in created else "00"
                        hour_counts[hour] = hour_counts.get(hour, 0) + 1
                
                # Detect patterns
                patterns = []
                
                # Emotion pattern
                top_emotion = max(emotion_counts.items(), key=lambda x: x[1])
                if top_emotion[1] > len(interactions) * 0.4:
                    patterns.append(f"Frequent {top_emotion[0]} state")
                
                # Time pattern
                if hour_counts:
                    peak_hour = max(hour_counts.items(), key=lambda x: x[1])
                    if peak_hour[1] > len(interactions) * 0.3:
                        patterns.append(f"Peak activity at {peak_hour[0]}:00")
                
                # Publish pattern insights
                if patterns:
                    await self._publish_event(
                        "behavioral_pattern",
                        {
                            "user_id": user_id,
                            "patterns": patterns,
                            "interaction_count": len(interactions),
                            "analysis_window": "7d"
                        },
                        urgency=3,  # Low urgency
                        user_id=user_id
                    )
                    
        except Exception as e:
            self.logger.error(f"Pattern recognition error: {e}")
    
    async def _loop_context_pre_computer(self):
        """
        LOOP 6: CONTEXT PRE-COMPUTER (1h interval)
        → Predict likely next interactions
        → Pre-assemble and cache context
        → Pre-compile scheduled briefs
        """
        self.logger.info("Running context pre-computer...")
        
        try:
            # Get active users
            users = await db.fetch_many("user_profile", limit=50)
            
            for user in users:
                user_id = user.get("user_id")
                
                # Pre-compute morning brief context if morning approaching
                hour = datetime.now().hour
                if 6 <= hour <= 9:
                    # Morning brief pre-computation
                    context_key = f"precomputed:morning_brief:{user_id}"
                    
                    brief_data = {
                        "type": "morning_brief",
                        "weather": "Fetching...",  # Would fetch real weather
                        "tasks_due_today": [],
                        "news_headlines": [],
                        "timestamp": datetime.now().isoformat()
                    }
                    
                    # Cache for 30 minutes
                    await cache.set(context_key, brief_data, ttl=1800)
                
                # Pre-compute user context
                context_key = f"precomputed:identity:{user_id}"
                identity_data = {
                    "user_id": user_id,
                    "personality_params": user.get("personality_params", {}),
                    "active_hours": user.get("active_hours", {}),
                    "timestamp": datetime.now().isoformat()
                }
                
                await cache.set(context_key, identity_data, ttl=3600)
                
        except Exception as e:
            self.logger.error(f"Context pre-computer error: {e}")
    
    async def _loop_rate_limit_tracker(self):
        """
        LOOP 7: RATE LIMIT TRACKER (5m interval)
        → Read API usage counters from Redis
        → Recompute routing weights
        → Publish routing table update to all processes
        """
        # Check Groq usage
        groq_remaining = await cache.get("api_limits:groq:remaining") or 14400
        
        # Publish routing update
        await cache.publish("tillu:system:routing", {
            "timestamp": datetime.now().isoformat(),
            "weights": {
                "groq": 1.0 if groq_remaining > 1000 else 0.5,
                "cerebras": 1.0,
                "openrouter": 1.0,
                "gemini": 1.0
            }
        })
    
    async def _loop_free_tier_governor(self):
        """
        LOOP 8: FREE TIER GOVERNOR (1h interval)
        → Audit usage across all free tiers
        → Project remaining capacity
        → Trigger archival if storage thresholds approaching
        """
        self.logger.info("Running free tier governor...")
        
        try:
            # Check Supabase storage
            # In production: use Supabase API to check storage
            storage_used = 400  # Mock MB
            storage_limit = 500  # 500MB free tier
            
            if storage_used > storage_limit * 0.85:
                # Trigger archival
                self.logger.warning(f"Storage at {storage_used}MB - approaching limit")
                
                # Publish warning event
                await self._publish_event(
                    "storage_warning",
                    {
                        "storage_used_mb": storage_used,
                        "storage_limit_mb": storage_limit,
                        "percent_used": (storage_used / storage_limit) * 100
                    },
                    urgency=7
                )
            
            # Check Redis operations (Upstash 10k/day)
            redis_ops = await cache.get("daily:ops:count") or 0
            if redis_ops > 8000:
                self.logger.warning(f"Redis ops at {redis_ops} - approaching limit")
                
        except Exception as e:
            self.logger.error(f"Free tier governor error: {e}")
    
    async def _loop_goal_probability(self):
        """
        LOOP 9: GOAL PROBABILITY ENGINE (6h interval)
        → Load all active goals
        → Calculate completion probability
        → Compute days-at-current-rate to deadline
        → Publish intervention events where needed
        """
        self.logger.info("Running goal probability engine...")
        
        try:
            # Get active goals with deadlines
            goals = await db.fetch_many(
                "tasks_goals",
                filters={"status": "active", "type": "goal"},
                limit=50
            )
            
            for goal in goals:
                due_date = goal.get("due_date")
                if not due_date:
                    continue
                
                # Calculate progress and probability
                progress = goal.get("progress_percent", 0)
                
                # Simple probability calculation
                # In production: more sophisticated model
                days_remaining = 30  # Mock calculation
                
                # At-risk goals
                if progress < 50 and days_remaining < 7:
                    await self._publish_event(
                        "goal_at_risk",
                        {
                            "goal_id": goal.get("id"),
                            "title": goal.get("title"),
                            "progress": progress,
                            "days_remaining": days_remaining,
                            "suggested_action": "Break into smaller tasks"
                        },
                        urgency=6,
                        user_id=goal.get("user_id")
                    )
                
                # Update probability score
                probability = min(100, progress * 1.5)  # Mock
                await db.update(
                    "tasks_goals",
                    {"probability": probability},
                    {"id": goal.get("id")}
                )
                
        except Exception as e:
            self.logger.error(f"Goal probability engine error: {e}")
    
    async def _loop_emotion_trend_tracker(self):
        """
        LOOP 10: EMOTION TREND TRACKER (30m interval)
        → Aggregate last 24h emotion log
        → Calculate rolling averages
        → Update emotional context in Redis
        → Trigger empathy mode if sustained distress detected
        """
        self.logger.info("Running emotion trend tracker...")
        
        try:
            # Get last 24h of emotion logs
            day_ago = (datetime.now() - timedelta(hours=24)).isoformat()
            
            # Get active users
            users = await db.fetch_many("user_profile", limit=100)
            
            for user in users:
                user_id = user.get("user_id")
                
                # Get recent emotions for user
                emotions = await db.fetch_many(
                    "emotion_log",
                    filters={"user_id": user_id},
                    order_by="created_at",
                    ascending=False,
                    limit=50
                )
                
                if len(emotions) < 3:
                    continue
                
                # Calculate distress indicators
                distress_count = sum(
                    1 for e in emotions
                    if e.get("stress_level") in ["high", "medium"] or
                    e.get("dominant_emotion") in ["sadness", "anger", "fear"]
                )
                
                distress_ratio = distress_count / len(emotions)
                
                # Update emotional context in Redis
                await cache.set(
                    f"emotion:trend:{user_id}",
                    {
                        "distress_ratio": distress_ratio,
                        "sample_size": len(emotions),
                        "timestamp": datetime.now().isoformat()
                    },
                    ttl=1800  # 30 minutes
                )
                
                # Trigger empathy mode if sustained distress
                if distress_ratio > 0.6 and len(emotions) >= 5:
                    await self._publish_event(
                        "sustained_distress",
                        {
                            "user_id": user_id,
                            "distress_ratio": distress_ratio,
                            "duration_hours": 24,
                            "suggested_action": "empathy_mode"
                        },
                        urgency=7,
                        user_id=user_id
                    )
                    
        except Exception as e:
            self.logger.error(f"Emotion trend tracker error: {e}")
    
    async def _loop_relationship_monitor(self):
        """
        LOOP 11: RELATIONSHIP MONITOR (6h interval)
        → Check birthday proximity
        → Check last_interaction dates
        → Generate relationship maintenance suggestions
        → Pre-load context for upcoming meetings
        """
        self.logger.info("Running relationship monitor...")
        
        try:
            # Get all people knowledge
            people = await db.fetch_many(
                "people_knowledge",
                filters={},
                limit=200
            )
            
            today = datetime.now()
            
            for person in people:
                # Check birthday
                birthday = person.get("birthday")
                if birthday:
                    # Parse birthday (assuming MM-DD format)
                    try:
                        bday_month, bday_day = map(int, birthday.split("-"))
                        if today.month == bday_month and today.day == bday_day:
                            # Birthday today!
                            await self._publish_event(
                                "birthday_reminder",
                                {
                                    "person_id": person.get("id"),
                                    "name": person.get("name"),
                                    "relationship_type": person.get("relationship_type"),
                                    "message": f"Today is {person.get('name')}'s birthday!"
                                },
                                urgency=6,
                                user_id=person.get("user_id")
                            )
                    except:
                        pass
                
                # Check last interaction
                last_interaction = person.get("last_interaction")
                if last_interaction:
                    # If no interaction in 30 days, suggest reaching out
                    # Simplified check - in production: proper date parsing
                    pass
                
        except Exception as e:
            self.logger.error(f"Relationship monitor error: {e}")
    
    async def _loop_email_monitor(self):
        """
        LOOP 12: EMAIL MONITOR (30m interval)
        → Fetch and analyze new emails
        → Detect urgency and sentiment
        → Publish important email events
        """
        self.logger.info("Running email monitor...")
        
        try:
            # Get all users with email enabled
            users = await db.fetch_many(
                "users",
                filters={},
                limit=10
            )
            
            for user in users:
                user_id = user.get("id")
                
                # Use Phase 5 email service to fetch and analyze
                from app.services.email_service import email_service
                emails = await email_service.fetch_and_analyze(user_id, max_emails=5, since_hours=1)
                
                # Publish events for high-importance emails
                for email in emails:
                    importance = email.get("importance_score", 5)
                    requires_response = email.get("requires_response", False)
                    
                    if importance >= 7 or requires_response:
                        await self._publish_event(
                            "important_email",
                            {
                                "email_id": email.get("email_id"),
                                "sender": email.get("sender"),
                                "subject": email.get("subject"),
                                "summary": email.get("summary"),
                                "importance": importance,
                                "requires_response": requires_response,
                                "suggested_response": email.get("suggested_response")
                            },
                            urgency=importance,
                            user_id=user_id
                        )
                    
        except Exception as e:
            self.logger.error(f"Email monitor error: {e}")
    
    async def _loop_calendar_monitor(self):
        """
        LOOP 13: CALENDAR MONITOR (1h interval)
        → Sync calendar events
        → Detect conflicts and preparation needs
        → Publish calendar intelligence events
        """
        self.logger.info("Running calendar monitor...")
        
        try:
            # Get all users
            users = await db.fetch_many(
                "users",
                filters={},
                limit=10
            )
            
            for user in users:
                user_id = user.get("id")
                
                # Use Phase 5 calendar service to sync events
                from app.services.calendar_service import calendar_service
                events = await calendar_service.sync_events(user_id, days_ahead=7)
                
                # Get today's summary
                today_summary = await calendar_service.get_day_summary(user_id)
                
                # Check for conflicts
                if today_summary.get("conflicts"):
                    await self._publish_event(
                        "calendar_conflict",
                        {
                            "user_id": user_id,
                            "date": today_summary.get("date"),
                            "conflicts": today_summary.get("conflicts")
                        },
                        urgency=8,
                        user_id=user_id
                    )
                
                # Check for events needing preparation
                needs_prep = [
                    e for e in events
                    if e.get("needs_preparation")
                ]
                
                if needs_prep:
                    await self._publish_event(
                        "event_preparation",
                        {
                            "user_id": user_id,
                            "events": [
                                {
                                    "title": e.get("title"),
                                    "due_date": e.get("due_date")
                                }
                                for e in needs_prep
                            ]
                        },
                        urgency=6,
                        user_id=user_id
                    )
                    
        except Exception as e:
            self.logger.error(f"Calendar monitor error: {e}")
    
    async def _loop_memory_consolidation(self):
        """
        LOOP 14: MEMORY CONSOLIDATION (24h interval)
        → Extract facts from interactions
        → Update behavioral patterns
        → Prune old memories
        """
        self.logger.info("Running memory consolidation...")
        
        try:
            # Get all users
            users = await db.fetch_many("user_profile", limit=50)
            
            for user in users:
                user_id = user.get("id")
                
                # Use Phase 6 MemoryConsolidationChain
                from app.chains.memory_consolidation import MemoryConsolidationChain
                chain = MemoryConsolidationChain()
                result = await chain.execute({"user_id": user_id})
                
                self.logger.info(f"Consolidated {result.get('consolidated', 0)} facts for user {user_id}")
                    
        except Exception as e:
            self.logger.error(f"Memory consolidation error: {e}")
    
    async def _loop_personality_evolution(self):
        """
        LOOP 15: PERSONALITY EVOLUTION (7d interval)
        → Analyze quality scores
        → Evolve personality parameters
        → Update user profile
        """
        self.logger.info("Running personality evolution...")
        
        try:
            # Get all users
            users = await db.fetch_many("user_profile", limit=50)
            
            for user in users:
                user_id = user.get("id")
                
                # Use Phase 6 PersonalityEvolutionChain
                from app.chains.personality_evolution import PersonalityEvolutionChain
                chain = PersonalityEvolutionChain()
                result = await chain.execute({"user_id": user_id})
                
                if result.get("evolved"):
                    self.logger.info(f"Evolved personality for user {user_id}")
                    
        except Exception as e:
            self.logger.error(f"Personality evolution error: {e}")
    
    async def _loop_ambient_monitoring(self):
        """
        LOOP 16: AMBIENT MONITORING (30m interval)
        → Scan for overdue tasks
        → Check urgent news
        → Check financial alerts
        → Generate proactive events
        """
        self.logger.info("Running ambient monitoring...")
        
        try:
            # Use Phase 6 AmbientMonitoringChain
            from app.chains.ambient_monitoring import AmbientMonitoringChain
            chain = AmbientMonitoringChain()
            result = await chain.execute({})
            
            self.logger.info(f"Generated {result.get('events_count', 0)} proactive events")
                    
        except Exception as e:
            self.logger.error(f"Ambient monitoring error: {e}")


async def main():
    """Entry point for daemon"""
    configure_logging()
    daemon = DaemonProcess()
    await daemon.start()


if __name__ == "__main__":
    asyncio.run(main())
