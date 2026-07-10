"""Command-line ingestion: builds the Chroma vector database from data/documents
without needing the API server running.

Usage:  python ingest.py
"""

from app.rag.pipeline import RagPipeline

if __name__ == "__main__":
    pipeline = RagPipeline()
    stats = pipeline.ingest_documents()
    print(f"Indexed {stats['documents_indexed']} document(s) into {stats['chunks_indexed']} chunk(s).")
