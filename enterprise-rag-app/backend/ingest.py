"""Command-line ingestion: builds the Elasticsearch index without needing the
API server running.

Usage:
    python ingest.py                      # ingest backend/data/documents
    python ingest.py --root C:\\path\\to\\docs   # ingest a different folder
"""

import argparse
from pathlib import Path

from app.config import settings
from app.rag.pipeline import RagPipeline

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=str, default=None, help="Folder to ingest from (default: data/documents)")
    args = parser.parse_args()

    root = Path(args.root) if args.root else None

    pipeline = RagPipeline()
    stats = pipeline.ingest_documents(root)

    print(f"Elasticsearch index  : {settings.es_index_prefix}_documents")
    print(f"Documents read from  : {root or settings.documents_dir}")
    print(f"Indexed {stats['documents_indexed']} document(s) into {stats['chunks_indexed']} chunk(s).")
