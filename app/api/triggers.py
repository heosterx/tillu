"""
TILLU Auto-Trigger API
=======================
Internal endpoints called by cron-job.org / Render cron jobs.
These fire WITHOUT user input — they are TILLU's autonomous actions.

All endpoints are protected by TILLU_CRON_SECRET header.
Set TILLU_CRON_SECRET in your environment variables.
"""

from __future__ import annotations

import os
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel

from app.core.indian_rules import get_current_ist_context, format_datetime_full
from app.core.timetable import TIMETABLE, get_entry, get_cron_table
from app.utils.logging import get_logger

logger = get_logger("triggers")
router = APIRouter(prefix="/internal/trigger", tags=["triggers"])

IST = ZoneInfo("Asia/Kolkata")
CRON_SECRET = os.environ.get("TILLU_CRON_SECRET", "")


def _verify_secret(x_cron_secret: str | None) -> None:
    """Verify the cron secret header."""
    if CRON_SECRET and x_cron_secret != CRON_SECRET:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid cron secret / गलत cron secret",
        )


class TriggerResponse(BaseModel):
    triggered: str
    time_ist: str
    status: str
    message_hi: str
    message_en: str


# ── Morning Brief ─────────────────────────────────────────────────────────────

@router.post("/morning-brief", response_model=TriggerResponse)
async def trigger_morning_brief(
    x_cron_secret: str | None = Header(default=None),
):
    """
    WF-02: Morning Intelligence Brief
    Fires at 7:00 AM IST daily.
    Sends weather + calendar + tasks + news brief to user.
    """
    _verify_secret(x_cron_secret)
    ist = get_current_ist_context()
    logger.info("Auto-trigger: morning-brief at %s", ist["current_time_ist"])

    # Import here to avoid circular imports at module load
    from app.chains.ambient_monitoring import AmbientMonitoringChain
    # In production: publish to Redis event queue for delivery
    # For now: log and return trigger confirmation

    return TriggerResponse(
        triggered="morning-brief",
        time_ist=ist["current_datetime_full"],
        status="queued",
        message_hi=f"सुबह की brief तैयार हो रही है — {ist['current_time_ist']}",
        message_en=f"Morning brief queued at {ist['current_time_ist']}",
    )


# ── News Scan ─────────────────────────────────────────────────────────────────

@router.post("/news-scan", response_model=TriggerResponse)
async def trigger_news_scan(
    x_cron_secret: str | None = Header(default=None),
):
    """News scan — fires every 30 min during active hours."""
    _verify_secret(x_cron_secret)
    ist = get_current_ist_context()
    logger.info("Auto-trigger: news-scan at %s", ist["current_time_ist"])

    return TriggerResponse(
        triggered="news-scan",
        time_ist=ist["current_datetime_full"],
        status="queued",
        message_hi=f"News scan शुरू — {ist['current_time_ist']}",
        message_en=f"News scan triggered at {ist['current_time_ist']}",
    )


# ── Task Reminder ─────────────────────────────────────────────────────────────

@router.post("/task-reminder", response_model=TriggerResponse)
async def trigger_task_reminder(
    x_cron_secret: str | None = Header(default=None),
):
    """Task reminder — fires at 9 AM and 9 PM IST."""
    _verify_secret(x_cron_secret)
    ist = get_current_ist_context()
    logger.info("Auto-trigger: task-reminder at %s", ist["current_time_ist"])

    return TriggerResponse(
        triggered="task-reminder",
        time_ist=ist["current_datetime_full"],
        status="queued",
        message_hi=f"Tasks reminder भेजा जा रहा है — {ist['current_time_ist']}",
        message_en=f"Task reminder queued at {ist['current_time_ist']}",
    )


# ── Evening Summary ───────────────────────────────────────────────────────────

@router.post("/evening-summary", response_model=TriggerResponse)
async def trigger_evening_summary(
    x_cron_secret: str | None = Header(default=None),
):
    """Evening summary — fires at 8:00 PM IST daily."""
    _verify_secret(x_cron_secret)
    ist = get_current_ist_context()
    logger.info("Auto-trigger: evening-summary at %s", ist["current_time_ist"])

    return TriggerResponse(
        triggered="evening-summary",
        time_ist=ist["current_datetime_full"],
        status="queued",
        message_hi=f"शाम की summary तैयार हो रही है — {ist['current_time_ist']}",
        message_en=f"Evening summary queued at {ist['current_time_ist']}",
    )


# ── Financial Watch ───────────────────────────────────────────────────────────

@router.post("/financial-watch", response_model=TriggerResponse)
async def trigger_financial_watch(
    x_cron_secret: str | None = Header(default=None),
):
    """Financial monitoring — fires every 15 min on market days."""
    _verify_secret(x_cron_secret)
    ist = get_current_ist_context()
    logger.info("Auto-trigger: financial-watch at %s", ist["current_time_ist"])

    return TriggerResponse(
        triggered="financial-watch",
        time_ist=ist["current_datetime_full"],
        status="queued",
        message_hi=f"Market watch चल रहा है — {ist['current_time_ist']}",
        message_en=f"Financial watch triggered at {ist['current_time_ist']}",
    )


# ── Memory Consolidation ──────────────────────────────────────────────────────

@router.post("/memory-consolidation", response_model=TriggerResponse)
async def trigger_memory_consolidation(
    x_cron_secret: str | None = Header(default=None),
):
    """Memory consolidation — fires at midnight IST daily."""
    _verify_secret(x_cron_secret)
    ist = get_current_ist_context()
    logger.info("Auto-trigger: memory-consolidation at %s", ist["current_time_ist"])

    return TriggerResponse(
        triggered="memory-consolidation",
        time_ist=ist["current_datetime_full"],
        status="queued",
        message_hi="आज की memories consolidate हो रही हैं…",
        message_en="Daily memory consolidation started",
    )


# ── Weekly Analytics ──────────────────────────────────────────────────────────

@router.post("/weekly-analytics", response_model=TriggerResponse)
async def trigger_weekly_analytics(
    x_cron_secret: str | None = Header(default=None),
):
    """Weekly analytics — fires Sunday 8 PM IST."""
    _verify_secret(x_cron_secret)
    ist = get_current_ist_context()
    logger.info("Auto-trigger: weekly-analytics at %s", ist["current_time_ist"])

    return TriggerResponse(
        triggered="weekly-analytics",
        time_ist=ist["current_datetime_full"],
        status="queued",
        message_hi="हफ्ते की analytics तैयार हो रही है…",
        message_en="Weekly analytics report generating",
    )


# ── Personality Evolution ─────────────────────────────────────────────────────

@router.post("/personality-evolution", response_model=TriggerResponse)
async def trigger_personality_evolution(
    x_cron_secret: str | None = Header(default=None),
):
    """Personality evolution — fires Sunday 10 PM IST."""
    _verify_secret(x_cron_secret)
    ist = get_current_ist_context()
    logger.info("Auto-trigger: personality-evolution at %s", ist["current_time_ist"])

    return TriggerResponse(
        triggered="personality-evolution",
        time_ist=ist["current_datetime_full"],
        status="queued",
        message_hi="Personality evolve हो रही है इस हफ्ते के interactions से…",
        message_en="Weekly personality evolution started",
    )


# ── Timetable Info ────────────────────────────────────────────────────────────

@router.get("/timetable")
async def get_timetable(
    x_cron_secret: str | None = Header(default=None),
):
    """Return the full timetable for cron-job.org setup."""
    _verify_secret(x_cron_secret)
    return {
        "timezone": "Asia/Kolkata (IST, UTC+5:30)",
        "total_jobs": len(TIMETABLE),
        "jobs": [
            {
                "id": e.id,
                "cron_expr": e.cron_expr,
                "url": f"/internal/trigger/{e.id}",
                "description_hi": e.description_hi,
                "description_en": e.description_en,
                "enabled": e.enabled,
                "priority": e.priority,
            }
            for e in TIMETABLE
        ],
        "setup_instructions": (
            "1. Go to cron-job.org → Create cronjob\n"
            "2. URL: https://tillu-gateway.onrender.com/internal/trigger/<id>\n"
            "3. Method: POST\n"
            "4. Header: X-Cron-Secret: <your TILLU_CRON_SECRET value>\n"
            "5. Timezone: Asia/Kolkata\n"
            "6. Use the cron_expr from each job above"
        ),
    }
