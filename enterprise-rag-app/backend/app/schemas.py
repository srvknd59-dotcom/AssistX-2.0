"""Pydantic request/response models — this is the API contract the React frontend codes against."""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    manuals_indexed: int
    tickets_indexed: int


class IngestResponse(BaseModel):
    manuals_indexed: int
    manual_chunks: int
    tickets_indexed: int


class DocumentInfo(BaseModel):
    name: str
    type: str  # "manual" | "ticket"
    chunk_count: int


class ChatStartResponse(BaseModel):
    session_id: str


class ChatSendRequest(BaseModel):
    session_id: str
    message: str


class Source(BaseModel):
    type: str  # "manual" | "ticket"
    label: str  # filename or "Ticket #123"
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
