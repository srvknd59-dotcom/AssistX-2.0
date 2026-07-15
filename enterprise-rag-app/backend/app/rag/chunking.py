"""Loading and splitting documents into small, embeddable units.

Plain text/markdown files become one "text" unit each, chunked by
chunk_text() the way they always were. PDFs are richer: pdfplumber pulls
page text *and* detects tables (serialized to Markdown so they stay
structured instead of collapsing into jumbled inline text), and pypdf pulls
embedded images out for vision captioning in pipeline.py. This mirrors what
the production ingestor.py does for manuals + diagrams, just against one
document type instead of a manuals/diagrams split.
"""

import io
from dataclasses import dataclass
from pathlib import Path

import pdfplumber
from pypdf import PdfReader

SUPPORTED_EXTENSIONS = {".txt", ".md", ".pdf"}

# Skip tiny embedded images (logos, bullet icons, dividers) - not worth a
# vision API call and would just add noise to search results.
MIN_IMAGE_DIMENSION = 80


@dataclass
class ContentUnit:
    """One piece of extracted content, before chunking/captioning/embedding."""

    source: str
    unit_type: str  # "text" | "table" | "image"
    text: str = ""  # populated for text/table; filled in by pipeline.py for images
    image_bytes: bytes | None = None  # PNG bytes, only set when unit_type == "image"
    page: int | None = None


def load_documents(docs_dir: Path) -> list[ContentUnit]:
    """Read every supported file in docs_dir and return its content units."""
    units: list[ContentUnit] = []
    if not docs_dir.exists():
        return units

    for path in sorted(docs_dir.rglob("*")):
        if path.suffix.lower() not in SUPPORTED_EXTENSIONS or not path.is_file():
            continue

        if path.suffix.lower() == ".pdf":
            units.extend(_load_pdf(path))
        else:
            text = path.read_text(encoding="utf-8", errors="ignore").strip()
            if text:
                units.append(ContentUnit(source=path.name, unit_type="text", text=text))

    return units


def _load_pdf(path: Path) -> list[ContentUnit]:
    units: list[ContentUnit] = []

    with pdfplumber.open(path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            text = (page.extract_text() or "").strip()
            if text:
                units.append(ContentUnit(source=path.name, unit_type="text", text=text, page=page_num))

            for table in page.extract_tables():
                markdown_table = _table_to_markdown(table)
                if markdown_table:
                    units.append(
                        ContentUnit(source=path.name, unit_type="table", text=markdown_table, page=page_num)
                    )

    units.extend(_extract_images(path))
    return units


def _table_to_markdown(rows: list[list[str | None]]) -> str:
    cleaned = [[(cell or "").strip() for cell in row] for row in rows]
    cleaned = [row for row in cleaned if any(cell for cell in row)]
    if not cleaned:
        return ""

    header, *body = cleaned
    width = len(header)
    lines = [
        "| " + " | ".join(c or " " for c in header) + " |",
        "| " + " | ".join("---" for _ in range(width)) + " |",
    ]
    for row in body:
        row = (row + [""] * width)[:width]
        lines.append("| " + " | ".join(c or " " for c in row) + " |")
    return "\n".join(lines)


def _extract_images(path: Path) -> list[ContentUnit]:
    units: list[ContentUnit] = []
    try:
        reader = PdfReader(str(path))
    except Exception:
        return units

    for page_num, page in enumerate(reader.pages, start=1):
        try:
            images = page.images
        except Exception:
            continue

        for image in images:
            try:
                pil_image = image.image
            except Exception:
                continue
            if pil_image is None:
                continue
            if pil_image.width < MIN_IMAGE_DIMENSION or pil_image.height < MIN_IMAGE_DIMENSION:
                continue

            buffer = io.BytesIO()
            pil_image.convert("RGB").save(buffer, format="PNG")
            units.append(
                ContentUnit(source=path.name, unit_type="image", image_bytes=buffer.getvalue(), page=page_num)
            )

    return units


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
