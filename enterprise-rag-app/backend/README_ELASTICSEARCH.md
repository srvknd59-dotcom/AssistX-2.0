# Running this project against Elasticsearch instead of Chroma

By default this project uses Chroma (`VECTOR_DB_BACKEND=chroma` in `.env`) —
an embedded vector database with no server to manage. Elasticsearch is the
real thing the production `chat_service.py`/`ingestor.py` in this repo run
against, but it's a separate server process you have to install and start
yourself. This still means **no Docker** — you download it, unzip it, and
run a `.bat` file — but it's a heavier, more manual setup than Chroma, and a
bigger surface area for something to go wrong in a live training session.
Read the whole page once before doing anything with a room full of people.

> **Safety net:** if Elasticsearch setup goes sideways during a session, you
> can always flip `VECTOR_DB_BACKEND` back to `chroma` in `.env`, restart the
> backend, and keep going — the rest of the app (frontend, ingestion,
> chat) works identically either way. Don't let an ES install problem block
> the whole session.

## 1. Download and extract

Go to the official Elasticsearch downloads page and get the **Windows ZIP**
distribution (not the MSI installer, not Docker):

https://www.elastic.co/downloads/elasticsearch

Unzip it somewhere simple with no spaces in the path, e.g.
`C:\elasticsearch\`. You should end up with a `bin\elasticsearch.bat` inside
that folder.

You do **not** need to separately install Java — the Windows ZIP bundles its
own JDK.

## 2. Disable security for local-only dev use

Elasticsearch 8.x turns on TLS and password auth by default, which is the
right call for anything reachable over a network — but for a single laptop
that never leaves `localhost`, it just adds certificate/enrollment-token
friction we don't need for a training session. Open
`config\elasticsearch.yml` in Notepad and add these two lines at the bottom
(create the file if it's missing entries, don't delete what's already there):

```yaml
xpack.security.enabled: false
xpack.security.http.ssl.enabled: false
```

**This is a local-development shortcut, not something to do on a shared or
internet-reachable machine.** If this laptop is ever used to run
Elasticsearch somewhere other than localhost, security should stay on and
the app's `ES_USERNAME`/`ES_PASSWORD` in `.env` should be set instead.

## 3. Start it

In a PowerShell window:

```powershell
cd C:\elasticsearch\bin
.\elasticsearch.bat
```

First startup takes a minute or two. Leave this window open — like the
backend and frontend, Elasticsearch needs to keep running in its own
terminal. You'll know it's ready when the logs stop scrolling and settle
on a line mentioning `started`.

**Checkpoint:** open http://localhost:9200 in a browser. You should get a
JSON response with `"cluster_name"` and version info, no login prompt (since
security is disabled). If you get a certificate warning or login prompt,
step 2 didn't take — double check `elasticsearch.yml` and restart.

## 4. Point the app at it

In `backend\.env`:

```
VECTOR_DB_BACKEND=elasticsearch
ES_URL=http://localhost:9200
ES_INDEX_PREFIX=rag
```

Leave `ES_USERNAME`/`ES_PASSWORD` blank (security is disabled per step 2).
Restart the backend (`.\run.ps1`) — the FastAPI startup log doesn't print
which backend it picked, but `GET /health` and `GET /documents` will work
identically either way; the difference is invisible from the frontend.

Then ingest as normal — `POST /ingest`, the UI's **Rebuild index** button,
or `python ingest.py` — this now writes into an Elasticsearch index named
`rag_documents` (`{ES_INDEX_PREFIX}_documents`) instead of the Chroma
folder.

**Checkpoint:** `curl http://localhost:9200/rag_documents/_count` (or open
that URL in a browser) should show a document count matching what
`GET /health`'s `chunks_indexed` reports.

## What's actually different under the hood

Same interface, different engine — nothing in `pipeline.py`, `main.py`, or
the frontend changes based on which backend is active. Compare
`app/rag/vector_store.py` (Chroma) with
`app/rag/vector_store_elasticsearch.py` (this one): both implement
`reset_collection`, `add`, `count`, `query`, `list_documents`. The
Elasticsearch version stores each chunk as a document with a `dense_vector`
field and searches with a `knn` query — the same mapping style
`ingestor.py` uses in the production app, just for one simple `documents`
index instead of separate manuals/JSM-ticket indices with BM25 hybrid
search, HyDE, and multi-query expansion layered on top.

## Stopping / resetting

- **Stop**: close the PowerShell window running `elasticsearch.bat`, or
  press Ctrl+C in it.
- **Reset all data**: stop Elasticsearch, delete the `data\` folder inside
  your Elasticsearch install directory, restart. This wipes every index,
  not just this project's — fine for a dedicated training laptop, not fine
  if anything else on the machine also uses this Elasticsearch instance.
- **Reset just this project's index**: with Elasticsearch running, call
  `POST /ingest` again (it deletes and recreates `rag_documents` before
  reloading), or manually: `curl -X DELETE http://localhost:9200/rag_documents`.

## Windows-specific troubleshooting

| Symptom | Fix |
| --- | --- |
| `elasticsearch.bat` window shows a wall of red text and exits | Usually a heap size problem on a low-RAM laptop. Edit `config\jvm.options` and lower `-Xms`/`-Xmx` (e.g. to `1g` each) if the machine has 8GB RAM or less. |
| Backend logs a connection error to `localhost:9200` | Elasticsearch isn't running or hasn't finished starting yet — check its window for a `started` log line. Also confirm `ES_URL` in `.env` matches (`http://localhost:9200`, not `https://`). |
| Browsing http://localhost:9200 asks for a username/password | Security wasn't actually disabled — re-check `config\elasticsearch.yml` for both lines from step 2, save, fully stop and restart Elasticsearch. |
| Port 9200 already in use | Something else is already running on that port (maybe a previous Elasticsearch you forgot was open) — find and close it, or change `http.port` in `elasticsearch.yml` and update `ES_URL` to match. |
| Everything feels slow / laptop fans spin up | Elasticsearch, the backend, and the frontend are all running at once — normal on modest hardware, but if it's unusable, this is a good moment to switch back to `VECTOR_DB_BACKEND=chroma` for the rest of the session. |
