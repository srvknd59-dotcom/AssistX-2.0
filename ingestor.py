# ingestor.py - CLI + REST ingestion service (mirrors ingest_service.py endpoints)
#
# Shared extraction/chunking/indexing logic lives in pdf_ingest.py; provider-agnostic
# chat/embedding/vision calls live in llm_providers.py. This file only owns the
# version-aware index naming used by the CLI ingest paths (ingest / ingest_diagrams).
import os
import re
import pathlib
import argparse
import logging
import sys
import tempfile
from typing import Dict, Optional

import pdfplumber
from elasticsearch import helpers
from dotenv import load_dotenv
from tqdm import tqdm
from flask import Flask, request, jsonify

import llm_providers
import pdf_ingest as pi

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("ingest")

app = Flask(__name__)

# --------------- Config (CLI-specific: index naming/versioning) ---------------
ES_INDEX_PREFIX = os.getenv("ES_INDEX_PREFIX", "").strip()
ES_INDEX_SINGLE = os.getenv("ES_INDEX", "").strip()
ES_ALIAS        = os.getenv("ES_ALIAS", "").strip()


def slug_version(version: str) -> str:
    v = version.strip().lower().replace("version", "v")
    v = re.sub(r"[^a-z0-9]+", "-", v).replace(".", "_").strip("-")
    return v or "unknown"


def _effective_prefix_and_alias() -> (str, Optional[str]):
    if ES_INDEX_PREFIX:
        return ES_INDEX_PREFIX, (ES_ALIAS or f"{ES_INDEX_PREFIX}_all")
    if ES_INDEX_SINGLE:
        return ES_INDEX_SINGLE, (ES_ALIAS or f"{ES_INDEX_SINGLE}_all")
    return "mcube_manuals", "mcube_manuals_all"


INDEX_PREFIX, INDEX_ALIAS = _effective_prefix_and_alias()


def index_for_version(version: str) -> str:
    return f"{INDEX_PREFIX}-{slug_version(version)}"


def derive_version_from_path(path: str) -> str:
    try:
        root = pathlib.Path(pi.DOCS_ROOT).resolve()
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
        root = pathlib.Path(pi.DOCS_ROOT).resolve()
        p = pathlib.Path(path).resolve()
        rel = p.relative_to(root)
        return rel.parts[0]
    except Exception:
        return pathlib.Path(path).parent.name or "Diagrams"


# --------------- Core ingest logic (PDFs) ---------------
def ingest(root: str, only: Optional[str], recreate: bool) -> Dict:
    es = pi.new_es_client()
    dims = len(llm_providers.embed_texts(["dimension probe"])[0][0])
    log.info(f"Embedding dims = {dims}")

    pdfs = []
    for dirpath, _, files in os.walk(root):
        for f in files:
            if f.lower().endswith(".pdf"):
                full = os.path.join(dirpath, f)
                if only and only.lower() not in full.lower():
                    continue
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
            es.indices.delete(index=index, ignore=[400, 404])

        pi.ensure_index(es, index, dims)
        if INDEX_ALIAS:
            pi.ensure_alias(es, INDEX_ALIAS, index)

        rows = []
        with pdfplumber.open(pdf_path) as pl:
            page_count = len(pl.pages)
            if pi.MAX_PAGES and pi.MAX_PAGES > 0:
                page_count = min(page_count, pi.MAX_PAGES)

            for pno in range(page_count):
                text = pi.extract_text_best_effort(pdf_path, pno)
                tables = pi.tables_pdfplumber(pl.pages[pno]) or pi.tables_camelot(pdf_path, pno + 1)

                all_urls, anchors = pi.extract_page_links(pdf_path, pno)
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
                        "page": pno + 1, "path": str(pathlib.Path(pdf_path).resolve()),
                        "links": all_urls, "primary_link": primary_link,
                    })

                prefix = f"{filename} • {version} • page {pno + 1}\n"
                for ch in pi.chunk_text(prefix + text):
                    rows.append({
                        "content": ch, "section": "", "chunk_type": "text", "table_title": None,
                        "filename": filename, "version": version, "page": pno + 1,
                        "path": str(pathlib.Path(pdf_path).resolve()),
                        "links": all_urls, "primary_link": primary_link,
                    })

                log.info(f"{filename} p{pno + 1}: chars={len(text)} tables={len(tables)} links={len(all_urls)} primary={bool(primary_link)}")

        docid = pi.doc_id_for(str(pathlib.Path(pdf_path).resolve()))
        for batch in pi.batched(rows, pi.BATCH_EMBED):
            vecs, _usage = llm_providers.embed_texts([r["content"] for r in batch])
            actions = []
            for i, (r, v) in enumerate(zip(batch, vecs)):
                chunk_id = f"{docid}-{r['page']}-{i}"
                actions.append({
                    "_index": index, "_id": chunk_id, "_op_type": "index",
                    "_source": {**r, "doc_id": docid, "chunk_id": chunk_id, "vector": v},
                })
            helpers.bulk(es, actions, request_timeout=180)
            total_chunks += len(actions)

        log.info(f"Indexed: {filename} -> {index} (chunks={len(rows)})")
        pdfs_processed += 1

    return {"pdfs_processed": pdfs_processed, "chunks_indexed": total_chunks}


# --------------- Core ingest logic (Diagrams) ---------------
def ingest_diagrams(docs_root: Optional[str] = None) -> Dict:
    root = docs_root or pi.DOCS_ROOT
    es = pi.new_es_client()
    dims = len(llm_providers.embed_texts(["dimension probe"])[0][0])

    log.info("Scanning for diagrams (*.png)...")
    image_rows = []
    for dirpath, _, files in os.walk(root):
        if pathlib.Path(dirpath).name.lower() != pi.IMAGE_DIR_NAME.lower():
            continue
        for f in files:
            if not f.lower().endswith(".png"):
                continue
            img_path = os.path.join(dirpath, f)
            version = version_for_path(img_path)
            index   = index_for_version(version)
            filename = os.path.basename(img_path)

            pi.ensure_index(es, index, dims)
            if INDEX_ALIAS:
                pi.ensure_alias(es, INDEX_ALIAS, index)

            caption = pi.generate_image_caption(img_path)
            content = f"{filename} • {version}\n[IMAGE]\n{caption}"

            vecs, _usage = llm_providers.embed_texts([content])
            docid = pi.doc_id_for(str(pathlib.Path(img_path).resolve()))
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
                    "vector": vecs[0],
                },
            })

    if image_rows:
        helpers.bulk(es, image_rows, request_timeout=180)
        log.info(f"Indexed {len(image_rows)} diagram images.")
    else:
        log.info("No diagrams found.")

    return {"images_indexed": len(image_rows)}


# --------------- REST API (single uploaded PDF, uses pdf_ingest logic) ---------------
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
        index_name = pi.sanitize_index_name(index_name)
    except Exception as e:
        return jsonify({"error": f"Invalid index_name: {str(e)}"}), 400

    original_filename = pi.safe_filename(pdf_file.filename)
    temp_file_path = None

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            pdf_file.save(tmp.name)
            temp_file_path = tmp.name

        result = pi.ingest_uploaded_pdf(
            pdf_path=temp_file_path,
            index_name=index_name,
            original_filename=original_filename,
            recreate_index=recreate_index,
            index_alias=INDEX_ALIAS or None,
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
    return jsonify({
        "status": "ok",
        "llm_provider": llm_providers.LLM_PROVIDER,
        "embed_provider": llm_providers.EMBED_PROVIDER,
    }), 200


if __name__ == "__main__":
    # CLI mode when --root / --only / --recreate-index args are given;
    # REST server mode when --serve is passed (or no recognized CLI args).
    if len(sys.argv) > 1 and sys.argv[1] != "--serve":
        ap = argparse.ArgumentParser()
        ap.add_argument("--root", default=pi.DOCS_ROOT)
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
