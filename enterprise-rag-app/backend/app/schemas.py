"""Pydantic request/response models — this is the API contract the React frontend codes against."""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    chunks_indexed: int
    tables_indexed: int = 0
    images_indexed: int = 0


class IngestResponse(BaseModel):
    documents_indexed: int
    chunks_indexed: int
    tables_indexed: int = 0
    images_captioned: int = 0


class DocumentInfo(BaseModel):
    name: str
    chunk_count: int


class UploadResponse(BaseModel):
    filename: str
    message: str


class ChatStartResponse(BaseModel):
    session_id: str


class ChatSendRequest(BaseModel):
    session_id: str
    message: str


class Source(BaseModel):
    label: str  # source filename
    snippet: str
    score: float
    content_type: str = "text"  # "text" | "table" | "image"
    page: int | None = None
    image_id: str | None = None  # if set, the actual image is at GET /images/{image_id}


class ChatSendResponse(BaseModel):
    answer: str
    sources: list[Source]


class ChatMessage(BaseModel):
    role: str
    content: str
    sources: list[Source] = []


class ChatHistoryResponse(BaseModel):
    session_id: str
    messages: list[ChatMessage]
