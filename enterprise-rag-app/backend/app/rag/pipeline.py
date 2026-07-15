"""Ties chunking + embeddings + the vector store + the LLM together.

This mirrors the core loop of the production chat_service.py/ingestor.py in
this repo, simplified to one document collection and one similarity search
instead of Elasticsearch's hybrid BM25 + vector + HyDE + multi-query
expansion:

    ingest:   read files -> chunk/table/caption -> embed -> store in Elasticsearch
    ask:      embed the question -> retrieve top_k chunks -> ask the LLM,
              grounded in only what was retrieved, with citations

PDFs produce three kinds of content units (see chunking.py): plain text
(word-chunked as usual), tables (kept as one Markdown-table chunk each, so a
table never gets split mid-row), and images (captioned by a vision model,
one chunk per captioned image) - the same manuals + diagram-caption idea the
production ingestor.py uses, just for one document type instead of a
manuals/diagrams split.
"""

import uuid
from collections import defaultdict
from pathlib import Path

from openai import OpenAI

from app.config import settings
from app.rag.chunking import ContentUnit, chunk_text, load_documents
from app.rag.embeddings import caption_image, embed_texts
from app.rag.vector_store import ElasticsearchVectorStore

COLLECTION_NAME = "documents"


def build_vector_store() -> ElasticsearchVectorStore:
    return ElasticsearchVectorStore(
        url=settings.es_url,
        index_prefix=settings.es_index_prefix,
        dims=settings.embed_dims,
        username=settings.es_username,
        password=settings.es_password,
    )


SYSTEM_PROMPT = """You are a helpful assistant that answers questions about a set of ingested
documents, using ONLY the numbered context passages below. Some passages are text, some are
tables (Markdown format), and some are descriptions of images/diagrams - treat all three as
equally valid evidence.

Rules:
- If the answer isn't in the context, say you don't know — never make something up.
- Cite every fact inline using its passage number, e.g. [1].
- When a passage is a table, you may reproduce relevant rows as a Markdown table in your answer.
- Keep answers concise.
"""


class RagPipeline:
    def __init__(self) -> None:
        self.client = OpenAI(api_key=settings.openai_api_key)
        self.store = build_vector_store()

    # -- Ingestion -----------------------------------------------------

    def ingest_documents(self, root: Path | None = None) -> dict:
        """Read every file in `root` (defaults to data/documents), chunk/table/caption it,
        embed it, and (re)build the index."""
        units = load_documents(root or settings.documents_dir)
        self.store.reset_collection(COLLECTION_NAME)

        ids, texts, metadatas = [], [], []
        chunk_index_by_source: dict[str, int] = defaultdict(int)
        images_captioned_by_source: dict[str, int] = defaultdict(int)
        tables_found = 0
        images_captioned = 0

        for unit in units:
            for chunk_text_value, content_type in self._render_unit(unit, images_captioned_by_source):
                if content_type == "table":
                    tables_found += 1
                elif content_type == "image":
                    images_captioned += 1

                idx = chunk_index_by_source[unit.source]
                chunk_index_by_source[unit.source] = idx + 1

                ids.append(f"{unit.source}::{idx}")
                texts.append(chunk_text_value)
                metadatas.append(
                    {
                        "source": unit.source,
                        "chunk_index": idx,
                        "content_type": content_type,
                        "page": unit.page,
                    }
                )

        if texts:
            embeddings = embed_texts(self.client, texts, settings.embed_model)
            self.store.add(COLLECTION_NAME, ids, texts, embeddings, metadatas)

        return {
            "documents_indexed": len({u.source for u in units}),
            "chunks_indexed": len(texts),
            "tables_indexed": tables_found,
            "images_captioned": images_captioned,
        }

    def _render_unit(self, unit: ContentUnit, images_captioned_by_source: dict[str, int]):
        """Yield (text, content_type) pairs for one content unit."""
        if unit.unit_type == "text":
            for chunk in chunk_text(unit.text, settings.chunk_size_words, settings.chunk_overlap_words):
                yield chunk, "text"

        elif unit.unit_type == "table":
            yield unit.text, "table"

        elif unit.unit_type == "image":
            if not settings.caption_images:
                return
            if images_captioned_by_source[unit.source] >= settings.max_images_per_document:
                return
            caption = caption_image(self.client, unit.image_bytes, settings.chat_model)
            if not caption:
                return
            images_captioned_by_source[unit.source] += 1
            page_note = f" (page {unit.page})" if unit.page else ""
            yield f"[Image{page_note}]: {caption}", "image"

    def counts(self) -> dict:
        by_type = self.store.count_by_content_type(COLLECTION_NAME)
        return {
            "chunks_indexed": self.store.count(COLLECTION_NAME),
            "tables_indexed": by_type.get("table", 0),
            "images_indexed": by_type.get("image", 0),
        }

    # -- Retrieval + generation -----------------------------------------

    def retrieve(self, question: str, top_k: int | None = None) -> list[dict]:
        top_k = top_k or settings.top_k
        query_embedding = embed_texts(self.client, [question], settings.embed_model)[0]
        hits = self.store.query(COLLECTION_NAME, query_embedding, top_k)

        return [
            {
                "label": hit["metadata"]["source"],
                "snippet": hit["text"],
                "score": hit["score"],
                "content_type": hit["metadata"].get("content_type") or "text",
                "page": hit["metadata"].get("page"),
            }
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
