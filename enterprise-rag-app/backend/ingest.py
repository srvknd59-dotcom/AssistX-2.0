"""Command-line ingestion: builds the Chroma vector database from data/manuals
and data/tickets without needing the API server running.

Usage:  python ingest.py
"""

from app.rag.pipeline import RagPipeline

if __name__ == "__main__":
    pipeline = RagPipeline()
    stats = pipeline.ingest_all()
    print(f"Indexed {stats['manuals_indexed']} manual(s) into {stats['manual_chunks']} chunk(s).")
    print(f"Indexed {stats['tickets_indexed']} ticket(s).")
