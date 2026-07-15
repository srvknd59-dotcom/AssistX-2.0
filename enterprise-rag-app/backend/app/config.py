"""Central configuration, loaded from environment variables / .env."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(BACKEND_ROOT / ".env"), extra="ignore")

    openai_api_key: str = ""
    embed_model: str = "text-embedding-3-small"
    embed_dims: int = 1536  # must match EMBED_MODEL's output size (3-small=1536, 3-large=3072)
    chat_model: str = "gpt-4o-mini"

    # Elasticsearch is the vector store - the same engine the production
    # chat_service.py/ingestor.py in this repo use. See
    # backend/README_ELASTICSEARCH.md for local Windows setup.
    es_url: str = "http://localhost:9200"
    es_index_prefix: str = "rag"
    es_username: str = ""
    es_password: str = ""

    cors_origin: str = "http://localhost:5173,http://127.0.0.1:5173"

    top_k: int = 4
    chunk_size_words: int = 180
    chunk_overlap_words: int = 30

    # Vision captioning for images embedded in ingested PDFs (chat_model does
    # the captioning - gpt-4o-mini and other current OpenAI chat models
    # support vision). Each image costs one extra API call during ingestion,
    # so it's capped per document and can be turned off entirely.
    caption_images: bool = True
    max_images_per_document: int = 20

    data_dir: str = "./data"

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origin.split(",") if origin.strip()]

    @property
    def documents_dir(self) -> Path:
        base = Path(self.data_dir)
        if not base.is_absolute():
            base = BACKEND_ROOT / base
        return base / "documents"

    @property
    def image_cache_dir(self) -> Path:
        base = Path(self.data_dir)
        if not base.is_absolute():
            base = BACKEND_ROOT / base
        return base / "image_cache"


settings = Settings()
