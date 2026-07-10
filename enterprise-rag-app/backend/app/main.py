"""FastAPI entry point — the API the React frontend talks to.

Run with: uvicorn app.main:app --reload --port 8000
"""

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.rag.chunking import SUPPORTED_EXTENSIONS
from app.rag.pipeline import COLLECTION_NAME, RagPipeline, new_session_id
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
    UploadResponse,
)

app = FastAPI(title="RAG Document Search API", version="1.0.0")

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
    return HealthResponse(status="ok", **pipeline.counts())


@app.post("/ingest", response_model=IngestResponse)
def ingest() -> IngestResponse:
    stats = pipeline.ingest_documents()
    return IngestResponse(**stats)


@app.post("/documents/upload", response_model=UploadResponse)
async def upload_document(file: UploadFile) -> UploadResponse:
    suffix = "." + file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if suffix not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{suffix}'. Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}",
        )

    settings.documents_dir.mkdir(parents=True, exist_ok=True)
    target = settings.documents_dir / file.filename
    target.write_bytes(await file.read())

    return UploadResponse(filename=file.filename, message="Uploaded. Call /ingest to add it to the index.")


@app.get("/documents", response_model=list[DocumentInfo])
def documents() -> list[DocumentInfo]:
    stored = pipeline.store._collection(COLLECTION_NAME).get()

    counts: dict[str, int] = {}
    for meta in stored["metadatas"]:
        counts[meta["source"]] = counts.get(meta["source"], 0) + 1

    return [DocumentInfo(name=name, chunk_count=n) for name, n in counts.items()]


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
