"""Splitting documents into small, embeddable passages."""

from pathlib import Path

from pypdf import PdfReader

SUPPORTED_EXTENSIONS = {".txt", ".md", ".pdf"}


def load_documents(docs_dir: Path) -> list[tuple[str, str]]:
    """Read every supported file in docs_dir and return (filename, text) pairs."""
    documents: list[tuple[str, str]] = []
    if not docs_dir.exists():
        return documents

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


def chunk_text(text: str, chunk_size: int = 180, overlap: int = 30) -> list[str]:
    """Split text into overlapping word-based windows (see HOW_RAG_WORKS in rag-ui-tutorial)."""
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
