"""A real, on-disk vector database (Chroma), instead of the in-memory NumPy
array used in rag-ui-tutorial. Chroma runs embedded in this process, persists
to a folder on disk, and needs no server or Docker — but it's the same kind
of engine (HNSW approximate nearest-neighbor index) that production vector
databases use, just running locally instead of as a managed cluster.
"""

import chromadb
from chromadb.config import Settings as ChromaSettings


class ChromaVectorStore:
    def __init__(self, persist_dir: str):
        self.client = chromadb.PersistentClient(
            path=persist_dir, settings=ChromaSettings(anonymized_telemetry=False)
        )

    def _collection(self, name: str):
        # cosine distance space matches how OpenAI embeddings are typically compared
        return self.client.get_or_create_collection(name=name, metadata={"hnsw:space": "cosine"})

    def reset_collection(self, name: str) -> None:
        try:
            self.client.delete_collection(name)
        except Exception:
            pass
        self._collection(name)

    def add(
        self,
        name: str,
        ids: list[str],
        texts: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict],
    ) -> None:
        if not ids:
            return
        self._collection(name).add(ids=ids, documents=texts, embeddings=embeddings, metadatas=metadatas)

    def count(self, name: str) -> int:
        try:
            return self._collection(name).count()
        except Exception:
            return 0

    def query(self, name: str, query_embedding: list[float], top_k: int) -> list[dict]:
        collection = self._collection(name)
        total = collection.count()
        if total == 0:
            return []

        results = collection.query(query_embeddings=[query_embedding], n_results=min(top_k, total))
        out = []
        for doc, meta, distance in zip(
            results["documents"][0], results["metadatas"][0], results["distances"][0]
        ):
            out.append({"text": doc, "metadata": meta, "score": 1 - distance})
        return out
