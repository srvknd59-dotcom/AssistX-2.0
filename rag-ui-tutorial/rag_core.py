"""
rag_core.py — the whole RAG pipeline in one small, readable file.

RAG stands for Retrieval-Augmented Generation. In plain English:
before asking an AI model a question, we first go find the few
paragraphs in our own documents that are most relevant, and hand
those to the model along with the question. That's it — that's RAG.

This file has five jobs, done in this order the first time you run
the app, and the last two every time you ask a question:

    1. load_documents   -> read your files off disk
    2. chunk_text        -> cut long documents into small pieces
    3. embed_texts        -> turn each piece into a list of numbers
    4. VectorStore         -> save/search those numbers by similarity
    5. answer_question      -> retrieve the best pieces, ask the LLM

See HOW_RAG_WORKS.md in this folder for the concepts behind each
step. This file is the implementation.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from openai import OpenAI
from pypdf import PdfReader

SUPPORTED_EXTENSIONS = {".txt", ".md", ".pdf"}


# ---------------------------------------------------------------------------
# Step 1: Load documents
# ---------------------------------------------------------------------------

def load_documents(docs_dir: str | Path) -> list[tuple[str, str]]:
    """Read every supported file in docs_dir and return (filename, text) pairs."""
    docs_dir = Path(docs_dir)
    documents: list[tuple[str, str]] = []

    for path in sorted(docs_dir.rglob("*")):
        if path.suffix.lower() not in SUPPORTED_EXTENSIONS or not path.is_file():
            continue

        if path.suffix.lower() == ".pdf":
            reader = PdfReader(str(path))
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
        else:
            text = path.read_text(encoding="utf-8", errors="ignore")

        text = text.strip()
        if text:
            documents.append((path.name, text))

    return documents


# ---------------------------------------------------------------------------
# Step 2: Chunk text
# ---------------------------------------------------------------------------

def chunk_text(text: str, chunk_size: int = 180, overlap: int = 30) -> list[str]:
    """Split text into overlapping word-based windows.

    chunk_size/overlap are measured in words, not characters, so this
    stays readable. Overlap keeps a sentence that spans two chunks
    from losing its meaning in either half — the price is that a
    little text gets embedded twice.
    """
    words = text.split()
    if not words:
        return []

    chunks = []
    step = max(chunk_size - overlap, 1)
    for start in range(0, len(words), step):
        chunk_words = words[start : start + chunk_size]
        chunks.append(" ".join(chunk_words))
        if start + chunk_size >= len(words):
            break
    return chunks


# ---------------------------------------------------------------------------
# Step 3: Embeddings
# ---------------------------------------------------------------------------

def embed_texts(client: OpenAI, texts: list[str], model: str, batch_size: int = 100) -> np.ndarray:
    """Turn a list of strings into a 2D array of embedding vectors (one row per string)."""
    vectors: list[list[float]] = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        response = client.embeddings.create(model=model, input=batch)
        vectors.extend(item.embedding for item in response.data)
    return np.array(vectors, dtype=np.float32)


# ---------------------------------------------------------------------------
# Step 4: A tiny vector store
# ---------------------------------------------------------------------------
#
# Real systems (including chat_service.py / ingestor.py elsewhere in this
# repo) use a dedicated database like Elasticsearch, FAISS, or Chroma to
# store and search millions of vectors quickly. For a handful of documents,
# plain NumPy is plenty fast and — more importantly for learning — you can
# read every line of what it's doing.

@dataclass
class VectorStore:
    chunks: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    embeddings: np.ndarray | None = None

    def add(self, chunks: list[str], sources: list[str], embeddings: np.ndarray) -> None:
        self.chunks.extend(chunks)
        self.sources.extend(sources)
        self.embeddings = embeddings if self.embeddings is None else np.vstack([self.embeddings, embeddings])

    def search(self, query_embedding: np.ndarray, top_k: int = 4) -> list[dict]:
        """Return the top_k chunks most similar to the query, using cosine similarity."""
        if self.embeddings is None or len(self.chunks) == 0:
            return []

        # Cosine similarity = dot product of *normalized* vectors.
        # Normalizing first means "similarity" only measures direction
        # (meaning), not vector length (which embedding models don't
        # use to encode meaning anyway).
        doc_norms = self.embeddings / np.linalg.norm(self.embeddings, axis=1, keepdims=True)
        query_norm = query_embedding / np.linalg.norm(query_embedding)
        scores = doc_norms @ query_norm

        top_indices = np.argsort(-scores)[:top_k]
        return [
            {"chunk": self.chunks[i], "source": self.sources[i], "score": float(scores[i])}
            for i in top_indices
        ]

    def save(self, store_dir: str | Path) -> None:
        store_dir = Path(store_dir)
        store_dir.mkdir(parents=True, exist_ok=True)
        np.save(store_dir / "embeddings.npy", self.embeddings)
        (store_dir / "chunks.json").write_text(
            json.dumps({"chunks": self.chunks, "sources": self.sources}), encoding="utf-8"
        )

    @classmethod
    def load(cls, store_dir: str | Path) -> "VectorStore":
        store_dir = Path(store_dir)
        data = json.loads((store_dir / "chunks.json").read_text(encoding="utf-8"))
        embeddings = np.load(store_dir / "embeddings.npy")
        return cls(chunks=data["chunks"], sources=data["sources"], embeddings=embeddings)

    @staticmethod
    def exists(store_dir: str | Path) -> bool:
        store_dir = Path(store_dir)
        return (store_dir / "embeddings.npy").exists() and (store_dir / "chunks.json").exists()


def build_index(
    client: OpenAI,
    docs_dir: str | Path,
    store_dir: str | Path,
    embed_model: str,
    chunk_size: int = 180,
    overlap: int = 30,
) -> tuple[VectorStore, dict]:
    """Run steps 1-4 end to end and persist the result to disk."""
    documents = load_documents(docs_dir)

    all_chunks: list[str] = []
    all_sources: list[str] = []
    for filename, text in documents:
        for chunk in chunk_text(text, chunk_size=chunk_size, overlap=overlap):
            all_chunks.append(chunk)
            all_sources.append(filename)

    store = VectorStore()
    if all_chunks:
        embeddings = embed_texts(client, all_chunks, model=embed_model)
        store.add(all_chunks, all_sources, embeddings)
        store.save(store_dir)

    stats = {"documents": len(documents), "chunks": len(all_chunks)}
    return store, stats


# ---------------------------------------------------------------------------
# Step 5: Retrieve + generate an answer
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are a helpful assistant that answers questions using ONLY the
context provided below. Each context passage is numbered, e.g. [1], [2].

Rules:
- If the answer isn't in the context, say you don't know — do not make something up.
- When you use a fact from a passage, cite it inline like [1].
- Keep answers short and clear.
"""


def answer_question(
    client: OpenAI,
    store: VectorStore,
    question: str,
    chat_model: str,
    embed_model: str,
    top_k: int = 4,
) -> dict:
    """Embed the question, retrieve relevant chunks, and ask the LLM to answer from them."""
    query_embedding = embed_texts(client, [question], model=embed_model)[0]
    results = store.search(query_embedding, top_k=top_k)

    context = "\n\n".join(f"[{i+1}] (from {r['source']}) {r['chunk']}" for i, r in enumerate(results))
    user_prompt = f"Context:\n{context}\n\nQuestion: {question}"

    response = client.chat.completions.create(
        model=chat_model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
    )

    return {
        "answer": response.choices[0].message.content,
        "sources": results,
    }
