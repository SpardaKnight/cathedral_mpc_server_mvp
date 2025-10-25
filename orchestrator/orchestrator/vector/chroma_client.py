from __future__ import annotations
import typing as t
import os
from dataclasses import dataclass
from urllib.parse import urlparse

from chromadb.config import Settings


@dataclass
class ChromaConfig:
    mode: str = "http"  # "http" | "embedded"
    url: str = "http://127.0.0.1:8000"
    collection_name: str = "cathedral"
    persist_dir: str = "/data/chroma"  # used only in embedded


class _HTTPClient:
    def __init__(self, url: str, collection: str):
        import chromadb

        parsed = urlparse(url)
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or 8000
        self._client = chromadb.HttpClient(host=host, port=port, settings=Settings())
        self._col = self._client.get_or_create_collection(name=collection, metadata={"hnsw:space": "cosine"})

    def health(self) -> bool:
        try:
            _ = self._client.list_collections()
            return True
        except Exception:
            return False

    def upsert(
        self,
        ids: t.List[str],
        embeddings: t.List[t.List[float]],
        documents: t.List[str],
        metadatas: t.List[dict],
    ) -> dict:
        try:
            self._col.upsert(ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas)
            return {"result": "ok", "upserted": len(ids)}
        except Exception as e:
            return {"result": "error", "error": str(e)}

    def query(self, query_texts: t.List[str], n_results: int = 5, where: t.Optional[dict] = None) -> dict:
        try:
            res = self._col.query(query_texts=query_texts, n_results=n_results, where=where)
            return {"result": "ok", "data": res}
        except Exception as e:
            return {"result": "error", "error": str(e)}


class _EmbeddedClient:
    def __init__(self, persist_dir: str, collection: str):
        import chromadb

        os.makedirs(persist_dir, exist_ok=True)
        self._client = chromadb.Client(Settings(persist_directory=persist_dir, is_persistent=True))
        self._col = self._client.get_or_create_collection(name=collection, metadata={"hnsw:space": "cosine"})

    def health(self) -> bool:
        try:
            _ = self._client.list_collections()
            return True
        except Exception:
            return False

    def upsert(self, ids, embeddings, documents, metadatas):
        try:
            self._col.upsert(ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas)
            return {"result": "ok", "upserted": len(ids)}
        except Exception as e:
            return {"result": "error", "error": str(e)}

    def query(self, query_texts, n_results=5, where=None):
        try:
            res = self._col.query(query_texts=query_texts, n_results=n_results, where=where)
            return {"result": "ok", "data": res}
        except Exception as e:
            return {"result": "error", "error": str(e)}


class ChromaClient:
    def __init__(self, cfg: ChromaConfig):
        self.cfg = cfg
        self._impl: t.Union[_EmbeddedClient, _HTTPClient]
        if cfg.mode == "embedded":
            self._impl = _EmbeddedClient(cfg.persist_dir, cfg.collection_name)
        else:
            self._impl = _HTTPClient(cfg.url, cfg.collection_name)

    def health(self) -> bool:
        return self._impl.health()

    def upsert(self, ids, embeddings, documents, metadatas):
        return self._impl.upsert(ids, embeddings, documents, metadatas)

    def query(self, query_texts, n_results=5, where=None):
        return self._impl.query(query_texts, n_results=n_results, where=where)
