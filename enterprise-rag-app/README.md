# Enterprise RAG App — FastAPI + Chroma/Elasticsearch + React

A step up from [`rag-ui-tutorial/`](../rag-ui-tutorial): the same RAG idea, but with
a **real vector database** — Chroma by default, or Elasticsearch — instead of a
NumPy array, a **typed REST API** (FastAPI) instead of one Streamlit script,
and a **production-shaped React + TypeScript frontend** instead of an
auto-generated UI. The vector store is swappable with one setting
(`VECTOR_DB_BACKEND` in `.env`); everything else — API, pipeline, frontend —
is identical either way. No Docker required for either backend.

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

**Running a training session for someone else?** See
[`TRAINER_GUIDE.md`](./TRAINER_GUIDE.md) — how to prepare, open, and run the
session, using Elasticsearch as the vector database with Chroma as a
fallback if the Elasticsearch install has trouble live.

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
                                                    │   │  Chroma  or           │  │
                                                    │   │  Elasticsearch         │  │
                                                    │   │  "documents" index     │  │
                                                    │   └────────────────────────┘  │
                                                    └─────────────────────────────┘
                                                                  │
                                                          OpenAI API (embeddings + chat)
```

`VECTOR_DB_BACKEND=chroma` (default) uses an embedded, no-server database.
`VECTOR_DB_BACKEND=elasticsearch` uses a real Elasticsearch server you run
locally — see [`backend/README_ELASTICSEARCH.md`](./backend/README_ELASTICSEARCH.md)
for Windows setup. Both implement the exact same interface
(`app/rag/vector_store.py` vs. `app/rag/vector_store_elasticsearch.py`), so
`pipeline.py`, `main.py`, and the whole frontend don't change at all based
on which one is active.

Documents are ingested one of two ways: dropped into `backend/data/documents/`
before running `/ingest`, or uploaded straight from the UI's sidebar (which
saves the file to that same folder and lets you rebuild the index with one
click) — mirroring what `ingestor.py` does in the production app, just
against Chroma instead of Elasticsearch and without the manuals/tickets
split.

## Choosing a vector store: NumPy, Chroma, or Elasticsearch?

| | rag-ui-tutorial | This project (Chroma) | This project (Elasticsearch) |
| --- | --- | --- | --- |
| Storage | NumPy array in a `.npy` file | Embedded vector DB, HNSW index, `chroma_data/` folder | A separate ES server process, `rag_documents` index |
| Setup | None | None — just a Python import | Download + unzip + run `elasticsearch.bat`, disable security for local dev |
| Query | Manual cosine similarity in Python | `collection.query()` | `knn` search on a `dense_vector` field |
| Matches production repo? | No | Conceptually (same idea) | Yes — literally the same engine `ingestor.py`/`chat_service.py` use |
| Scale | Dozens of chunks | Tens of thousands, one laptop | Same as Chroma at this size; the real answer if you outgrow one machine |
| Operational overhead | None | None | A service to start, stop, and troubleshoot |

Both project backends still require **no Docker** — Chroma is a Python
library, Elasticsearch is a downloaded ZIP you run directly. Pick Chroma for
the least friction, Elasticsearch if the point of the exercise is to mirror
the production app as closely as possible. See
[`backend/README_ELASTICSEARCH.md`](./backend/README_ELASTICSEARCH.md) to
switch.

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
        vector_store_elasticsearch.py  Elasticsearch wrapper (same interface)
        pipeline.py              Ties it together: ingest + retrieve + generate
    data/
      documents/          Sample docs to start with (reused from rag-ui-tutorial);
                           uploaded files land here too
    ingest.py             CLI: build the index without starting the server
    setup.ps1 / run.ps1   Windows one-command setup / start
    README_ELASTICSEARCH.md  How to install + switch to the Elasticsearch backend
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
| `POST /ingest` | (Re)build the vector index from `data/documents/` (Chroma or Elasticsearch, per `.env`) |
| `POST /documents/upload` | Upload a `.txt`/`.md`/`.pdf` file into `data/documents/` |
| `GET /documents` | List indexed documents and their chunk counts |
| `POST /chat/start` | Create a chat session, returns a `session_id` |
| `POST /chat/send` | Send a message; returns a grounded answer + cited sources |
| `GET /chat/{session_id}/history` | Replay a session's messages |

## Extending this project

- **Add metadata filtering**: both `query()` implementations can take a
  filter — Chroma's `where={...}`, Elasticsearch's `knn.filter` — e.g. filter
  by upload date or a category you attach at ingest time.
- **Persist chat history**: swap the in-memory `_sessions` dict in `main.py` for
  a real database, the way `chat_service.py` uses MariaDB.
- **Auth**: add an API key check like `chat_service.py`'s
  `X-AssistX-Internal-Key` middleware before exposing this beyond localhost.
- **Multiple collections again**: if a second document type shows up later
  (e.g. meeting notes vs. policies), both vector store classes already
  support named collections/indices — `pipeline.py` just needs a second
  `ingest_*`/`retrieve` path, the same shape this project had before it was
  simplified down to one.
- **Hybrid search / BM25**: this is the biggest gap versus the production
  app. Elasticsearch already stores a plain `text` field alongside the
  vector — adding a combined BM25 + kNN query in
  `vector_store_elasticsearch.py`'s `query()` is the natural next step if
  you want to see hybrid retrieval, not just vector similarity.
