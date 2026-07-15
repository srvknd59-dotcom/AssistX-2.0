"""The vector store: a real Elasticsearch index with a dense_vector field and
kNN search, the same approach the production chat_service.py/ingestor.py in
this repo use.

Elasticsearch is a separate server process, so this requires Elasticsearch
running and reachable at ES_URL before the backend starts. See
backend/README_ELASTICSEARCH.md for local setup on Windows.
"""

from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk


class ElasticsearchVectorStore:
    def __init__(
        self,
        url: str,
        index_prefix: str,
        dims: int,
        username: str = "",
        password: str = "",
    ) -> None:
        if username and password:
            self.client = Elasticsearch(url, basic_auth=(username, password))
        else:
            self.client = Elasticsearch(url)
        self.index_prefix = index_prefix
        self.dims = dims

    def _index_name(self, name: str) -> str:
        return f"{self.index_prefix}_{name}"

    def reset_collection(self, name: str) -> None:
        index = self._index_name(name)
        if self.client.indices.exists(index=index):
            self.client.indices.delete(index=index)
        self.client.indices.create(
            index=index,
            mappings={
                "properties": {
                    "text": {"type": "text"},
                    "source": {"type": "keyword"},
                    "chunk_index": {"type": "integer"},
                    "embedding": {
                        "type": "dense_vector",
                        "dims": self.dims,
                        "index": True,
                        "similarity": "cosine",
                    },
                }
            },
        )

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
        index = self._index_name(name)
        actions = [
            {
                "_index": index,
                "_id": doc_id,
                "_source": {"text": text, "embedding": embedding, **metadata},
            }
            for doc_id, text, embedding, metadata in zip(ids, texts, embeddings, metadatas)
        ]
        bulk(self.client, actions)
        self.client.indices.refresh(index=index)

    def count(self, name: str) -> int:
        index = self._index_name(name)
        if not self.client.indices.exists(index=index):
            return 0
        return self.client.count(index=index)["count"]

    def query(self, name: str, query_embedding: list[float], top_k: int) -> list[dict]:
        index = self._index_name(name)
        if not self.client.indices.exists(index=index):
            return []

        response = self.client.search(
            index=index,
            knn={
                "field": "embedding",
                "query_vector": query_embedding,
                "k": top_k,
                "num_candidates": max(top_k * 10, 50),
            },
            size=top_k,
            source=["text", "source", "chunk_index"],
        )

        return [
            {
                "text": hit["_source"]["text"],
                "metadata": {"source": hit["_source"]["source"], "chunk_index": hit["_source"].get("chunk_index")},
                "score": hit["_score"],
            }
            for hit in response["hits"]["hits"]
        ]

    def list_documents(self, name: str) -> list[dict]:
        index = self._index_name(name)
        if not self.client.indices.exists(index=index):
            return []

        response = self.client.search(
            index=index,
            size=0,
            aggs={"by_source": {"terms": {"field": "source", "size": 1000}}},
        )
        buckets = response["aggregations"]["by_source"]["buckets"]
        return [{"name": b["key"], "chunk_count": b["doc_count"]} for b in buckets]
