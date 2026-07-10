# Enterprise RAG App — FastAPI + Chroma + React

A step up from [`rag-ui-tutorial/`](../rag-ui-tutorial): the same RAG idea, but with
a **real, on-disk vector database** (Chroma) instead of a NumPy array, a **typed
REST API** (FastAPI) instead of one Streamlit script, and a **production-shaped
React + TypeScript frontend** instead of an auto-generated UI. Still no Docker,
no external database server, and everything runs locally with two commands.

This project's whole job is the same core loop as the production
`chat_service.py`/`ingestor.py` in the repo root: **ingest documents into a
vector index, then search/chat over them with grounded, cited answers.**
There's no ticketing system or multi-source retrieval here — one document
collection, ingested from disk or uploaded through the UI, searched and
answered against. Simple on purpose.

**For the day-by-day build plan, see [`ONE_DAY_PLAN.md`](./ONE_DAY_PLAN.md).**
It assumes this code already exists (it does — it's in this folder) and walks
through *understanding, running, and extending it* in roughly 8 hours on a
Windows machine.

## Architecture

```
┌────────────────────┐        HTTP/JSON         ┌─────────────────────────────┐
│   React frontend    │ ───────────────────────▶ │        FastAPI backend       │
│  (Vite + TS, :5173) │ ◀─────────────────────── │           (:8000)            │
└────────────────────┘                            │                              │
                                                    │  ┌────────────────────────┐ │
                                                    │  │   RagPipeline           │ │
                                                    │  │  - chunking             │ │
                                                    │  │  - OpenAI embeddings    │ │
                                                    │  │  - retrieve + generate  │ │
                                                    │  └───────────┬────────────┘ │
                                                    │              │              │
                                                    │   ┌──────────▼───────────┐  │
                                                    │   │   Chroma (on disk)    │  │
                                                    │   │  "documents"           │  │
                                                    │   │  collection            │  │
                                                    │   └────────────────────────┘  │
                                                    └─────────────────────────────┘
                                                                  │
                                                          OpenAI API (embeddings + chat)
```

Documents are ingested one of two ways: dropped into `backend/data/documents/`
before running `/ingest`, or uploaded straight from the UI's sidebar (which
saves the file to that same folder and lets you rebuild the index with one
click) — mirroring what `ingestor.py` does in the production app, just
against Chroma instead of Elasticsearch and without the manuals/tickets
split.

## Why Chroma instead of the NumPy store from rag-ui-tutorial?

| | rag-ui-tutorial | This project |
| --- | --- | --- |
| Storage | NumPy array in a `.npy` file | Chroma — an embedded vector database, HNSW index, persisted to `chroma_data/` |
| Query | Manual cosine similarity in Python | `collection.query()` — the same call pattern real vector DBs (Pinecone, Qdrant, Weaviate) use |
| Adding documents | Edit files on disk, rebuild | Same, **plus** upload a file straight from the UI |
| Metadata filtering | None | Supported natively by Chroma (not used here, but this is where you'd add it) |
| Scale | Fine for dozens of chunks | Fine for tens of thousands of chunks on a laptop, embedded, no server |

Chroma still requires **no Docker and no separate server process** — it's a
Python library that reads/writes a folder on disk, which is why it fits the
"nothing in Docker, runs on her Windows machine" requirement while still
being architecturally the real thing.

## Project structure

```
enterprise-rag-app/
  backend/
    app/
      main.py            FastAPI routes (chat, ingest, upload, documents, health)
      config.py           Settings loaded from .env
      schemas.py           Request/response models (the API contract)
      rag/
        chunking.py         Load + split documents
        embeddings.py         OpenAI embedding calls
        vector_store.py        Chroma wrapper (real vector DB)
        pipeline.py              Ties it together: ingest + retrieve + generate
    data/
      documents/          Sample docs to start with (reused from rag-ui-tutorial);
                           uploaded files land here too
    ingest.py             CLI: build the index without starting the server
    setup.ps1 / run.ps1   Windows one-command setup / start
  frontend/
    src/
      api/client.ts       Typed API client (axios)
      hooks/useChat.ts     Chat state management
      components/         Header, Sidebar (list + upload), ChatWindow, MessageBubble, SourcesPanel, ChatInput
      App.tsx
    setup.ps1 / run.ps1   Windows one-command setup / start
  start-all.ps1           Launches backend + frontend together
```

## Quick start (Windows)

Full detail is in `ONE_DAY_PLAN.md`; the short version:

```powershell
cd enterprise-rag-app\backend
.\setup.ps1        # creates venv, installs deps, creates .env — edit .env and add your OPENAI_API_KEY
.\run.ps1           # starts the API on http://localhost:8000

# in a second terminal
cd enterprise-rag-app\frontend
.\setup.ps1
.\run.ps1           # starts the app on http://localhost:5173
```

Or from the repo root, after running both `setup.ps1` scripts once:

```powershell
cd enterprise-rag-app
.\start-all.ps1
```

Then open http://localhost:5173, click **Rebuild index** once (builds the
Chroma vector database from `backend/data/documents/`), and start asking
questions. Use the sidebar's file picker to upload your own `.txt`, `.md`,
or `.pdf` and click **Rebuild index** again to include it.

## API reference

Interactive docs are auto-generated by FastAPI at `http://localhost:8000/docs`
once the backend is running. Summary:

| Method & path | Purpose |
| --- | --- |
| `GET /health` | Service status + how many chunks are indexed |
| `POST /ingest` | (Re)build the Chroma index from `data/documents/` |
| `POST /documents/upload` | Upload a `.txt`/`.md`/`.pdf` file into `data/documents/` |
| `GET /documents` | List indexed documents and their chunk counts |
| `POST /chat/start` | Create a chat session, returns a `session_id` |
| `POST /chat/send` | Send a message; returns a grounded answer + cited sources |
| `GET /chat/{session_id}/history` | Replay a session's messages |

## Extending this project

- **Add metadata filtering**: Chroma's `query()` accepts a `where={...}` filter —
  e.g. filter by upload date or a category you attach at ingest time. See
  `vector_store.py`.
- **Persist chat history**: swap the in-memory `_sessions` dict in `main.py` for
  a real database, the way `chat_service.py` uses MariaDB.
- **Auth**: add an API key check like `chat_service.py`'s
  `X-AssistX-Internal-Key` middleware before exposing this beyond localhost.
- **Multiple collections again**: if a second document type shows up later
  (e.g. meeting notes vs. policies), `ChromaVectorStore` already supports
  named collections — `pipeline.py` just needs a second `ingest_*`/`retrieve`
  path, the same shape this project had before it was simplified down to one.
