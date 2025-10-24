import os, time, typing as t
from dataclasses import dataclass

# We intentionally use the official chromadb Python client in HTTP mode.
# Docs: https://cookbook.chromadb.dev/running/running-chroma/ (HTTP server exposes FastAPI with /docs) 
# Client API: chromadb.HttpClient(host, port)  (See examples in community answers and code) 

@dataclass
class ChromaConfig:
    mode: str = "http"
    url: str = "http://127.0.0.1:8000"
    collection_name: str = "cathedral"

class ChromaClientHTTP:
    def __init__(self, url: str, collection_name: str):
        import chromadb
        from urllib.parse import urlparse
        parsed = urlparse(url)
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or 8000
        self._client = chromadb.HttpClient(host=host, port=port, settings=chromadb.config.Settings())
        # Create or get collection. We do NOT set an embedding function because we supply embeddings from LM Studio.
        self._collection = self._client.get_or_create_collection(name=collection_name, metadata={{"hnsw:space":"cosine"}})

    def health(self) -> bool:
        # A simple call to list collections ensures the server is reachable.
        try:
            _ = self._client.list_collections()
            return True
        except Exception:
            return False

    def upsert(self, ids: t.List[str], embeddings: t.List[t.List[float]], documents: t.List[str], metadatas: t.List[dict]) -> dict:
        # If ID already exists, Chroma updates it; dimension mismatches will raise — we catch and return error.
        try:
            self._collection.upsert(ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas)
            return {{"result":"ok","upserted":len(ids)}}
        except Exception as e:
            return {{"result":"error","error":str(e)}}

    def query(self, query_texts: t.List[str], n_results: int = 5, where: t.Optional[dict] = None) -> dict:
        try:
            res = self._collection.query(query_texts=query_texts, n_results=n_results, where=where)
            return {{"result":"ok","data":res}}
        except Exception as e:
            return {{"result":"error","error":str(e)}}

class ChromaClient:
    def __init__(self, cfg: ChromaConfig):
        self.cfg = cfg
        if cfg.mode != "http":
            # Embedded mode is explicitly out of scope for HA — placeholder raise to prevent accidental local vectors.
            raise RuntimeError("Embedded Chroma mode is not allowed on HA node; use HTTP mode.")
        self._http = ChromaClientHTTP(cfg.url, cfg.collection_name)

    def health(self) -> bool:
        return self._http.health()

    def upsert(self, ids, embeddings, documents, metadatas):
        return self._http.upsert(ids, embeddings, documents, metadatas)

    def query(self, query_texts, n_results=5, where=None):
        return self._http.query(query_texts, n_results=n_results, where=where)
