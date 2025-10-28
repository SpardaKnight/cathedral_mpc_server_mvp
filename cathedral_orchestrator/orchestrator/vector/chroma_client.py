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
    def __init__(self, http_client: httpx.AsyncClient, config: ChromaConfig):
        self._client = http_client
        self._config = config
        self._collection_cache: Dict[str, str] = {}
        self._lock = asyncio.Lock()

    def update_config(self, config: ChromaConfig) -> None:
        normalized = (config.url or "").rstrip("/")
        previous = (self._config.url or "").rstrip("/")
        self._config = config
        if normalized != previous:
            self._collection_cache.clear()
            jlog(
                logger,
                event="chroma_config_updated",
                url=normalized,
                previous=previous,
            )

    @property
    def base_url(self) -> str:
        return (self._config.url or "").rstrip("/")

    async def health_ok(self) -> bool:
        base = self.base_url
        if not base:
            jlog(logger, level="WARN", event="chroma_health_missing_url")
            return False

        base = base.rstrip("/")
        urls = [
            f"{base}/api/v2/heartbeat",
            f"{base}/api/v1/heartbeat",
            f"{base}/docs",
        ]

        for url in urls:
            try:
                resp = await self._client.get(
                    url, follow_redirects=True, timeout=5.0
                )
                status = resp.status_code
                if 200 <= status < 400:
                    jlog(
                        logger,
                        event="chroma_health",
                        url=base,
                        probe=url,
                        ok=True,
                        status=status,
                    )
                    return True
                jlog(
                    logger,
                    level="WARN",
                    event="chroma_health_probe_failed",
                    url=url,
                    status=status,
                )
            except Exception as exc:  # pragma: no cover - network guard
                jlog(
                    logger,
                    level="WARN",
                    event="chroma_health_probe_error",
                    url=url,
                    error=str(exc),
                )

        jlog(logger, level="WARN", event="chroma_health", url=base, ok=False)
        return False

    def _v2_base(self, base: str) -> str:
        return f"{base}/api/v2"

    def _v1_base(self, base: str) -> str:
        return f"{base}/api/v1"

    async def ensure_collection(self, name: Optional[str] = None) -> Optional[str]:
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
            collection_id = await self._ensure_collection_v2(base, target)
            if collection_id:
                self._collection_cache[target] = collection_id
                return collection_id
            collection_id = await self._ensure_collection_v1(base, target)
            if collection_id:
                self._collection_cache[target] = collection_id
                return collection_id
            return None

    async def _ensure_collection_v2(self, base: str, target: str) -> Optional[str]:
        # GET /api/v2/collections/by_name?name=<target>
        try:
            url = f"{self._v2_base(base)}/collections/by_name"
            resp = await self._client.get(
                url,
                params={"name": target},
                follow_redirects=True,
                timeout=20,
            )
            if resp.status_code == 200:
                data = resp.json() or {}
                collection = data.get("collection") or {}
                cid = data.get("id") or collection.get("id")
                if cid:
                    jlog(
                        logger,
                        event="chroma_collection_found_v2",
                        name=target,
                        collection_id=cid,
                    )
                    return str(cid)
        except Exception as exc:
            jlog(
                logger,
                level="WARN",
                event="chroma_collection_lookup_failed_v2",
                name=target,
                error=str(exc),
            )
        # POST /api/v2/collections
        try:
            url = f"{self._v2_base(base)}/collections"
            payload = {"name": target, "metadata": {}}
            resp = await self._client.post(
                url,
                json=payload,
                follow_redirects=True,
                timeout=30,
            )
            if resp.status_code in (200, 201):
                data = resp.json() or {}
                collection = data.get("collection") or {}
                cid = data.get("id") or collection.get("id")
                if cid:
                    jlog(
                        logger,
                        event="chroma_collection_created_v2",
                        name=target,
                        collection_id=cid,
                    )
                    return str(cid)
            if resp.status_code in (400, 409, 422):
                lookup_url = f"{self._v2_base(base)}/collections/by_name"
                retry = await self._client.get(
                    lookup_url,
                    params={"name": target},
                    follow_redirects=True,
                    timeout=20,
                )
                if retry.status_code == 200:
                    data = retry.json() or {}
                    collection = data.get("collection") or {}
                    cid = data.get("id") or collection.get("id")
                    if cid:
                        jlog(
                            logger,
                            event="chroma_collection_exists_v2",
                            name=target,
                            collection_id=cid,
                        )
                        return str(cid)
        except Exception as exc:
            jlog(
                logger,
                level="WARN",
                event="chroma_collection_create_failed_v2",
                name=target,
                error=str(exc),
            )
        return None

    async def _ensure_collection_v1(self, base: str, target: str) -> Optional[str]:
        try:
            url = f"{self._v1_base(base)}/collections/{target}"
            resp = await self._client.get(
                url,
                follow_redirects=True,
                timeout=20,
            )
            if resp.status_code == 200:
                data = resp.json() or {}
                collection = data.get("collection") or {}
                cid = data.get("id") or collection.get("id")
                if cid:
                    jlog(
                        logger,
                        event="chroma_collection_found_v1",
                        name=target,
                        collection_id=cid,
                    )
                    return str(cid)
        except Exception as exc:
            jlog(
                logger,
                level="WARN",
                event="chroma_collection_lookup_failed_v1",
                name=target,
                error=str(exc),
            )
        try:
            url = f"{self._v1_base(base)}/collections"
            resp = await self._client.post(
                url,
                json={"name": target},
                follow_redirects=True,
                timeout=30,
            )
            if resp.status_code in (200, 201):
                data = resp.json() or {}
                collection = data.get("collection") or {}
                cid = data.get("id") or collection.get("id")
                if cid:
                    jlog(
                        logger,
                        event="chroma_collection_created_v1",
                        name=target,
                        collection_id=cid,
                    )
                    return str(cid)
            if resp.status_code in (400, 409):
                lookup_url = f"{self._v1_base(base)}/collections/{target}"
                retry = await self._client.get(
                    lookup_url,
                    follow_redirects=True,
                    timeout=20,
                )
                if retry.status_code == 200:
                    data = retry.json() or {}
                    collection = data.get("collection") or {}
                    cid = data.get("id") or collection.get("id")
                    if cid:
                        jlog(
                            logger,
                            event="chroma_collection_exists_v1",
                            name=target,
                            collection_id=cid,
                        )
                        return str(cid)
        except Exception as exc:
            jlog(
                logger,
                level="WARN",
                event="chroma_collection_create_failed_v1",
                name=target,
                error=str(exc),
            )
        return None

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
        url = f"{base}/api/v1/collections/{collection_id}/add"
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
            try:
                resp = await self._client.post(url, json=payload, timeout=60)
                resp.raise_for_status()
                jlog(
                    logger,
                    event="chroma_upsert_ok",
                    collection_id=collection_id,
                    count=item_count,
                )
                return True
            except httpx.HTTPStatusError as exc:
                jlog(
                    logger,
                    level="ERROR",
                    event="chroma_upsert_http_error",
                    collection_id=collection_id,
                    status=exc.response.status_code,
                    body=exc.response.text,
                )
                return False
            except Exception as exc:  # pragma: no cover - network guard
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
