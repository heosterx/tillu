"""
TILLU Daemon — HuggingFace Spaces Runner
==========================================
HF Spaces requires HTTP on port 7860.
Runs daemon loops + FastAPI health server concurrently.

Key design: daemon loops are started AFTER the HTTP server is up,
so HF health checks pass even during slow startup.
"""

from __future__ import annotations

import asyncio
import os
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import uvicorn
from fastapi import FastAPI
from fastapi.responses import ORJSONResponse

IST = ZoneInfo("Asia/Kolkata")
START_TIME = time.time()

# ── Shared state ──────────────────────────────────────────────────────────────
_daemon = None
_daemon_started = False
_daemon_error: str | None = None
_loop_stats: dict = {}

# ── FastAPI health app ────────────────────────────────────────────────────────
app = FastAPI(
    title="TILLU Daemon",
    description="Background intelligence — 16 async loops",
    version="1.0.0",
    default_response_class=ORJSONResponse,
)


@app.get("/health")
async def health():
    return {
        "status": "ok" if _daemon_started else "starting",
        "service": "tillu-daemon",
        "uptime_seconds": round(time.time() - START_TIME, 1),
    }


@app.get("/status")
async def status():
    now = datetime.now(IST)
    active = 0
    if _daemon and hasattr(_daemon, "tasks"):
        active = len([t for t in _daemon.tasks if not t.done()])
    return {
        "service": "tillu-daemon",
        "status": "running" if _daemon_started and not _daemon_error else (
            "error" if _daemon_error else "starting"
        ),
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "time_ist": now.strftime("%d %b %Y, %I:%M %p IST"),
        "active_loops": active,
        "total_loops": len(_daemon.loops) if _daemon else 0,
        "error": _daemon_error,
    }


@app.get("/")
async def root():
    return await status()


# ── Daemon runner ─────────────────────────────────────────────────────────────

async def run_daemon():
    """Start daemon loops after a short delay (lets HTTP server come up first)."""
    global _daemon, _daemon_started, _daemon_error

    # Wait for HTTP server to be ready
    await asyncio.sleep(3)

    try:
        # Configure logging
        from app.utils.logging import configure_logging
        configure_logging()

        from app.utils.logging import get_logger
        logger = get_logger("daemon.hf_runner")
        logger.info("Starting TILLU Daemon loops...")

        # Import DaemonProcess here — not at module level
        from daemon.core import DaemonProcess
        _daemon = DaemonProcess()
        _daemon_started = True
        logger.info("Daemon started with %d loops", len(_daemon.loops))
        await _daemon.start()

    except Exception as e:
        _daemon_error = str(e)
        # Don't crash the HTTP server — log and keep health endpoint alive
        import traceback
        print("Daemon error:", e)
        traceback.print_exc()


async def run_server():
    """Run FastAPI health server on port 7860."""
    config = uvicorn.Config(
        app=app,
        host="0.0.0.0",
        port=7860,
        log_level="warning",
        access_log=False,
    )
    server = uvicorn.Server(config)
    await server.serve()


async def main():
    print("TILLU Daemon HF Runner starting...")
    print("HTTP health server: port 7860")
    print("Daemon loops: starting in 3s...")

    await asyncio.gather(
        run_server(),
        run_daemon(),
        return_exceptions=True,
    )


if __name__ == "__main__":
    asyncio.run(main())
