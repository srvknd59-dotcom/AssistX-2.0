"""FastAPI entry point — the API the React frontend talks to.

Run with: uvicorn app.main:app --reload --port 8000
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.rag.pipeline import RagPipeline, new_session_id
from app.schemas import (
    ChatHistoryResponse,
    ChatMessage,
    ChatSendRequest,
    ChatSendResponse,
    ChatStartResponse,
    DocumentInfo,
    HealthResponse,
    IngestResponse,
    Source,
)

app = FastAPI(title="Enterprise RAG API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

pipeline = RagPipeline()

# In-memory session store. This is a teaching project: the production
# chat_service.py in this repo persists sessions/history to MariaDB instead.
_sessions: dict[str, list[dict]] = {}


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    counts = pipeline.counts()
    return HealthResponse(status="ok", **counts)


@app.post("/ingest", response_model=IngestResponse)
def ingest() -> IngestResponse:
    stats = pipeline.ingest_all()
    return IngestResponse(**stats)


@app.get("/documents", response_model=list[DocumentInfo])
def documents() -> list[DocumentInfo]:
    manuals = pipeline.store._collection("manuals").get()
    tickets = pipeline.store._collection("tickets").get()

    manual_counts: dict[str, int] = {}
    for meta in manuals["metadatas"]:
        manual_counts[meta["source"]] = manual_counts.get(meta["source"], 0) + 1

    docs = [DocumentInfo(name=name, type="manual", chunk_count=n) for name, n in manual_counts.items()]
    docs.append(DocumentInfo(name="tickets.json", type="ticket", chunk_count=len(tickets["ids"])))
    return docs


@app.post("/chat/start", response_model=ChatStartResponse)
def chat_start() -> ChatStartResponse:
    session_id = new_session_id()
    _sessions[session_id] = []
    return ChatStartResponse(session_id=session_id)


@app.post("/chat/send", response_model=ChatSendResponse)
def chat_send(payload: ChatSendRequest) -> ChatSendResponse:
    if payload.session_id not in _sessions:
        raise HTTPException(status_code=404, detail="Unknown session_id. Call /chat/start first.")

    history = _sessions[payload.session_id]
    result = pipeline.answer(payload.message, history=history)

    sources = [Source(**s) for s in result["sources"]]
    history.append({"role": "user", "content": payload.message})
    history.append({"role": "assistant", "content": result["answer"]})

    return ChatSendResponse(answer=result["answer"], sources=sources)


@app.get("/chat/{session_id}/history", response_model=ChatHistoryResponse)
def chat_history(session_id: str) -> ChatHistoryResponse:
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail="Unknown session_id.")
    messages = [ChatMessage(role=turn["role"], content=turn["content"]) for turn in _sessions[session_id]]
    return ChatHistoryResponse(session_id=session_id, messages=messages)
