"""
TILLU Workflow Manager
=======================
Enables TILLU to upgrade its own n8n workflows autonomously.

How it works:
  1. TILLU detects a workflow needs updating (via LLM analysis or explicit request)
  2. It generates/modifies the workflow JSON using an LLM
  3. It pushes the updated workflow to n8n via REST API
  4. It activates the workflow and verifies it's running
  5. It logs the change to Supabase for audit trail

Self-upgrade triggers:
  - User says "update morning brief to include crypto prices"
  - Weekly self-audit detects a workflow is failing
  - New data source becomes available
  - Performance analysis shows a workflow is slow

Security:
  - All workflow changes are logged with timestamp + reason
  - Changes can be rolled back via /internal/workflow/rollback
  - LLM-generated workflows are validated before deployment
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from app.utils.logging import get_logger

logger = get_logger("workflow_manager")

IST = ZoneInfo("Asia/Kolkata")

N8N_URL      = os.environ.get("N8N_URL", "https://tillu-ai-tillu-engine.hf.space")
N8N_EMAIL    = os.environ.get("N8N_EMAIL", "tillu@tillu.ai")
N8N_PASSWORD = os.environ.get("N8N_PASSWORD", "")


class WorkflowManager:
    """
    Manages TILLU's n8n workflows — list, update, activate, rollback.
    Used by the self-upgrade system and the workflow-upgrade trigger.
    """

    def __init__(self):
        self._session: httpx.AsyncClient | None = None
        self._logged_in = False

    async def _get_session(self) -> httpx.AsyncClient:
        if self._session is None or self._session.is_closed:
            self._session = httpx.AsyncClient(
                base_url=N8N_URL,
                timeout=30.0,
                follow_redirects=True,
            )
        if not self._logged_in:
            await self._login()
        return self._session

    async def _login(self) -> None:
        if not N8N_PASSWORD:
            raise ValueError("N8N_PASSWORD not set in environment")
        r = await self._session.post(
            "/rest/login",
            json={"emailOrLdapLoginId": N8N_EMAIL, "password": N8N_PASSWORD},
        )
        if r.status_code != 200:
            raise RuntimeError(f"n8n login failed: {r.status_code} {r.text[:100]}")
        self._logged_in = True
        logger.info("n8n login successful")

    async def list_workflows(self) -> list[dict[str, Any]]:
        """List all workflows in n8n."""
        s = await self._get_session()
        r = await s.get("/rest/workflows")
        r.raise_for_status()
        return r.json().get("data", [])

    async def get_workflow(self, workflow_id: str) -> dict[str, Any]:
        """Get a specific workflow by ID."""
        s = await self._get_session()
        r = await s.get(f"/rest/workflows/{workflow_id}")
        r.raise_for_status()
        return r.json().get("data", {})

    async def create_workflow(self, workflow_data: dict) -> dict[str, Any]:
        """Create a new workflow."""
        s = await self._get_session()
        r = await s.post("/rest/workflows", json=workflow_data)
        r.raise_for_status()
        result = r.json().get("data", {})
        logger.info("Created workflow: %s (id=%s)", workflow_data.get("name"), result.get("id"))
        return result

    async def update_workflow(self, workflow_id: str, workflow_data: dict) -> dict[str, Any]:
        """Update an existing workflow."""
        s = await self._get_session()
        r = await s.put(f"/rest/workflows/{workflow_id}", json=workflow_data)
        r.raise_for_status()
        result = r.json().get("data", {})
        logger.info("Updated workflow: %s (id=%s)", workflow_data.get("name"), workflow_id)
        return result

    async def activate_workflow(self, workflow_id: str) -> bool:
        """Activate a workflow."""
        s = await self._get_session()
        r = await s.patch(f"/rest/workflows/{workflow_id}", json={"active": True})
        return r.status_code == 200

    async def deactivate_workflow(self, workflow_id: str) -> bool:
        """Deactivate a workflow."""
        s = await self._get_session()
        r = await s.patch(f"/rest/workflows/{workflow_id}", json={"active": False})
        return r.status_code == 200

    async def upsert_workflow(self, workflow_data: dict) -> dict[str, Any]:
        """
        Create or update a workflow by name.
        If a workflow with the same name exists, update it.
        Otherwise create new.
        """
        name = workflow_data.get("name", "")
        existing = await self.list_workflows()

        # Find by name (exact match)
        match = next((w for w in existing if w.get("name") == name), None)

        if match:
            wf_id = match["id"]
            # Preserve the ID in the update
            workflow_data["id"] = wf_id
            result = await self.update_workflow(wf_id, workflow_data)
            return {**result, "_action": "updated", "_id": wf_id}
        else:
            result = await self.create_workflow(workflow_data)
            return {**result, "_action": "created", "_id": result.get("id")}

    async def sync_all_from_repo(self, workflows_dir: str) -> list[dict]:
        """
        Sync all workflow JSON files from the repo to n8n.
        This is the self-upgrade mechanism — called when workflows change.
        """
        import os
        results = []

        if not os.path.isdir(workflows_dir):
            raise ValueError(f"Workflows directory not found: {workflows_dir}")

        files = sorted(f for f in os.listdir(workflows_dir) if f.endswith(".json"))
        logger.info("Syncing %d workflows from %s", len(files), workflows_dir)

        for fname in files:
            fpath = os.path.join(workflows_dir, fname)
            with open(fpath, "r", encoding="utf-8") as f:
                wf_data = json.load(f)

            try:
                result = await self.upsert_workflow(wf_data)
                results.append({
                    "file": fname,
                    "name": wf_data.get("name"),
                    "action": result.get("_action"),
                    "id": result.get("_id"),
                    "status": "ok",
                })
                logger.info("Synced: %s (%s)", wf_data.get("name"), result.get("_action"))
            except Exception as e:
                results.append({
                    "file": fname,
                    "name": wf_data.get("name"),
                    "status": "error",
                    "error": str(e),
                })
                logger.error("Failed to sync %s: %s", fname, e)

        return results

    async def generate_and_deploy(
        self,
        instruction: str,
        base_workflow_name: str | None = None,
    ) -> dict[str, Any]:
        """
        Use LLM to generate/modify a workflow based on natural language instruction,
        then deploy it to n8n.

        Args:
            instruction: Natural language description of what the workflow should do
            base_workflow_name: If provided, modify this existing workflow

        Returns:
            {"workflow_id", "name", "action", "instruction"}
        """
        from app.providers.hf_inference import chat as hf_chat

        # Get base workflow if modifying
        base_json = ""
        if base_workflow_name:
            existing = await self.list_workflows()
            match = next((w for w in existing if w.get("name") == base_workflow_name), None)
            if match:
                base_wf = await self.get_workflow(match["id"])
                base_json = f"\n\nExisting workflow to modify:\n```json\n{json.dumps(base_wf, indent=2)[:3000]}\n```"

        prompt = f"""You are a TILLU n8n workflow engineer.
Generate a valid n8n workflow JSON for the following requirement:

{instruction}
{base_json}

Rules:
- Return ONLY valid JSON, no explanation
- Use n8n node types: n8n-nodes-base.httpRequest, n8n-nodes-base.scheduleTrigger, n8n-nodes-base.function, etc.
- TILLU_GATEWAY_URL env var points to the FastAPI gateway
- All times in IST (Asia/Kolkata)
- Include proper connections between nodes
- Name the workflow descriptively

Return the complete workflow JSON:"""

        result = await hf_chat(
            messages=[{"role": "user", "content": prompt}],
            model="deepseek-ai/DeepSeek-V3-0324",  # best for structured output
            max_tokens=4000,
            temperature=0.2,  # low temp for structured JSON
        )

        # Extract JSON from response
        content = result["content"]
        start = content.find("{")
        end = content.rfind("}") + 1
        if start < 0 or end <= start:
            raise ValueError("LLM did not return valid JSON workflow")

        workflow_json = json.loads(content[start:end])

        # Validate minimum structure
        if "nodes" not in workflow_json or "name" not in workflow_json:
            raise ValueError("Generated workflow missing required fields (nodes, name)")

        # Ensure connections field exists
        if "connections" not in workflow_json:
            workflow_json["connections"] = {}

        # Deploy
        deploy_result = await self.upsert_workflow(workflow_json)

        logger.info(
            "LLM-generated workflow deployed: %s (%s)",
            workflow_json["name"],
            deploy_result.get("_action"),
        )

        return {
            "workflow_id": deploy_result.get("_id"),
            "name": workflow_json["name"],
            "action": deploy_result.get("_action"),
            "instruction": instruction,
            "model_used": result["model"],
        }

    async def close(self):
        if self._session and not self._session.is_closed:
            await self._session.aclose()


# Singleton
workflow_manager = WorkflowManager()
