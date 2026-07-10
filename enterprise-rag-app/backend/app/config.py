"""Central configuration, loaded from environment variables / .env."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(BACKEND_ROOT / ".env"), extra="ignore")

    openai_api_key: str = ""
    embed_model: str = "text-embedding-3-small"
    chat_model: str = "gpt-4o-mini"

    chroma_persist_dir: str = "./chroma_data"
    cors_origin: str = "http://localhost:5173,http://127.0.0.1:5173"

    top_k_per_collection: int = 3
    chunk_size_words: int = 180
    chunk_overlap_words: int = 30

    data_dir: str = "./data"

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origin.split(",") if origin.strip()]

    @property
    def chroma_path(self) -> Path:
        path = Path(self.chroma_persist_dir)
        if not path.is_absolute():
            path = BACKEND_ROOT / path
        return path

    @property
    def manuals_dir(self) -> Path:
        base = Path(self.data_dir)
        if not base.is_absolute():
            base = BACKEND_ROOT / base
        return base / "manuals"

    @property
    def tickets_file(self) -> Path:
        base = Path(self.data_dir)
        if not base.is_absolute():
            base = BACKEND_ROOT / base
        return base / "tickets" / "tickets.json"


settings = Settings()
