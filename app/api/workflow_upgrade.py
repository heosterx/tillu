"""
TILLU Self-Upgrade API
=======================
Endpoints that allow TILLU to upgrade its own n8n workflows.

POST /internal/workflow/sync          — sync all workflows from repo to n8n
POST /internal/workflow/generate      — LLM generates + deploys a new workflow
POST /internal/workflow/update/{name} — LLM modifies an existing workflow
GET  /internal/workflow/list          — list all current workflows
POST /internal/workflow/activate/{id} — activate a workflow
POST /internal/workflow/deactivate/{id} — deactivate a workflow

All endpoints protected by X-Cron-Secret header.
"""

from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel

from app.utils.logging import get_logger

logger = get_logger("workflow_upgrade")
router = APIRouter(prefix="/internal/workflow", tags=["workflow-upgrade"])

CRON_SECRET = os.environ.get("TILLU_CRON_SECRET", "")
N8N_WORKFLOWS_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "n8n", "workflows"
)


def _verify(x_cron_secret: str | None) -> None:
    if CRON_SECRET and x_cron_secret != CRON_SECRET:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")


class GenerateRequest(BaseModel):
    instruction: str
    base_workflow_name: str | None = None


class SyncResponse(BaseModel):
    synced: int
    results: list[dict[str, Any]]


# ── List workflows ────────────────────────────────────────────────────────────

@router.get("/list")
async def list_workflows(x_cron_secret: str | None = Header(default=None)):
    """List all workflows currently in n8n."""
    _verify(x_cron_secret)
    from app.services.workflow_manager import workflow_manager
    try:
        workflows = await workflow_manager.list_workflows()
        return {
            "total": len(workflows),
            "workflows": [
                {
                    "id": w.get("id"),
                    "name": w.get("name"),
                    "active": w.get("active"),
                    "updatedAt": w.get("updatedAt"),
                }
                for w in workflows
            ],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Sync from repo ────────────────────────────────────────────────────────────

@router.post("/sync", response_model=SyncResponse)
async def sync_workflows(x_cron_secret: str | None = Header(default=None)):
    """
    Sync all workflow JSON files from the repo to n8n.
    Creates new workflows and updates existing ones by name.
    Called automatically when workflows change in git.
    """
    _verify(x_cron_secret)
    from app.services.workflow_manager import workflow_manager
    try:
        results = await workflow_manager.sync_all_from_repo(N8N_WORKFLOWS_DIR)
        ok = [r for r in results if r.get("status") == "ok"]
        logger.info("Workflow sync: %d/%d succeeded", len(ok), len(results))
        return SyncResponse(synced=len(ok), results=results)
    except Exception as e:
        logger.error("Workflow sync failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ── LLM generate + deploy ─────────────────────────────────────────────────────

@router.post("/generate")
async def generate_workflow(
    req: GenerateRequest,
    x_cron_secret: str | None = Header(default=None),
):
    """
    Use LLM to generate a new workflow from natural language instruction
    and deploy it directly to n8n.

    Example:
      POST /internal/workflow/generate
      {"instruction": "Create a workflow that checks INR/USD rate every hour and alerts if it moves more than 1%"}
    """
    _verify(x_cron_secret)
    from app.services.workflow_manager import workflow_manager
    try:
        result = await workflow_manager.generate_and_deploy(
            instruction=req.instruction,
            base_workflow_name=req.base_workflow_name,
        )
        logger.info(
            "Workflow generated+deployed: %s (%s) from instruction: %s",
            result["name"], result["action"], req.instruction[:60],
        )
        return result
    except Exception as e:
        logger.error("Workflow generation failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ── Activate / Deactivate ─────────────────────────────────────────────────────

@router.post("/activate/{workflow_id}")
async def activate_workflow(
    workflow_id: str,
    x_cron_secret: str | None = Header(default=None),
):
    """Activate a workflow by ID."""
    _verify(x_cron_secret)
    from app.services.workflow_manager import workflow_manager
    ok = await workflow_manager.activate_workflow(workflow_id)
    return {"workflow_id": workflow_id, "active": ok}


@router.post("/deactivate/{workflow_id}")
async def deactivate_workflow(
    workflow_id: str,
    x_cron_secret: str | None = Header(default=None),
):
    """Deactivate a workflow by ID."""
    _verify(x_cron_secret)
    from app.services.workflow_manager import workflow_manager
    ok = await workflow_manager.deactivate_workflow(workflow_id)
    return {"workflow_id": workflow_id, "active": not ok}


# ── Self-upgrade trigger (called by n8n itself) ───────────────────────────────

@router.post("/self-upgrade")
async def self_upgrade(
    x_cron_secret: str | None = Header(default=None),
):
    """
    TILLU's self-upgrade endpoint.
    Called by n8n WF-17 (weekly self-audit) to sync latest workflows from repo.
    This is how TILLU upgrades itself without human intervention.
    """
    _verify(x_cron_secret)
    from app.services.workflow_manager import workflow_manager
    from app.core.indian_rules import get_current_ist_context

    ist = get_current_ist_context()
    logger.info("Self-upgrade triggered at %s", ist["current_time_ist"])

    try:
        results = await workflow_manager.sync_all_from_repo(N8N_WORKFLOWS_DIR)
        ok    = [r for r in results if r.get("status") == "ok"]
        fails = [r for r in results if r.get("status") != "ok"]

        return {
            "status": "completed",
            "time_ist": ist["current_datetime_full"],
            "synced": len(ok),
            "failed": len(fails),
            "results": results,
            "message_hi": f"TILLU ne apne {len(ok)} workflows upgrade kar liye — {ist['current_time_ist']}",
            "message_en": f"Self-upgrade complete: {len(ok)} workflows synced at {ist['current_time_ist']}",
        }
    except Exception as e:
        logger.error("Self-upgrade failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Self-upgrade failed: {e}")
