import logging
import os
from typing import Any, Dict, List

import httpx

from .logging_config import jlog

# Tools delegation to HA: allow-list domains; call Core REST API /api/services/{domain}/{service}
# REST API docs: https://developers.home-assistant.io/docs/api/rest/

SUPERVISOR_BASE = os.environ.get("SUPERVISOR_BASE", "http://supervisor")
SUPERVISOR_TOKEN = os.environ.get("SUPERVISOR_TOKEN", "")

logger = logging.getLogger("cathedral")


class ToolBridge:
    def __init__(self, allowed_domains: List[str]):
        self.allowed_domains = set(allowed_domains or [])
        jlog(
            logger,
            event="toolbridge_init",
            domains=sorted(self.allowed_domains),
        )

    async def call(self, tool_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        try:
            domain, service = tool_name.split(".", 1)
        except ValueError:
            jlog(logger, level="ERROR", event="toolbridge_invalid_tool", tool=tool_name)
            return {"ok": False, "error": "invalid_tool_name"}
        if domain not in self.allowed_domains:
            jlog(
                logger,
                level="WARN",
                event="toolbridge_domain_blocked",
                domain=domain,
                service=service,
            )
            return {"ok": False, "error": f"domain_not_allowed:{domain}"}

        data = payload or {}
        headers = {
            "Authorization": f"Bearer {SUPERVISOR_TOKEN}",
            "Content-Type": "application/json",
        }
        url = f"{SUPERVISOR_BASE}/core/api/services/{domain}/{service}"
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(url, headers=headers, json=data)
        except httpx.HTTPError as exc:
            jlog(
                logger,
                level="ERROR",
                event="toolbridge_http_error",
                url=url,
                error=str(exc),
            )
            return {"ok": False, "error": f"http_error:{exc}"}

        try:
            body = response.json() if response.text else {}
        except ValueError:
            body = response.text

        status = response.status_code
        if status in (200, 201, 202):
            jlog(
                logger,
                event="toolbridge_call_success",
                domain=domain,
                service=service,
                status=status,
            )
            return {"ok": True, "result": body}
        if status == 401:
            jlog(
                logger,
                level="WARN",
                event="toolbridge_unauthorized",
                domain=domain,
                service=service,
            )
            return {"ok": False, "status": status, "error": "unauthorized"}

        jlog(
            logger,
            level="ERROR",
            event="toolbridge_call_failed",
            domain=domain,
            service=service,
            status=status,
        )
        return {"ok": False, "status": status, "error": body}
