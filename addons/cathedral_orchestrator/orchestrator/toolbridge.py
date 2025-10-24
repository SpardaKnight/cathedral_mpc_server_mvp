import os, json, httpx
from typing import Dict, Any, List

# Tools delegation to HA: allow-list domains; call Core REST API /api/services/{domain}/{service}
# REST API docs: https://developers.home-assistant.io/docs/api/rest/ 

SUPERVISOR_BASE = os.environ.get("SUPERVISOR_BASE", "http://supervisor")
SUPERVISOR_TOKEN = os.environ.get("SUPERVISOR_TOKEN", "")

class ToolBridge:
    def __init__(self, allowed_domains: List[str]):
        self.allowed_domains = set(allowed_domains or [])

    async def call(self, tool_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        # tool_name like 'light.turn_on'; enforce allow-list
        try:
            domain, service = tool_name.split(".", 1)
        except ValueError:
            return {"ok": False, "error": "invalid_tool_name"}
        if domain not in self.allowed_domains:
            return {"ok": False, "error": f"domain_not_allowed:{domain}"}
        # Basic argument validation
        data = payload or {}
        headers = {"Authorization": f"Bearer {SUPERVISOR_TOKEN}", "Content-Type": "application/json"}
        url = f"{SUPERVISOR_BASE}/core/api/services/{domain}/{service}"
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(url, headers=headers, json=data)
            if r.status_code in (200, 201):
                return {"ok": True, "result": r.json() if r.text else {}}
            return {"ok": False, "status": r.status_code, "error": r.text}
