"""Ties chunking + embeddings + the vector store + the LLM together.

Two collections are indexed, mirroring the two source types the production
chat_service.py/ingestor.py in this repo retrieve from:

    "manuals" -> product documentation (chunked files, like the manuals index)
    "tickets" -> past support tickets  (like the JSM ticket index)

A question is answered by retrieving the best passages from *both*
collections in parallel and letting the model cite whichever ones it used —
the same "hybrid source" grounding pattern as the production app, simplified
to a single vector similarity search per collection instead of BM25 + vector
+ HyDE + multi-query expansion.
"""

import json
import uuid

from openai import OpenAI

from app.config import settings
from app.rag.chunking import chunk_text, load_documents
from app.rag.embeddings import embed_texts
from app.rag.vector_store import ChromaVectorStore

SYSTEM_PROMPT = """You are an enterprise support assistant. Answer the user's question using
ONLY the numbered context passages below, which come from product manuals and past support
tickets.

Rules:
- If the answer isn't in the context, say you don't know — never make something up.
- Cite every fact inline using its passage number, e.g. [1].
- Prefer manual passages for "how do I / what is" questions, and ticket passages for
  troubleshooting a specific reported problem, but use whichever is actually relevant.
- Keep answers concise.
"""


class RagPipeline:
    def __init__(self) -> None:
        self.client = OpenAI(api_key=settings.openai_api_key)
        self.store = ChromaVectorStore(str(settings.chroma_path))

    # -- Ingestion -----------------------------------------------------

    def ingest_manuals(self) -> dict:
        documents = load_documents(settings.manuals_dir)
        self.store.reset_collection("manuals")

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
            self.store.add("manuals", ids, texts, embeddings, metadatas)

        return {"documents": len(documents), "chunks": len(texts)}

    def ingest_tickets(self) -> dict:
        self.store.reset_collection("tickets")
        if not settings.tickets_file.exists():
            return {"tickets": 0}

        tickets = json.loads(settings.tickets_file.read_text(encoding="utf-8"))

        ids, texts, metadatas = [], [], []
        for ticket in tickets:
            text = (
                f"Subject: {ticket['subject']}\n"
                f"Problem: {ticket['description']}\n"
                f"Resolution: {ticket['resolution']}"
            )
            ids.append(str(ticket["id"]))
            texts.append(text)
            metadatas.append({"ticket_id": str(ticket["id"]), "subject": ticket["subject"]})

        if texts:
            embeddings = embed_texts(self.client, texts, settings.embed_model)
            self.store.add("tickets", ids, texts, embeddings, metadatas)

        return {"tickets": len(tickets)}

    def ingest_all(self) -> dict:
        manuals_stats = self.ingest_manuals()
        tickets_stats = self.ingest_tickets()
        return {
            "manuals_indexed": manuals_stats["documents"],
            "manual_chunks": manuals_stats["chunks"],
            "tickets_indexed": tickets_stats.get("tickets", 0),
        }

    def counts(self) -> dict:
        return {
            "manuals_indexed": self.store.count("manuals"),
            "tickets_indexed": self.store.count("tickets"),
        }

    # -- Retrieval + generation -----------------------------------------

    def retrieve(self, question: str, top_k_per_collection: int | None = None) -> list[dict]:
        top_k = top_k_per_collection or settings.top_k_per_collection
        query_embedding = embed_texts(self.client, [question], settings.embed_model)[0]

        manual_hits = self.store.query("manuals", query_embedding, top_k)
        ticket_hits = self.store.query("tickets", query_embedding, top_k)

        results = []
        for hit in manual_hits:
            results.append(
                {
                    "type": "manual",
                    "label": hit["metadata"]["source"],
                    "snippet": hit["text"],
                    "score": hit["score"],
                }
            )
        for hit in ticket_hits:
            results.append(
                {
                    "type": "ticket",
                    "label": f"Ticket #{hit['metadata']['ticket_id']}: {hit['metadata']['subject']}",
                    "snippet": hit["text"],
                    "score": hit["score"],
                }
            )

        results.sort(key=lambda r: r["score"], reverse=True)
        return results

    def answer(self, question: str, history: list[dict] | None = None) -> dict:
        sources = self.retrieve(question)

        context = "\n\n".join(f"[{i+1}] ({s['type']}: {s['label']}) {s['snippet']}" for i, s in enumerate(sources))

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
