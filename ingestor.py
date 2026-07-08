# ingestor.py - REST service (mirrors ingest_service.py endpoints)
import os, re, hashlib, pathlib, argparse, logging, base64, sys, tempfile
from typing import List, Optional, Iterable, Tuple, Dict

import fitz  # PyMuPDF
from pdfminer.high_level import extract_text as pdfminer_extract_text
import pdfplumber

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

import requests
from tenacity import retry, wait_exponential, stop_after_attempt
from elasticsearch import Elasticsearch, helpers
from dotenv import load_dotenv
from tqdm import tqdm
from flask import Flask, request, jsonify

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("ingest")

app = Flask(__name__)

# --------------- Config ---------------
AZURE_ENDPOINT         = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_API_KEY          = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_EMBED_DEPLOYMENT = os.getenv("AZURE_OPENAI_EMBED_DEPLOYMENT")
AZURE_API_VERSION      = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
AZURE_VISION_DEPLOYMENT = os.getenv("AZURE_OPENAI_VISION_DEPLOYMENT", os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT", ""))
HEADERS = {"api-key": AZURE_API_KEY, "Content-Type": "application/json"}

ES_HOST         = os.getenv("ES_HOST", "http://localhost:9200")
ES_USERNAME     = os.getenv("ES_USERNAME", "elastic")
ES_PASSWORD     = os.getenv("ES_PASSWORD", "changeme")
ES_INDEX_PREFIX = os.getenv("ES_INDEX_PREFIX", "").strip()
ES_INDEX_SINGLE = os.getenv("ES_INDEX", "").strip()
ES_ALIAS        = os.getenv("ES_ALIAS", "").strip()

DOCS_ROOT      = os.getenv("DOCS_ROOT", "./manuals")
IMAGE_DIR_NAME = os.getenv("IMAGE_DIR_NAME", "Diagrams")
CHUNK_SIZE     = int(os.getenv("CHUNK_SIZE", "1200"))
CHUNK_OVERLAP  = int(os.getenv("CHUNK_OVERLAP", "180"))
BATCH_EMBED    = int(os.getenv("BATCH_EMBED", "40"))
USE_CAMELOT    = os.getenv("USE_CAMELOT", "0") == "1"
MAX_PAGES      = int(str(os.getenv("MAX_PAGES", "0")).strip() or "0")
UPLOAD_LOGICAL_PATH_PREFIX = os.getenv("UPLOAD_LOGICAL_PATH_PREFIX", "/uploaded_docs")

# --------------- Small helpers ---------------
def clean_text(s: str) -> str:
    if not s: return ""
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

def slug_version(version: str) -> str:
    v = version.strip().lower().replace("version", "v")
    v = re.sub(r"[^a-z0-9]+", "-", v).replace(".", "_").strip("-")
    return v or "unknown"

def _effective_prefix_and_alias() -> (str, Optional[str]):
    if ES_INDEX_PREFIX: return ES_INDEX_PREFIX, (ES_ALIAS or f"{ES_INDEX_PREFIX}_all")
    if ES_INDEX_SINGLE: return ES_INDEX_SINGLE, (ES_ALIAS or f"{ES_INDEX_SINGLE}_all")
    return "mcube_manuals", "mcube_manuals_all"

INDEX_PREFIX, INDEX_ALIAS = _effective_prefix_and_alias()

def index_for_version(version: str) -> str:
    return f"{INDEX_PREFIX}-{slug_version(version)}"

def derive_version_from_path(path: str) -> str:
    try:
        root = pathlib.Path(DOCS_ROOT).resolve()
        p = pathlib.Path(path).resolve()
        rel = p.relative_to(root)
        return rel.parts[0]
    except Exception:
        p = pathlib.Path(path)
        for part in p.parts[::-1]:
            if "version" in part.lower():
                return part
        return p.parent.name or "unknown"

def version_for_path(path: str) -> str:
    """Immediate folder name under DOCS_ROOT (same logic as PDFs)."""
    try:
        root = pathlib.Path(DOCS_ROOT).resolve()
        p = pathlib.Path(path).resolve()
        rel = p.relative_to(root)
        return rel.parts[0]
    except Exception:
        return pathlib.Path(path).parent.name or "Diagrams"

def doc_id_for(path: str) -> str:
    return hashlib.sha1(path.encode("utf-8")).hexdigest()[:16]

def batched(seq: Iterable, n: int):
    buf=[]
    for x in seq:
        buf.append(x)
        if len(buf) >= n:
            yield buf; buf=[]
    if buf: yield buf

#-------------- Image Helpers-----------------
def _b64_image(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")

def generate_image_caption(path: str) -> str:
    """
    Use Azure OpenAI vision chat to create a short technical caption for search.
    Keeps it concise & factual (no hallucinations).
    """
    if not AZURE_ENDPOINT or not AZURE_API_KEY or not AZURE_VISION_DEPLOYMENT:
        return pathlib.Path(path).stem.replace("_"," ").replace("-"," ").strip()

    b64 = _b64_image(path)
    url = f"{AZURE_ENDPOINT}/openai/deployments/{AZURE_VISION_DEPLOYMENT}/chat/completions?api-version={AZURE_API_VERSION}"
    payload = {
        "messages": [
            {"role": "system", "content": "You caption technical diagrams for mcube manuals. Return a single concise caption (<= 25 words). Be literal; no speculation."},
            {"role": "user", "content": [
                {"type": "text", "text": "Caption this diagram for search."},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}
            ]}
        ],
        "temperature": 0.0,
        "max_tokens": 80
    }
    try:
        r = requests.post(url, headers=HEADERS, json=payload, timeout=60)
        r.raise_for_status()
        cap = (r.json()["choices"][0]["message"]["content"] or "").strip()
        return re.sub(r"\s+", " ", cap)[:300]
    except Exception as e:
        log.warning(f"Vision caption failed for {path}: {e}")
        return pathlib.Path(path).stem.replace("_"," ").replace("-"," ").strip()

# --------------- Text extraction ---------------
def text_pymupdf(path: str, pno: int) -> str:
    with fitz.open(path) as doc:
        page = doc.load_page(pno)
        blocks = [b for b in page.get_text("blocks") if isinstance(b[4], str) and b[4].strip()]
        if blocks:
            blocks.sort(key=lambda b: (round(b[1],1), round(b[0],1)))
            return clean_text("\n".join(clean_text(b[4]) for b in blocks))
        return clean_text(page.get_text("text"))

def text_pdfminer(path: str, pno: int) -> str:
    return clean_text(pdfminer_extract_text(path, page_numbers=[pno]) or "")

def text_pdfium(path: str, pno: int) -> str:
    if not HAS_PDFIUM: return ""
    doc = pdfium.PdfDocument(path)
    page = doc.get_page(pno)
    textpage = page.get_textpage()
    s = textpage.get_text_bounded()
    textpage.close(); page.close(); doc.close()
    return clean_text(s or "")

def extract_text_best_effort(path: str, pno: int) -> str:
    candidates = [text_pymupdf(path, pno), text_pdfminer(path, pno)]
    if HAS_PDFIUM: candidates.append(text_pdfium(path, pno))
    return max(candidates, key=lambda s: len(s or ""))

# --------------- Link extraction (anchor text + URL) ---------------
def extract_page_links(path: str, pno: int) -> Tuple[List[str], List[Dict[str,str]]]:
    """
    Returns (all_urls, anchors) for the given page.
    anchors = [{"text": "...", "url": "..."}], where text is best-effort anchor text near the link bbox.
    """
    urls: List[str] = []
    anchors: List[Dict[str,str]] = []
    try:
        doc = fitz.open(path)
        page = doc.load_page(pno)
        link_annots = page.get_links() or []
        words = page.get_text("words")
        for ln in link_annots:
            uri = (ln.get("uri") or "").strip()
            if not uri or not uri.startswith(("http://","https://")):
                continue
            urls.append(uri)
            rect = fitz.Rect(ln["from"]) if ln.get("from") else None
            anchor_text = ""
            if rect and words:
                pad = 1.0
                rpad = fitz.Rect(rect.x0-pad, rect.y0-pad, rect.x1+pad, rect.y1+pad)
                near = [w[4] for w in words if rpad.intersects(fitz.Rect(w[0],w[1],w[2],w[3]))]
                if near:
                    anchor_text = " ".join(near).strip()
            anchors.append({"text": anchor_text, "url": uri})
        doc.close()
    except Exception as e:
        log.warning(f"link extract failed p{pno+1} {path}: {e}")
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
        md += "|" + "|".join([(c or "").replace("\n"," ").strip() for c in r]) + "|\n"
    return md

def tables_pdfplumber(pl_page) -> List[str]:
    out, seen = [], set()
    strategies = [
        dict(vertical_strategy="lines", horizontal_strategy="lines"),
        dict(vertical_strategy="text", horizontal_strategy="text", snap_tolerance=4, join_tolerance=4, edge_min_length=3,
             min_words_vertical=1, min_words_horizontal=1),
        dict(vertical_strategy="lines_strict", horizontal_strategy="lines_strict"),
    ]
    for st in strategies:
        try:
            found = pl_page.find_tables(table_settings=st)
            for t in found or []:
                rows = t.extract()
                if not rows or not any(any(c for c in row) for row in rows): continue
                key = tuple(tuple(row) for row in rows[:2])
                if key in seen: continue
                seen.add(key)
                out.append(to_markdown_table(rows))
        except Exception:
            pass
    return out

def tables_camelot(path: str, page_no_1based: int) -> List[str]:
    if not (USE_CAMELOT and HAS_CAMELOT): return []
    try:
        tabs = camelot.read_pdf(path, pages=str(page_no_1based), flavor="lattice")
        md=[]
        for tb in tabs:
            rows = [tb.df.columns.tolist()] + tb.df.values.tolist()
            rows = [[(c or "").strip() for c in r] for r in rows]
            if len(rows) >= 2 and any(any(cell for cell in r) for r in rows[1:]):
                md.append(to_markdown_table(rows))
        return md
    except Exception:
        return []

# --------------- Chunking & Embeddings ---------------
def chunk_text(text: str, size=CHUNK_SIZE, overlap=CHUNK_OVERLAP) -> List[str]:
    out, start, n = [], 0, len(text)
    while start < n:
        end = min(start + size, n)
        out.append(text[start:end])
        if end == n: break
        start = max(0, end - overlap)
    return [c.strip() for c in out if c.strip()]

@retry(wait=wait_exponential(min=1, max=20), stop=stop_after_attempt(6))
def embed_texts(texts: List[str]) -> List[List[float]]:
    if not AZURE_ENDPOINT or not AZURE_API_KEY or not AZURE_EMBED_DEPLOYMENT:
        raise RuntimeError("Azure OpenAI embedding config missing")
    url = f"{AZURE_ENDPOINT}/openai/deployments/{AZURE_EMBED_DEPLOYMENT}/embeddings?api-version={AZURE_API_VERSION}"
    r = requests.post(url, headers=HEADERS, json={"input": texts}, timeout=90)
    if r.status_code >= 300:
        raise RuntimeError(f"Embedding failed: {r.status_code} {r.text[:200]}")
    data = r.json()
    return [item["embedding"] for item in sorted(data["data"], key=lambda x: x["index"])]

def ensure_index(es: Elasticsearch, index_name: str, dims: int):
    mapping = {
        "settings": {"index": {"number_of_shards": 1, "number_of_replicas": 0}},
        "mappings": {
            "properties": {
                "content":     {"type": "text"},
                "section":     {"type": "text"},
                "chunk_type":  {"type": "keyword"},
                "table_title": {"type": "text"},
                "caption":     {"type": "text"},
                "vector":      {"type": "dense_vector", "dims": dims, "index": True, "similarity": "cosine"},
                "doc_id":      {"type": "keyword"},
                "chunk_id":    {"type": "keyword"},
                "path":        {"type": "keyword"},
                "filename":    {"type": "keyword"},
                "version":     {"type": "keyword"},
                "page":        {"type": "integer"},
                "links":       {"type": "text"},
                "primary_link":{"type": "text"}
            }
        }
    }
    if not es.indices.exists(index=index_name):
        es.indices.create(index=index_name, body=mapping)

def ensure_alias(es: Elasticsearch, alias: str, index_name: str):
    try:
        es.indices.update_aliases(body={"actions":[{"add":{"index":index_name,"alias":alias}}]})
    except Exception:
        pass

# --------------- Core ingest logic (PDFs) ---------------
def ingest(root: str, only: Optional[str], recreate: bool) -> Dict:
    es = Elasticsearch(ES_HOST, basic_auth=(ES_USERNAME, ES_PASSWORD), verify_certs=False)
    dims = len(embed_texts(["dimension probe"])[0])
    log.info(f"Embedding dims = {dims}")

    pdfs=[]
    for dirpath, _, files in os.walk(root):
        for f in files:
            if f.lower().endswith(".pdf"):
                full = os.path.join(dirpath, f)
                if only and only.lower() not in full.lower(): continue
                pdfs.append(full)
    if not pdfs:
        log.warning(f"No PDFs under {root} (filter={only})")
        return {"pdfs_processed": 0, "chunks_indexed": 0}

    total_chunks = 0
    pdfs_processed = 0

    for pdf_path in tqdm(sorted(pdfs, key=lambda p: p.lower()), desc="PDFs"):
        version  = derive_version_from_path(pdf_path)
        index    = index_for_version(version)
        filename = os.path.basename(pdf_path)

        if recreate and es.indices.exists(index=index):
            es.indices.delete(index=index, ignore=[400,404])

        ensure_index(es, index, dims)
        if INDEX_ALIAS: ensure_alias(es, INDEX_ALIAS, index)

        rows=[]
        with pdfplumber.open(pdf_path) as pl:
            page_count = len(pl.pages)
            if MAX_PAGES and MAX_PAGES > 0:
                page_count = min(page_count, MAX_PAGES)

            for pno in range(page_count):
                text = extract_text_best_effort(pdf_path, pno)
                tables = tables_pdfplumber(pl.pages[pno]) or tables_camelot(pdf_path, pno+1)

                all_urls, anchors = extract_page_links(pdf_path, pno)
                primary_link = next((u for u in all_urls if u.lower().endswith(".mp4")), None)

                video_lines=[]
                for a in anchors:
                    if not a.get("url"): continue
                    txt = (a.get("text") or "").strip()
                    if a["url"].lower().endswith(".mp4"):
                        if not txt:
                            txt = pathlib.Path(a["url"]).name
                        video_lines.append(f"VIDEO: {txt} -> {a['url']}")
                if video_lines:
                    text = f"{text}\n\n" + "\n".join(video_lines)

                for md in tables:
                    block = f"{filename} • {version} • page {pno+1}\n[TABLE]\n{md}"
                    rows.append({
                        "content": block, "section": "", "chunk_type": "table",
                        "table_title": None, "filename": filename, "version": version,
                        "page": pno+1, "path": str(pathlib.Path(pdf_path).resolve()),
                        "links": all_urls, "primary_link": primary_link
                    })

                prefix = f"{filename} • {version} • page {pno+1}\n"
                for ch in chunk_text(prefix + text):
                    rows.append({
                        "content": ch, "section": "", "chunk_type": "text", "table_title": None,
                        "filename": filename, "version": version, "page": pno+1,
                        "path": str(pathlib.Path(pdf_path).resolve()),
                        "links": all_urls, "primary_link": primary_link
                    })

                log.info(f"{filename} p{pno+1}: chars={len(text)} tables={len(tables)} links={len(all_urls)} primary={bool(primary_link)}")

        docid = doc_id_for(str(pathlib.Path(pdf_path).resolve()))
        for batch in batched(rows, BATCH_EMBED):
            vecs = embed_texts([r["content"] for r in batch])
            actions=[]
            for i, (r, v) in enumerate(zip(batch, vecs)):
                chunk_id = f"{docid}-{r['page']}-{i}"
                actions.append({
                    "_index": index, "_id": chunk_id, "_op_type": "index",
                    "_source": {**r, "doc_id": docid, "chunk_id": chunk_id, "vector": v}
                })
            helpers.bulk(es, actions, request_timeout=180)
            total_chunks += len(actions)

        log.info(f"Indexed: {filename} -> {index} (chunks={len(rows)})")
        pdfs_processed += 1

    return {"pdfs_processed": pdfs_processed, "chunks_indexed": total_chunks}


# --------------- Core ingest logic (Diagrams) ---------------
def ingest_diagrams(docs_root: Optional[str] = None) -> Dict:
    root = docs_root or DOCS_ROOT
    es = Elasticsearch(ES_HOST, basic_auth=(ES_USERNAME, ES_PASSWORD), verify_certs=False)
    dims = len(embed_texts(["dimension probe"])[0])

    log.info("Scanning for diagrams (*.png)...")
    image_rows = []
    for dirpath, _, files in os.walk(root):
        if pathlib.Path(dirpath).name.lower() != IMAGE_DIR_NAME.lower():
            continue
        for f in files:
            if not f.lower().endswith(".png"):
                continue
            img_path = os.path.join(dirpath, f)
            version = version_for_path(img_path)
            index   = index_for_version(version)
            filename = os.path.basename(img_path)

            ensure_index(es, index, dims)
            if INDEX_ALIAS:
                ensure_alias(es, INDEX_ALIAS, index)

            caption = generate_image_caption(img_path)
            content = f"{filename} • {version}\n[IMAGE]\n{caption}"

            vec = embed_texts([content])[0]
            docid = doc_id_for(str(pathlib.Path(img_path).resolve()))
            chunk_id = f"{docid}-img-0"

            image_rows.append({
                "_index": index, "_id": chunk_id, "_op_type": "index",
                "_source": {
                    "content": content,
                    "caption": caption,
                    "section": "",
                    "chunk_type": "image",
                    "table_title": None,
                    "filename": filename,
                    "version": version,
                    "page": None,
                    "path": str(pathlib.Path(img_path).resolve()),
                    "doc_id": docid,
                    "chunk_id": chunk_id,
                    "vector": vec
                }
            })

    if image_rows:
        helpers.bulk(es, image_rows, request_timeout=180)
        log.info(f"Indexed {len(image_rows)} diagram images.")
    else:
        log.info("No diagrams found.")

    return {"images_indexed": len(image_rows)}


# --------------- Single uploaded PDF ingest (uses ingestor logic) ---------------
def ingest_uploaded_pdf(
    pdf_path: str,
    index_name: str,
    original_filename: str,
    recreate_index: bool = False
) -> Dict:
    es = Elasticsearch(ES_HOST, basic_auth=(ES_USERNAME, ES_PASSWORD), verify_certs=False)

    dims = len(embed_texts(["dimension probe"])[0])
    log.info(f"Embedding dims = {dims}")

    filename = safe_filename(original_filename)
    version = filename
    logical_path = f"{UPLOAD_LOGICAL_PATH_PREFIX.rstrip('/')}/{filename}"

    if recreate_index and es.indices.exists(index=index_name):
        es.indices.delete(index=index_name, ignore=[400, 404])

    ensure_index(es, index_name, dims)
    if INDEX_ALIAS:
        ensure_alias(es, INDEX_ALIAS, index_name)

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
                    "source": "upload_api"
                })

            prefix = f"{filename} • {version} • page {pno + 1}\n"
            for ch in chunk_text(prefix + text):
                rows.append({
                    "content": ch, "section": "", "chunk_type": "text", "table_title": None,
                    "filename": filename, "version": version, "page": pno + 1,
                    "path": logical_path,
                    "links": all_urls, "primary_link": primary_link,
                    "source": "upload_api"
                })

            log.info(
                f"{filename} p{pno + 1}: chars={len(text)} tables={len(tables)} "
                f"links={len(all_urls)} primary={bool(primary_link)}"
            )

    docid = doc_id_for(f"{index_name}:{filename}")
    total_chunks = 0

    for batch in batched(rows, BATCH_EMBED):
        vecs = embed_texts([r["content"] for r in batch])
        actions = []
        for i, (r, v) in enumerate(zip(batch, vecs)):
            chunk_id = f"{docid}-{r['page']}-{i}"
            actions.append({
                "_index": index_name, "_id": chunk_id, "_op_type": "index",
                "_source": {**r, "doc_id": docid, "chunk_id": chunk_id, "vector": v}
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
        "pages_processed": page_count
    }


# --------------- REST API ---------------
@app.route("/api/ingest/pdf-upload", methods=["POST"])
def pdf_upload():
    pdf_file = request.files.get("file") or request.files.get("pdf")
    index_name = request.form.get("index_name", "").strip()
    recreate_index = request.form.get("recreate_index", "false").lower() == "true"

    if not pdf_file:
        return jsonify({"error": "Missing file in form-data"}), 400

    if not pdf_file.filename or pdf_file.filename.strip() == "":
        return jsonify({"error": "No file selected"}), 400

    if not pdf_file.filename.lower().endswith(".pdf"):
        return jsonify({"error": "Only PDF files are allowed"}), 400

    if not index_name:
        return jsonify({"error": "index_name is required"}), 400

    try:
        index_name = sanitize_index_name(index_name)
    except Exception as e:
        return jsonify({"error": f"Invalid index_name: {str(e)}"}), 400

    original_filename = safe_filename(pdf_file.filename)
    temp_file_path = None

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            pdf_file.save(tmp.name)
            temp_file_path = tmp.name

        result = ingest_uploaded_pdf(
            pdf_path=temp_file_path,
            index_name=index_name,
            original_filename=original_filename,
            recreate_index=recreate_index
        )

        return jsonify(result), 200

    except Exception as e:
        log.exception("PDF ingestion failed")
        return jsonify({"error": f"Ingestion failed: {str(e)}"}), 500

    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except Exception:
                pass


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    # CLI mode when --root / --only / --recreate-index args are given;
    # REST server mode when --serve is passed (or no recognized CLI args).
    if len(sys.argv) > 1 and sys.argv[1] != "--serve":
        ap = argparse.ArgumentParser()
        ap.add_argument("--root", default=DOCS_ROOT)
        ap.add_argument("--only", default=None)
        ap.add_argument("--recreate-index", action="store_true")
        args = ap.parse_args()
        result = ingest(args.root, args.only, args.recreate_index)
        # also run diagrams after PDFs (original behaviour)
        diag_result = ingest_diagrams(args.root)
        log.info(f"Done: {result}, diagrams: {diag_result}")
    else:
        port = int(os.getenv("INGESTOR_PORT", "5002"))
        log.info(f"Starting ingestor REST service on port {port}")
        app.run(host="0.0.0.0", port=port, debug=False)
