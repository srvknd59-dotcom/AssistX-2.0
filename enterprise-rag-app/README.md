# Enterprise RAG App — FastAPI + Elasticsearch + React

A step up from [`rag-ui-tutorial/`](../rag-ui-tutorial): the same RAG idea, but with
a **real vector database** (Elasticsearch — the same engine the production
`chat_service.py`/`ingestor.py` in this repo run against) instead of a NumPy
array, a **typed REST API** (FastAPI) instead of one Streamlit script, and a
**production-shaped React + TypeScript frontend** instead of an
auto-generated UI. No Docker required — Elasticsearch runs as a local
Windows process you start yourself.

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
session.

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
                                                    │   │    Elasticsearch       │  │
                                                    │   │  "documents" index     │  │
                                                    │   │  dense_vector + kNN    │  │
                                                    │   └────────────────────────┘  │
                                                    └─────────────────────────────┘
                                                                  │
                                                          OpenAI API (embeddings + chat)
```

Elasticsearch is a separate server process — it must be running and
reachable (`ES_URL` in `.env`) before the backend starts. See
[`backend/README_ELASTICSEARCH.md`](./backend/README_ELASTICSEARCH.md) for
Windows setup (no Docker: download a ZIP, run a `.bat` file).

Documents are ingested one of two ways: dropped into `backend/data/documents/`
before running `/ingest`, or uploaded straight from the UI's sidebar (which
saves the file to that same folder and lets you rebuild the index with one
click) — mirroring what `ingestor.py` does in the production app.

## PDF tables and images

`.pdf` ingestion isn't plain-text-only. `app/rag/chunking.py` uses
`pdfplumber` to detect tables per page and serializes each one to a
Markdown table — kept as one atomic chunk (never split mid-row), so it
embeds and retrieves as a structured table instead of jumbled inline text,
and renders as a real `<table>` both in the chat answer and in the Sources
panel. Embedded images are extracted with `pypdf` and described by a
vision-capable model (`CHAT_MODEL` — e.g. `gpt-4o-mini`) the same way the
production `ingestor.py` captions diagrams; the caption becomes its own
searchable chunk. Sources are tagged `content_type: text | table | image`
plus a `page` number, which the UI shows as a badge on each citation.

This costs one extra OpenAI call per image during ingestion. Tune it in
`.env`:

```
CAPTION_IMAGES=true          # set false to skip image captioning entirely
MAX_IMAGES_PER_DOCUMENT=20   # cap per document, in case a PDF has many images
```

Decorative images (logos, icons, dividers) are filtered automatically — the
vision model is asked to reply `DECORATIVE` for those, and they're skipped
rather than indexed as noise.

## Compared to rag-ui-tutorial's NumPy store

| | rag-ui-tutorial | This project |
| --- | --- | --- |
| Storage | NumPy array in a `.npy` file | Elasticsearch, a separate server, `rag_documents` index |
| Setup | None | Download + unzip + run `elasticsearch.bat`, disable security for local dev |
| Query | Manual cosine similarity in Python | `knn` search on a `dense_vector` field |
| Matches production repo? | No | Yes — literally the same engine `ingestor.py`/`chat_service.py` use |
| Scale | Dozens of chunks | Tens of thousands of chunks and up |
| Operational overhead | None | A service to start, stop, and troubleshoot |

Still **no Docker** — Elasticsearch is a downloaded ZIP you run directly, not
a container.

## Project structure

```
enterprise-rag-app/
  backend/
    app/
      main.py            FastAPI routes (chat, ingest, upload, documents, health)
      config.py           Settings loaded from .env
      schemas.py           Request/response models (the API contract)
      rag/
        chunking.py         Load + split documents; PDF tables (pdfplumber) + images (pypdf)
        embeddings.py         OpenAI embedding calls + vision image captioning
        vector_store.py        Elasticsearch wrapper (dense_vector + kNN)
        pipeline.py              Ties it together: ingest + retrieve + generate
    data/
      documents/          Sample docs to start with (reused from rag-ui-tutorial);
                           uploaded files land here too
    ingest.py             CLI: build the index without starting the server (supports --root)
    run_server.py          Starts the API from an editor's Run/Build button (no terminal needed)
    setup.ps1 / run.ps1   Windows one-command setup / start
    README_ELASTICSEARCH.md  Elasticsearch install steps for Windows
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

1. Install and start Elasticsearch — see [`backend/README_ELASTICSEARCH.md`](./backend/README_ELASTICSEARCH.md)
2. Then:

```powershell
cd enterprise-rag-app\backend
.\setup.ps1        # creates venv, installs deps, creates .env — edit .env and add your OPENAI_API_KEY + ES_URL
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
Elasticsearch index from `backend/data/documents/`), and start asking
questions. Use the sidebar's file picker to upload your own `.txt`, `.md`,
or `.pdf` and click **Rebuild index** again to include it.

## API reference

Interactive docs are auto-generated by FastAPI at `http://localhost:8000/docs`
once the backend is running. Summary:

| Method & path | Purpose |
| --- | --- |
| `GET /health` | Service status + how many chunks are indexed |
| `POST /ingest` | (Re)build the Elasticsearch index from `data/documents/` — extracts text, tables, and captioned images from PDFs |
| `POST /documents/upload` | Upload a `.txt`/`.md`/`.pdf` file into `data/documents/` |
| `GET /documents` | List indexed documents and their chunk counts |
| `POST /chat/start` | Create a chat session, returns a `session_id` |
| `POST /chat/send` | Send a message; returns a grounded answer + cited sources |
| `GET /chat/{session_id}/history` | Replay a session's messages |

## Extending this project

- **Add metadata filtering**: `query()` in `vector_store.py` can take a
  `knn.filter` — e.g. filter by upload date or a category you attach at
  ingest time.
- **Persist chat history**: swap the in-memory `_sessions` dict in `main.py` for
  a real database, the way `chat_service.py` uses MariaDB.
- **Auth**: add an API key check like `chat_service.py`'s
  `X-AssistX-Internal-Key` middleware before exposing this beyond localhost.
- **Multiple collections again**: if a second document type shows up later
  (e.g. meeting notes vs. policies), `ElasticsearchVectorStore` already
  supports named indices — `pipeline.py` just needs a second
  `ingest_*`/`retrieve` path, the same shape this project had before it was
  simplified down to one.
- **Hybrid search / BM25**: this is the biggest gap versus the production
  app. Elasticsearch already stores a plain `text` field alongside the
  vector — adding a combined BM25 + kNN query in `vector_store.py`'s
  `query()` is the natural next step if you want to see hybrid retrieval,
  not just vector similarity.
