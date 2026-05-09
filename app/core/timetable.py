"""
TILLU Timetable — Auto-Trigger Schedule
========================================
Defines all scheduled actions that fire WITHOUT user input.
These are the cron jobs that make TILLU proactively intelligent.

Each entry defines:
  - cron_expr   : standard cron expression (IST timezone)
  - action      : internal gateway endpoint to call
  - description : what it does
  - enabled     : can be toggled without code change

IMPORTANT: Actual cron scheduling is done externally via:
  - cron-job.org (free, set manually)
  - OR Render cron jobs (in render.yaml)
  - OR n8n Schedule Trigger nodes

This file is the SINGLE SOURCE OF TRUTH for the schedule.
Copy the cron expressions from here when setting up cron-job.org.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TimetableEntry:
    id: str
    cron_expr: str          # IST timezone
    action: str             # Gateway internal endpoint
    description_hi: str     # Hindi description
    description_en: str     # English description
    payload: dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    priority: str = "normal"  # urgent | normal | low


# ── TILLU Daily Timetable ─────────────────────────────────────────────────────
# All times are IST (UTC+5:30)

TIMETABLE: list[TimetableEntry] = [

    # ── Morning Routine ───────────────────────────────────────────────────────

    TimetableEntry(
        id="morning-brief",
        cron_expr="0 7 * * *",          # 7:00 AM IST daily
        action="/internal/trigger/morning-brief",
        description_hi="सुबह की intelligence brief — मौसम, calendar, tasks, news",
        description_en="Morning intelligence brief — weather, calendar, tasks, top news",
        payload={"workflow": "WF-02", "lang": "hi"},
        priority="urgent",
    ),

    TimetableEntry(
        id="morning-news-scan",
        cron_expr="30 7 * * *",         # 7:30 AM IST daily
        action="/internal/trigger/news-scan",
        description_hi="सुबह की news scan — India, NCR, और user interests",
        description_en="Morning news scan — India, NCR local, and user interests",
        payload={"focus": ["india", "ncr", "delhi", "technology"], "lang": "hi"},
    ),

    TimetableEntry(
        id="task-reminder-morning",
        cron_expr="0 9 * * *",          # 9:00 AM IST daily
        action="/internal/trigger/task-reminder",
        description_hi="आज के tasks और deadlines की याद दिलाना",
        description_en="Remind about today's tasks and approaching deadlines",
        payload={"period": "morning", "lang": "hi"},
    ),

    # ── Daytime Monitoring ────────────────────────────────────────────────────

    TimetableEntry(
        id="news-cycle-day",
        cron_expr="*/30 9-21 * * *",    # Every 30 min, 9 AM–9 PM IST
        action="/internal/trigger/news-cycle",
        description_hi="हर 30 मिनट में news update — breaking news filter",
        description_en="News cycle every 30 min during active hours",
        payload={"urgency_threshold": 7},
    ),

    TimetableEntry(
        id="financial-watch",
        cron_expr="*/15 9-16 * * 1-5",  # Every 15 min, Mon–Fri market hours
        action="/internal/trigger/financial-watch",
        description_hi="Market hours में financial monitoring — NSE/BSE, crypto",
        description_en="Financial monitoring during NSE/BSE market hours",
        payload={"markets": ["NSE", "BSE", "crypto"], "alert_threshold_pct": 2.0},
    ),

    TimetableEntry(
        id="web-monitor",
        cron_expr="*/30 * * * *",       # Every 30 min, always
        action="/internal/trigger/web-monitor",
        description_hi="Watched URLs में changes detect करना",
        description_en="Detect changes on monitored URLs",
        payload={},
    ),

    TimetableEntry(
        id="context-precompute",
        cron_expr="0 * * * *",          # Every hour
        action="/internal/trigger/context-precompute",
        description_hi="अगले घंटे के लिए context pre-compute करना",
        description_en="Pre-compute context for the next hour",
        payload={},
        priority="low",
    ),

    # ── Afternoon Check-in ────────────────────────────────────────────────────

    TimetableEntry(
        id="afternoon-checkin",
        cron_expr="0 14 * * *",         # 2:00 PM IST daily
        action="/internal/trigger/afternoon-checkin",
        description_hi="दोपहर का check-in — tasks progress, कुछ urgent तो नहीं?",
        description_en="Afternoon check-in — task progress, any urgent items?",
        payload={"period": "afternoon", "lang": "hi"},
    ),

    # ── Evening Wrap-up ───────────────────────────────────────────────────────

    TimetableEntry(
        id="evening-summary",
        cron_expr="0 20 * * *",         # 8:00 PM IST daily
        action="/internal/trigger/evening-summary",
        description_hi="शाम की summary — आज क्या हुआ, कल क्या है",
        description_en="Evening summary — what happened today, what's tomorrow",
        payload={"period": "evening", "lang": "hi"},
        priority="urgent",
    ),

    TimetableEntry(
        id="task-reminder-evening",
        cron_expr="0 21 * * *",         # 9:00 PM IST daily
        action="/internal/trigger/task-reminder",
        description_hi="रात को pending tasks की reminder",
        description_en="Evening reminder for pending tasks",
        payload={"period": "evening", "lang": "hi"},
    ),

    # ── Night Processing ──────────────────────────────────────────────────────

    TimetableEntry(
        id="memory-consolidation",
        cron_expr="0 0 * * *",          # 12:00 AM IST daily (midnight)
        action="/internal/trigger/memory-consolidation",
        description_hi="आज की सभी बातचीत को memory में consolidate करना",
        description_en="Consolidate today's interactions into long-term memory",
        payload={"workflow": "WF-09"},
        priority="low",
    ),

    TimetableEntry(
        id="free-tier-governance",
        cron_expr="0 23 * * *",         # 11:00 PM IST daily
        action="/internal/trigger/free-tier-governance",
        description_hi="API usage check — free tier limits की निगरानी",
        description_en="Check API usage against free tier limits",
        payload={"workflow": "WF-13"},
        priority="low",
    ),

    # ── Weekly ────────────────────────────────────────────────────────────────

    TimetableEntry(
        id="weekly-analytics",
        cron_expr="0 20 * * 0",         # Sunday 8:00 PM IST
        action="/internal/trigger/weekly-analytics",
        description_hi="हफ्ते की life analytics — patterns, goals, progress",
        description_en="Weekly life analytics — patterns, goals, progress report",
        payload={"workflow": "WF-10", "lang": "hi"},
        priority="urgent",
    ),

    TimetableEntry(
        id="personality-evolution",
        cron_expr="0 22 * * 0",         # Sunday 10:00 PM IST
        action="/internal/trigger/personality-evolution",
        description_hi="हफ्ते के interactions से personality evolve करना",
        description_en="Evolve personality parameters from weekly interactions",
        payload={"workflow": "WF-16"},
        priority="low",
    ),

    TimetableEntry(
        id="relationship-intelligence",
        cron_expr="0 9 * * 1",          # Monday 9:00 AM IST
        action="/internal/trigger/relationship-intelligence",
        description_hi="Contacts check — birthdays, follow-ups, check-ins",
        description_en="Relationship intelligence — birthdays, follow-ups due",
        payload={"workflow": "WF-15", "lang": "hi"},
    ),

    # ── System Health ─────────────────────────────────────────────────────────

    TimetableEntry(
        id="health-guardian",
        cron_expr="*/5 * * * *",        # Every 5 min
        action="/api/v1/health",
        description_hi="System health check — सभी services ठीक हैं?",
        description_en="System health guardian — keepalive + status check",
        payload={},
        priority="urgent",
    ),

]

# ── Lookup helpers ────────────────────────────────────────────────────────────

_INDEX: dict[str, TimetableEntry] = {e.id: e for e in TIMETABLE}


def get_entry(entry_id: str) -> TimetableEntry | None:
    return _INDEX.get(entry_id)


def get_enabled() -> list[TimetableEntry]:
    return [e for e in TIMETABLE if e.enabled]


def get_cron_table() -> str:
    """
    Print a human-readable cron table for manual setup on cron-job.org.
    Copy-paste this output when configuring external cron jobs.
    """
    lines = [
        "=" * 70,
        "TILLU Timetable — cron-job.org Setup (IST timezone)",
        "=" * 70,
        f"{'ID':<30} {'CRON':<20} {'DESCRIPTION'}",
        "-" * 70,
    ]
    for e in get_enabled():
        lines.append(f"{e.id:<30} {e.cron_expr:<20} {e.description_en}")
    lines.append("=" * 70)
    lines.append("Timezone: Asia/Kolkata (IST, UTC+5:30)")
    lines.append(f"Total active jobs: {len(get_enabled())}")
    return "\n".join(lines)


if __name__ == "__main__":
    print(get_cron_table())
