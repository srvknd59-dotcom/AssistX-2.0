# ingest_service.py - lightweight REST-only PDF ingestion endpoint.
#
# This is the entrypoint for Dockerfile.ingest. It shares all extraction,
# chunking, and embedding logic with ingestor.py via pdf_ingest.py and
# llm_providers.py rather than duplicating it.
import os
import logging
import tempfile

from dotenv import load_dotenv
from flask import Flask, request, jsonify

import llm_providers
import pdf_ingest as pi

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("ingest_service")

app = Flask(__name__)


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
    app.run(host="0.0.0.0", port=5001, debug=False)
