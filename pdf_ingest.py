# pdf_ingest.py
# Shared PDF/table/link extraction, chunking, and Elasticsearch indexing helpers.
#
# Both ingestor.py (CLI + REST) and ingest_service.py (REST-only) import this
# module so the extraction and single-PDF-upload indexing logic exists in
# exactly one place instead of being duplicated across the two services.

import os
import re
import hashlib
import pathlib
import logging
from typing import Dict, Iterable, List, Optional, Tuple

import fitz  # PyMuPDF
import pdfplumber
from pdfminer.high_level import extract_text as pdfminer_extract_text

try:
    import camelot
    HAS_CAMELOT = True
except Exception:
    HAS_CAMELOT = False

try:
    import pypdfium2 as pdfium
    HAS_PDFIUM = True
except Exception:
    HAS_PDFIUM = False

from elasticsearch import Elasticsearch, helpers

import llm_providers

log = logging.getLogger("pdf_ingest")

# --------------- Config ---------------
ES_HOST     = os.getenv("ES_HOST", "http://localhost:9200")
ES_USERNAME = os.getenv("ES_USERNAME", "elastic")
ES_PASSWORD = os.getenv("ES_PASSWORD", "changeme")

DOCS_ROOT      = os.getenv("DOCS_ROOT", "./manuals")
IMAGE_DIR_NAME = os.getenv("IMAGE_DIR_NAME", "Diagrams")
CHUNK_SIZE     = int(os.getenv("CHUNK_SIZE", "1200"))
CHUNK_OVERLAP  = int(os.getenv("CHUNK_OVERLAP", "180"))
BATCH_EMBED    = int(os.getenv("BATCH_EMBED", "40"))
USE_CAMELOT    = os.getenv("USE_CAMELOT", "0") == "1"
MAX_PAGES      = int(str(os.getenv("MAX_PAGES", "0")).strip() or "0")
UPLOAD_LOGICAL_PATH_PREFIX = os.getenv("UPLOAD_LOGICAL_PATH_PREFIX", "/uploaded_docs")


def new_es_client() -> Elasticsearch:
    return Elasticsearch(ES_HOST, basic_auth=(ES_USERNAME, ES_PASSWORD), verify_certs=False)


# --------------- Small helpers ---------------
def clean_text(s: str) -> str:
    if not s:
        return ""
    s = s.replace("\x00", " ")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def sanitize_index_name(index_name: str) -> str:
    index_name = index_name.strip().lower()
    index_name = re.sub(r"[^a-z0-9._-]+", "-", index_name)
    index_name = re.sub(r"-{2,}", "-", index_name).strip("-._")
    if not index_name:
        raise ValueError("Invalid index_name after sanitization")
    return index_name


def safe_filename(filename: str) -> str:
    if not filename:
        return "uploaded.pdf"
    filename = os.path.basename(filename)
    filename = re.sub(r"[^A-Za-z0-9._ -]+", "_", filename).strip()
    return filename or "uploaded.pdf"


def doc_id_for(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:16]


def batched(seq: Iterable, n: int):
    buf = []
    for x in seq:
        buf.append(x)
        if len(buf) >= n:
            yield buf
            buf = []
    if buf:
        yield buf


# --------------- Image captioning (provider-agnostic) ---------------
def generate_image_caption(path: str) -> str:
    caption = llm_providers.caption_image(
        path,
        "You caption technical diagrams for mcube manuals. Return a single concise caption (<= 25 words). Be literal; no speculation.",
        "Caption this diagram for search.",
    )
    if caption:
        return caption[:300]
    return pathlib.Path(path).stem.replace("_", " ").replace("-", " ").strip()


# --------------- Text extraction ---------------
def text_pymupdf(path: str, pno: int) -> str:
    with fitz.open(path) as doc:
        page = doc.load_page(pno)
        blocks = [b for b in page.get_text("blocks") if isinstance(b[4], str) and b[4].strip()]
        if blocks:
            blocks.sort(key=lambda b: (round(b[1], 1), round(b[0], 1)))
            return clean_text("\n".join(clean_text(b[4]) for b in blocks))
        return clean_text(page.get_text("text"))


def text_pdfminer(path: str, pno: int) -> str:
    return clean_text(pdfminer_extract_text(path, page_numbers=[pno]) or "")


def text_pdfium(path: str, pno: int) -> str:
    if not HAS_PDFIUM:
        return ""
    doc = pdfium.PdfDocument(path)
    page = doc.get_page(pno)
    textpage = page.get_textpage()
    s = textpage.get_text_bounded()
    textpage.close()
    page.close()
    doc.close()
    return clean_text(s or "")


def extract_text_best_effort(path: str, pno: int) -> str:
    candidates = [text_pymupdf(path, pno), text_pdfminer(path, pno)]
    if HAS_PDFIUM:
        candidates.append(text_pdfium(path, pno))
    return max(candidates, key=lambda s: len(s or ""))


# --------------- Link extraction ---------------
def extract_page_links(path: str, pno: int) -> Tuple[List[str], List[Dict[str, str]]]:
    urls: List[str] = []
    anchors: List[Dict[str, str]] = []
    try:
        doc = fitz.open(path)
        page = doc.load_page(pno)
        link_annots = page.get_links() or []
        words = page.get_text("words")
        for ln in link_annots:
            uri = (ln.get("uri") or "").strip()
            if not uri or not uri.startswith(("http://", "https://")):
                continue
            urls.append(uri)
            rect = fitz.Rect(ln["from"]) if ln.get("from") else None
            anchor_text = ""
            if rect and words:
                pad = 1.0
                rpad = fitz.Rect(rect.x0 - pad, rect.y0 - pad, rect.x1 + pad, rect.y1 + pad)
                near = [w[4] for w in words if rpad.intersects(fitz.Rect(w[0], w[1], w[2], w[3]))]
                if near:
                    anchor_text = " ".join(near).strip()
            anchors.append({"text": anchor_text, "url": uri})
        doc.close()
    except Exception as e:
        log.warning(f"link extract failed p{pno + 1} {path}: {e}")
    urls = list(dict.fromkeys(urls))
    return urls, anchors


# --------------- Tables ---------------
def to_markdown_table(rows: List[List[str]]) -> str:
    if not rows or len(rows) < 2:
        return "\n".join(["\t".join([(c or "") for c in r]) for r in (rows or [])])
    headers = [(h or "").strip() for h in rows[0]]
    md = "|" + "|".join(headers) + "|\n"
    md += "|" + "|".join(["---"] * len(headers)) + "|\n"
    for r in rows[1:]:
        md += "|" + "|".join([(c or "").replace("\n", " ").strip() for c in r]) + "|\n"
    return md


def tables_pdfplumber(pl_page) -> List[str]:
    out, seen = [], set()
    strategies = [
        dict(vertical_strategy="lines", horizontal_strategy="lines"),
        dict(
            vertical_strategy="text",
            horizontal_strategy="text",
            snap_tolerance=4,
            join_tolerance=4,
            edge_min_length=3,
            min_words_vertical=1,
            min_words_horizontal=1,
        ),
        dict(vertical_strategy="lines_strict", horizontal_strategy="lines_strict"),
    ]
    for st in strategies:
        try:
            found = pl_page.find_tables(table_settings=st)
            for t in found or []:
                rows = t.extract()
                if not rows or not any(any(c for c in row) for row in rows):
                    continue
                key = tuple(tuple(row) for row in rows[:2])
                if key in seen:
                    continue
                seen.add(key)
                out.append(to_markdown_table(rows))
        except Exception:
            pass
    return out


def tables_camelot(path: str, page_no_1based: int) -> List[str]:
    if not (USE_CAMELOT and HAS_CAMELOT):
        return []
    try:
        tabs = camelot.read_pdf(path, pages=str(page_no_1based), flavor="lattice")
        md = []
        for tb in tabs:
            rows = [tb.df.columns.tolist()] + tb.df.values.tolist()
            rows = [[(c or "").strip() for c in r] for r in rows]
            if len(rows) >= 2 and any(any(cell for cell in r) for r in rows[1:]):
                md.append(to_markdown_table(rows))
        return md
    except Exception:
        return []


# --------------- Chunking ---------------
def chunk_text(text: str, size=CHUNK_SIZE, overlap=CHUNK_OVERLAP) -> List[str]:
    out, start, n = [], 0, len(text)
    while start < n:
        end = min(start + size, n)
        out.append(text[start:end])
        if end == n:
            break
        start = max(0, end - overlap)
    return [c.strip() for c in out if c.strip()]


# --------------- Elasticsearch index management ---------------
def ensure_index(es: Elasticsearch, index_name: str, dims: int):
    mapping = {
        "settings": {"index": {"number_of_shards": 1, "number_of_replicas": 0}},
        "mappings": {
            "properties": {
                "content": {"type": "text"},
                "section": {"type": "text"},
                "chunk_type": {"type": "keyword"},
                "table_title": {"type": "text"},
                "caption": {"type": "text"},
                "vector": {"type": "dense_vector", "dims": dims, "index": True, "similarity": "cosine"},
                "doc_id": {"type": "keyword"},
                "chunk_id": {"type": "keyword"},
                "path": {"type": "keyword"},
                "filename": {"type": "keyword"},
                "version": {"type": "keyword"},
                "page": {"type": "integer"},
                "links": {"type": "text"},
                "primary_link": {"type": "text"},
                "source": {"type": "keyword"},
            }
        },
    }
    if not es.indices.exists(index=index_name):
        es.indices.create(index=index_name, body=mapping)


def ensure_alias(es: Elasticsearch, alias: str, index_name: str):
    try:
        es.indices.update_aliases(body={"actions": [{"add": {"index": index_name, "alias": alias}}]})
    except Exception:
        pass


# --------------- Single uploaded PDF ingest (shared REST logic) ---------------
def ingest_uploaded_pdf(
    pdf_path: str,
    index_name: str,
    original_filename: str,
    recreate_index: bool = False,
    index_alias: Optional[str] = None,
) -> Dict:
    es = new_es_client()

    dims = len(llm_providers.embed_texts(["dimension probe"])[0][0])
    log.info(f"Embedding dims = {dims}")

    filename = safe_filename(original_filename)
    version = filename
    logical_path = f"{UPLOAD_LOGICAL_PATH_PREFIX.rstrip('/')}/{filename}"

    if recreate_index and es.indices.exists(index=index_name):
        es.indices.delete(index=index_name, ignore=[400, 404])

    ensure_index(es, index_name, dims)
    if index_alias:
        ensure_alias(es, index_alias, index_name)

    rows = []
    page_count = 0

    with pdfplumber.open(pdf_path) as pl:
        page_count = len(pl.pages)
        if MAX_PAGES and MAX_PAGES > 0:
            page_count = min(page_count, MAX_PAGES)

        for pno in range(page_count):
            text = extract_text_best_effort(pdf_path, pno)
            tables = tables_pdfplumber(pl.pages[pno]) or tables_camelot(pdf_path, pno + 1)

            all_urls, anchors = extract_page_links(pdf_path, pno)
            primary_link = next((u for u in all_urls if u.lower().endswith(".mp4")), None)

            video_lines = []
            for a in anchors:
                if not a.get("url"):
                    continue
                txt = (a.get("text") or "").strip()
                if a["url"].lower().endswith(".mp4"):
                    if not txt:
                        txt = pathlib.Path(a["url"]).name
                    video_lines.append(f"VIDEO: {txt} -> {a['url']}")
            if video_lines:
                text = f"{text}\n\n" + "\n".join(video_lines)

            for md in tables:
                block = f"{filename} • {version} • page {pno + 1}\n[TABLE]\n{md}"
                rows.append({
                    "content": block, "section": "", "chunk_type": "table",
                    "table_title": None, "filename": filename, "version": version,
                    "page": pno + 1, "path": logical_path,
                    "links": all_urls, "primary_link": primary_link,
                    "source": "upload_api",
                })

            prefix = f"{filename} • {version} • page {pno + 1}\n"
            for ch in chunk_text(prefix + text):
                rows.append({
                    "content": ch, "section": "", "chunk_type": "text", "table_title": None,
                    "filename": filename, "version": version, "page": pno + 1,
                    "path": logical_path,
                    "links": all_urls, "primary_link": primary_link,
                    "source": "upload_api",
                })

            log.info(
                f"{filename} p{pno + 1}: chars={len(text)} tables={len(tables)} "
                f"links={len(all_urls)} primary={bool(primary_link)}"
            )

    docid = doc_id_for(f"{index_name}:{filename}")
    total_chunks = 0

    for batch in batched(rows, BATCH_EMBED):
        vecs, _usage = llm_providers.embed_texts([r["content"] for r in batch])
        actions = []
        for i, (r, v) in enumerate(zip(batch, vecs)):
            chunk_id = f"{docid}-{r['page']}-{i}"
            actions.append({
                "_index": index_name, "_id": chunk_id, "_op_type": "index",
                "_source": {**r, "doc_id": docid, "chunk_id": chunk_id, "vector": v},
            })
        helpers.bulk(es, actions, request_timeout=180)
        total_chunks += len(actions)

    log.info(f"Indexed: {filename} -> {index_name} (chunks={total_chunks})")

    return {
        "message": "PDF uploaded and indexed successfully",
        "filename": filename,
        "version": version,
        "index_name": index_name,
        "logical_path": logical_path,
        "chunks_indexed": total_chunks,
        "pages_processed": page_count,
    }
