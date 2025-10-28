from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Dict, Optional, Sequence

import httpx

from ..logging_config import jlog

logger = logging.getLogger("cathedral")


@dataclass
class ChromaConfig:
    url: str = ""
    collection_name: str = "cathedral"


class ChromaClient:
    """
    Async HTTP client for Chroma that supports API v2 and v1.

    - Prefer v2 when available. Fall back to v1 on 404, 405, 410, or 422.
    - Ensure a collection exists before first embed and cache name -> id.
    - Upserts use /api/v2/collections/{id}/add when possible.
    """

    def __init__(self, http_client: httpx.AsyncClient, config: ChromaConfig):
        self._client = http_client
        self._config = config
        self._collection_cache: Dict[str, str] = {}
        self._lock = asyncio.Lock()
        self._prefer_v2: bool = True

    # ---- helpers -------------------------------------------------------------

    @property
    def base_url(self) -> str:
        return (self._config.url or "").rstrip("/")

    def _v2_base(self, base: str) -> str:
        return f"{base}/api/v2"

    def _v1_base(self, base: str) -> str:
        return f"{base}/api/v1"

    def _v2(self, path: str) -> str:
        return f"{self.base_url}/api/v2{path}"

    def _v1(self, path: str) -> str:
        return f"{self.base_url}/api/v1{path}"

    @staticmethod
    def _should_fallback(status: int) -> bool:
        # Common responses on mismatched API versions
        return status in (404, 405, 410, 422)

    # ---- health --------------------------------------------------------------

    async def health(self) -> bool:
        base = self.base_url
        if not base:
            jlog(logger, level="ERROR", event="chroma_missing_base")
            return False
        # v2 heartbeat
        try:
            url = self._v2("/heartbeat")
            resp = await self._client.get(url, timeout=5.0, follow_redirects=True)
            if 200 <= resp.status_code < 400:
                self._prefer_v2 = True
                jlog(logger, event="chroma_health", url=base, probe=url, ok=True, status=resp.status_code)
                return True
        except Exception as exc:
            jlog(logger, level="WARN", event="chroma_health_probe_v2_error", url=base, error=str(exc))
        # v1 heartbeat
        try:
            url = self._v1("/heartbeat")
            resp = await self._client.get(url, timeout=5.0, follow_redirects=True)
            if 200 <= resp.status_code < 400:
                self._prefer_v2 = False
                jlog(logger, event="chroma_health", url=base, probe=url, ok=True, status=resp.status_code)
                return True
        except Exception as exc:
            jlog(logger, level="WARN", event="chroma_health_probe_v1_error", url=base, error=str(exc))
        jlog(logger, level="ERROR", event="chroma_health", url=base, probe="auto", ok=False)
        return False

    # ---- collections ---------------------------------------------------------

    async def ensure_collection(self, name: Optional[str] = None) -> Optional[str]:
        """
        Ensure a collection exists and return its id.

        v2: GET /collections/by_name?name=X, POST /collections {name, metadata}
        v1: GET /collections/<name>, POST /collections {name}
        """
        target = (name or self._config.collection_name or "").strip()
        if not target:
            jlog(logger, level="ERROR", event="chroma_collection_invalid_name")
            return None
        base = self.base_url
        if not base:
            jlog(logger, level="ERROR", event="chroma_collection_missing_base")
            return None

        async with self._lock:
            cached = self._collection_cache.get(target)
            if cached:
                return cached
            if await self._ensure_collection_v2(target):
                return self._collection_cache.get(target)
            if await self._ensure_collection_v1(target):
                return self._collection_cache.get(target)
            return None

    async def _ensure_collection_v2(self, target: str) -> bool:
        if not self.base_url:
            return False
        # GET by name
        try:
            url = self._v2("/collections/by_name")
            resp = await self._client.get(url, params={"name": target}, timeout=20, follow_redirects=True)
            if resp.status_code == 200:
                data = resp.json() or {}
                cid = data.get("id") or (data.get("collection") or {}).get("id")
                if cid:
                    self._collection_cache[target] = str(cid)
                    self._prefer_v2 = True
                    jlog(logger, event="chroma_collection_found_v2", name=target, collection_id=str(cid))
                    return True
        except Exception as exc:
            jlog(logger, level="WARN", event="chroma_collection_lookup_failed_v2", name=target, error=str(exc))
        # POST to create
        try:
            url = self._v2("/collections")
            payload = {"name": target, "metadata": {}}
            resp = await self._client.post(url, json=payload, timeout=30, follow_redirects=True)
            if resp.status_code in (200, 201):
                data = resp.json() or {}
                cid = data.get("id") or (data.get("collection") or {}).get("id")
                if cid:
                    self._collection_cache[target] = str(cid)
                    self._prefer_v2 = True
                    jlog(logger, event="chroma_collection_created_v2", name=target, collection_id=str(cid))
                    return True
            elif self._should_fallback(resp.status_code):
                jlog(logger, level="WARN", event="chroma_collection_create_v2_unavailable", name=target, status=resp.status_code)
        except Exception as exc:
            jlog(logger, level="WARN", event="chroma_collection_create_failed_v2", name=target, error=str(exc))
        return False

    async def _ensure_collection_v1(self, target: str) -> bool:
        if not self.base_url:
            return False
        # GET by name
        try:
            url = self._v1(f"/collections/{target}")
            resp = await self._client.get(url, timeout=20, follow_redirects=True)
            if resp.status_code == 200:
                data = resp.json() or {}
                cid = data.get("id") or (data.get("collection") or {}).get("id")
                if cid:
                    self._collection_cache[target] = str(cid)
                    self._prefer_v2 = False
                    jlog(logger, event="chroma_collection_found_v1", name=target, collection_id=str(cid))
                    return True
        except Exception as exc:
            jlog(logger, level="WARN", event="chroma_collection_lookup_failed_v1", name=target, error=str(exc))
        # POST to create
        try:
            url = self._v1("/collections")
            resp = await self._client.post(url, json={"name": target}, timeout=30, follow_redirects=True)
            if resp.status_code in (200, 201):
                data = resp.json() or {}
                cid = data.get("id") or (data.get("collection") or {}).get("id")
                if cid:
                    self._collection_cache[target] = str(cid)
                    self._prefer_v2 = False
                    jlog(logger, event="chroma_collection_created_v1", name=target, collection_id=str(cid))
                    return True
        except Exception as exc:
            jlog(logger, level="WARN", event="chroma_collection_create_failed_v1", name=target, error=str(exc))
        return False

    # ---- upserts -------------------------------------------------------------

    async def upsert(
        self,
        collection_id: str,
        *,
        ids: Sequence[str],
        documents: Sequence[str],
        metadatas: Sequence[dict],
        embeddings: Optional[Sequence[Sequence[float]]] = None,
    ) -> bool:
        base = self.base_url
        if not base:
            jlog(logger, level="ERROR", event="chroma_upsert_missing_base")
            return False
        if not collection_id:
            jlog(logger, level="ERROR", event="chroma_upsert_missing_collection")
            return False

        # Prefer API v2 then fall back to v1. Some servers have v1 disabled with 405/410.
        candidates = [
            f"{self._v2_base(base)}/collections/{collection_id}/add",
            f"{self._v1_base(base)}/collections/{collection_id}/add",
            f"{self._v1_base(base)}/collections/{collection_id}/upsert",
        ]
        payload: Dict[str, object] = {
            "ids": list(ids),
            "documents": list(documents),
            "metadatas": list(metadatas),
        }
        if embeddings is not None:
            payload["embeddings"] = [list(vec) for vec in embeddings]

        attempt = 0
        item_count = len(ids)
        while attempt < 3:
            attempt += 1
            for url in candidates:
                try:
                    resp = await self._client.post(url, json=payload, follow_redirects=True, timeout=30)
                    status = resp.status_code
                    if 200 <= status < 300:
                        jlog(
                            logger,
                            event="chroma_upsert_ok",
                            collection_id=collection_id,
                            count=item_count,
                            url=url,
                            status=status,
                        )
                        return True
                    if status in (404, 405, 410, 501, 503):
                        jlog(
                            logger,
                            level="WARN",
                            event="chroma_upsert_wrong_api",
                            url=url,
                            status=status,
                            attempt=attempt,
                        )
                        continue
                    body = ""
                    try:
                        body = resp.text
                    except Exception:
                        pass
                    jlog(
                        logger,
                        level="ERROR",
                        event="chroma_upsert_bad_status",
                        status=status,
                        body=body[:500],
                        url=url,
                    )
                    break
                except httpx.HTTPStatusError as exc:
                    jlog(
                        logger,
                        level="ERROR",
                        event="chroma_upsert_http_error",
                        status=exc.response.status_code,
                        url=str(exc.request.url),
                        body=exc.response.text,
                    )
                    break
                except Exception as exc:  # network guard
                    jlog(
                        logger,
                        level="WARN",
                        event="chroma_upsert_retry",
                        attempt=attempt,
                        collection_id=collection_id,
                        error=str(exc),
                    )
            await asyncio.sleep(min(2 ** attempt, 5))
        jlog(logger, level="ERROR", event="chroma_upsert_exhausted", collection_id=collection_id)
        return False
