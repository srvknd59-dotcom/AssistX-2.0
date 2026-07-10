"""Pydantic request/response models — this is the API contract the React frontend codes against."""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    chunks_indexed: int


class IngestResponse(BaseModel):
    documents_indexed: int
    chunks_indexed: int


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
