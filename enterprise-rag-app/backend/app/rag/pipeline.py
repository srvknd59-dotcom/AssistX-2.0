"""Ties chunking + embeddings + the vector store + the LLM together.

This mirrors the core loop of the production chat_service.py/ingestor.py in
this repo, simplified to one document collection and one similarity search
instead of Elasticsearch's hybrid BM25 + vector + HyDE + multi-query
expansion:

    ingest:   read files -> chunk -> embed -> store in the vector store
    ask:      embed the question -> retrieve top_k chunks -> ask the LLM,
              grounded in only what was retrieved, with citations

The vector store itself is swappable — Chroma (embedded, default) or
Elasticsearch (a real server, same engine the production app uses) — chosen
by VECTOR_DB_BACKEND in .env. Both implement the same reset_collection/add/
count/query/list_documents interface, so nothing else in this file needs to
know which one is active.
"""

import uuid
from pathlib import Path

from openai import OpenAI

from app.config import settings
from app.rag.chunking import chunk_text, load_documents
from app.rag.embeddings import embed_texts
from app.rag.vector_store import ChromaVectorStore

COLLECTION_NAME = "documents"


def build_vector_store():
    if settings.vector_db_backend == "elasticsearch":
        from app.rag.vector_store_elasticsearch import ElasticsearchVectorStore

        return ElasticsearchVectorStore(
            url=settings.es_url,
            index_prefix=settings.es_index_prefix,
            dims=settings.embed_dims,
            username=settings.es_username,
            password=settings.es_password,
        )
    return ChromaVectorStore(str(settings.chroma_path))


SYSTEM_PROMPT = """You are a helpful assistant that answers questions about a set of ingested
documents, using ONLY the numbered context passages below.

Rules:
- If the answer isn't in the context, say you don't know — never make something up.
- Cite every fact inline using its passage number, e.g. [1].
- Keep answers concise.
"""


class RagPipeline:
    def __init__(self) -> None:
        self.client = OpenAI(api_key=settings.openai_api_key)
        self.store = build_vector_store()

    # -- Ingestion -----------------------------------------------------

    def ingest_documents(self, root: Path | None = None) -> dict:
        """Read every file in `root` (defaults to data/documents), chunk it, embed it, and (re)build the index."""
        documents = load_documents(root or settings.documents_dir)
        self.store.reset_collection(COLLECTION_NAME)

        ids, texts, metadatas = [], [], []
        for filename, text in documents:
            for i, chunk in enumerate(
                chunk_text(text, settings.chunk_size_words, settings.chunk_overlap_words)
            ):
                ids.append(f"{filename}::{i}")
                texts.append(chunk)
                metadatas.append({"source": filename, "chunk_index": i})

        if texts:
            embeddings = embed_texts(self.client, texts, settings.embed_model)
            self.store.add(COLLECTION_NAME, ids, texts, embeddings, metadatas)

        return {"documents_indexed": len(documents), "chunks_indexed": len(texts)}

    def counts(self) -> dict:
        return {"chunks_indexed": self.store.count(COLLECTION_NAME)}

    # -- Retrieval + generation -----------------------------------------

    def retrieve(self, question: str, top_k: int | None = None) -> list[dict]:
        top_k = top_k or settings.top_k
        query_embedding = embed_texts(self.client, [question], settings.embed_model)[0]
        hits = self.store.query(COLLECTION_NAME, query_embedding, top_k)

        return [
            {"label": hit["metadata"]["source"], "snippet": hit["text"], "score": hit["score"]}
            for hit in hits
        ]

    def answer(self, question: str, history: list[dict] | None = None) -> dict:
        sources = self.retrieve(question)

        context = "\n\n".join(f"[{i+1}] ({s['label']}) {s['snippet']}" for i, s in enumerate(sources))

        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        for turn in (history or [])[-6:]:
            messages.append({"role": turn["role"], "content": turn["content"]})
        messages.append({"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"})

        response = self.client.chat.completions.create(
            model=settings.chat_model,
            messages=messages,
            temperature=0.2,
        )

        return {"answer": response.choices[0].message.content, "sources": sources}


def new_session_id() -> str:
    return uuid.uuid4().hex
