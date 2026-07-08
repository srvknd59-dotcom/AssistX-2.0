# Assistx

Assistx is a Flask-based retrieval-augmented generation (RAG) service for mcube support content. It searches indexed product manuals, diagrams, and Jira Service Management (JSM) tickets in Elasticsearch, sends the retrieved context to a configurable LLM provider, and returns grounded chat answers with source references.

## Features

- **LLM-agnostic chat and embeddings** — swap providers (Azure OpenAI, OpenAI-compatible, Anthropic, Google Gemini) via environment variables, with chat and embeddings configured independently.
- **Hybrid retrieval** over manuals and JSM tickets using BM25 plus optional vector search.
- **Query improvement** with HyDE and multi-query expansion for better recall.
- **Parallel retrieval** across manuals and JSM tickets to reduce response latency.
- **Grounded chat responses** with manual, diagram, and ticket context.
- **Clickable references** for manual files and Jira ticket sources.
- **PowerPoint generation** for slide-oriented answers.
- **Feedback capture** with like/dislike comments stored in MariaDB.
- **User administration and usage tracking** endpoints for Assistx users.
- **Automatic provisioning** for configured corporate email domains.

## Repository layout

| Path | Purpose |
| --- | --- |
| `chat_service.py` | Main Flask API service for chat, retrieval, feedback, users, usage summaries, diagrams, and PPT downloads. |
| `llm_providers.py` | Provider-agnostic chat/embedding/vision-caption layer shared by all services (Azure, OpenAI-compatible, Anthropic, Gemini). |
| `pdf_ingest.py` | Shared PDF/table/link extraction, chunking, and Elasticsearch indexing helpers used by both ingestion services. |
| `ingestor.py` | CLI + REST PDF/diagram ingestion pipeline that chunks manuals, captions diagrams, embeds content, and indexes documents into Elasticsearch. |
| `ingest_service.py` | Lightweight REST-only PDF upload/ingest endpoint (entrypoint for `Dockerfile.ingest`). |
| `requirements.txt` | Python runtime dependencies. |
| `Dockerfile` | Container image definition for the chat service. |
| `Dockerfile.ingest` | Container image definition for the ingestion service. |
| `docker-compose.yaml` | Minimal compose configuration for running the service with an `.env` file. |

## Requirements

- Python 3.10+
- Elasticsearch 8.x
- MariaDB or MySQL-compatible database for feedback, audit, user, and usage tables
- API credentials for your chosen chat and embedding providers (see below)
- Optional system tools for full PDF/table/OCR support:
  - Poppler
  - Ghostscript
  - Tesseract OCR

## Configuration

The application reads configuration from environment variables and an optional `.env` file.

### LLM provider

Chat/completions and embeddings are configured **independently** via `LLM_PROVIDER` and `EMBED_PROVIDER`, because not every chat provider also offers embeddings (e.g. Anthropic has none). `EMBED_PROVIDER` defaults to whatever `LLM_PROVIDER` is set to, so single-provider setups (e.g. all-Azure or all-OpenAI) only need to set `LLM_PROVIDER`.

| Variable | Default | Description |
| --- | --- | --- |
| `LLM_PROVIDER` | `azure` | Chat/vision provider: `azure`, `openai`, `anthropic`, or `gemini`. |
| `EMBED_PROVIDER` | value of `LLM_PROVIDER` | Embedding provider: `azure`, `openai`, or `gemini` (not `anthropic` — it has no embeddings API). |

**`openai`** — any OpenAI-compatible API (OpenAI itself, Groq, Together, Mistral, DeepSeek, Ollama, vLLM, OpenRouter, etc.) via a configurable base URL:

| Variable | Default | Description |
| --- | --- | --- |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | OpenAI-compatible API base URL. Point this at any compatible provider/self-hosted server. |
| `OPENAI_API_KEY` | empty | API key for the above endpoint. |
| `OPENAI_CHAT_MODEL` | `gpt-4o-mini` | Chat model name. |
| `OPENAI_EMBED_MODEL` | `text-embedding-3-large` | Embedding model name. |
| `OPENAI_VISION_MODEL` | value of `OPENAI_CHAT_MODEL` | Vision-capable model used for diagram captions during ingestion. |

**`azure`** — Azure OpenAI:

| Variable | Default | Description |
| --- | --- | --- |
| `AZURE_OPENAI_ENDPOINT` | empty | Azure OpenAI resource endpoint. |
| `AZURE_OPENAI_API_KEY` | empty | Azure OpenAI API key. |
| `AZURE_OPENAI_CHAT_DEPLOYMENT` | `gpt-4o-mini` | Azure chat deployment name. |
| `AZURE_OPENAI_EMBED_DEPLOYMENT` | empty | Azure embedding deployment name. |
| `AZURE_OPENAI_API_VERSION` | `2024-02-15-preview` | Azure OpenAI API version. |
| `AZURE_OPENAI_VISION_DEPLOYMENT` | chat deployment | Vision-capable deployment for diagram captions during ingestion. |

**`anthropic`** — Claude (chat + vision only; pair with `EMBED_PROVIDER=openai`/`azure`/`gemini`):

| Variable | Default | Description |
| --- | --- | --- |
| `ANTHROPIC_BASE_URL` | `https://api.anthropic.com` | Anthropic API base URL. |
| `ANTHROPIC_API_KEY` | empty | Anthropic API key. |
| `ANTHROPIC_CHAT_MODEL` | `claude-sonnet-5` | Claude model name. |
| `ANTHROPIC_API_VERSION` | `2023-06-01` | Anthropic `anthropic-version` header value. |

**`gemini`** — Google Gemini (chat, vision, and embeddings):

| Variable | Default | Description |
| --- | --- | --- |
| `GEMINI_BASE_URL` | `https://generativelanguage.googleapis.com/v1beta` | Gemini API base URL. |
| `GEMINI_API_KEY` | empty | Gemini API key. |
| `GEMINI_CHAT_MODEL` | `gemini-2.0-flash` | Gemini chat/vision model name — confirm the current model ID in Google's docs. |
| `GEMINI_EMBED_MODEL` | `text-embedding-004` | Gemini embedding model name — confirm the current model ID in Google's docs. |

All providers are called via plain HTTP (`requests`), so no extra SDK dependencies are required to add or switch providers.

### Search and retrieval

| Variable | Default | Description |
| --- | --- | --- |
| `ES_BASE_URL` | `http://100.112.2.184:9200` | Elasticsearch URL used by the chat service. |
| `ES_HOST` | `http://localhost:9200` | Elasticsearch URL used by the ingestor. |
| `ES_USERNAME` | `elastic` | Elasticsearch username. |
| `ES_PASSWORD` | `changeme` | Elasticsearch password. |
| `ES_ALIAS` | `mcube_manuals_v1_all` in chat service | Manuals alias used for search. |
| `ES_JSM_INDEX` | `mcube_jsm_tickets` | JSM ticket index used for search. |
| `ES_INDEX_PREFIX` | empty | Optional ingestor index prefix. |
| `ES_INDEX` | empty | Optional single ingestor target index. |
| `TOP_K` | `20` | Number of hits to retrieve per source. |
| `PAGE_WINDOW` | `8` | Nearby-page window for manual context expansion. |
| `DIAGRAM_TOP_K` | `1` | Number of diagrams to attach to answers. |
| `HYDE_ENABLED` | `true` | Enable hypothetical-document query expansion. |
| `MULTI_QUERY_ENABLED` | `true` | Enable multi-query expansion. |
| `MULTI_QUERY_COUNT` | `2` | Number of query variants to generate. |

### Documents and generated files

| Variable | Default | Description |
| --- | --- | --- |
| `DOCS_ROOT` | `./manuals` in ingestor | Root directory containing manuals to ingest. |
| `IMAGE_ROOT` | `./data/manuals` | Root directory used by the chat service for diagram file lookup. |
| `IMAGE_DIR_NAME` | `Diagrams` | Diagram directory name scanned by the ingestor. |
| `DOC_BASE_URL` | `https://help.tcgdigital.com/mcube/manuals` | Base URL used to build manual source links. |
| `PPT_OUTPUT_DIR` | `./data/ppt` | Directory where generated PPT files are stored. |

### Database and auth

| Variable | Default | Description |
| --- | --- | --- |
| `DB_HOST` | `127.0.0.1` | MariaDB/MySQL host. |
| `DB_PORT` | `3306` | MariaDB/MySQL port. |
| `DB_USER` | `root` | Database username. |
| `DB_PASS` | `root` | Database password. |
| `DB_NAME` | `mcube_chat` | Database name. |
| `DB_POOL_SIZE` | `5` | Connection pool size. |
| `ASSISTX_INTERNAL_API_KEY` | empty | Required value for `X-AssistX-Internal-Key` on protected API calls when configured. |
| `AUTO_PROVISION_TCG_EMAILS` | `true` | Auto-create users for the configured email domain. |
| `TCG_EMAIL_DOMAIN` | `tcgdigital.com` | Email domain eligible for auto-provisioning. |
| `MONTHLY_TOKEN_BUDGET` | `138000000` | Monthly token budget used for quota calculations. |
| `MIN_TOKENS_PER_ANSWER` | `2000` | Reserve used when reporting remaining answer capacity. |

## Local setup

1. Create and activate a virtual environment:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```

2. Install dependencies:

   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

3. Create a `.env` file with your Elasticsearch, database, and LLM credentials.

4. Start the chat service:

   ```bash
   python chat_service.py
   ```

The service listens on `PORT`, which defaults to `7001`.

## Ingest manuals and diagrams

Run the ingestor after configuring Elasticsearch and your chosen embedding provider's credentials:

```bash
python ingestor.py --root /path/to/manuals --recreate-index
```

Useful options:

- `--root`: Manual root directory. Defaults to `DOCS_ROOT`.
- `--only`: Ingest a single matching document or path.
- `--recreate-index`: Recreate the target index before ingesting.

`ingestor.py` can also run as a REST service (`python ingestor.py --serve`, port `INGESTOR_PORT`/`5002`) exposing `POST /api/ingest/pdf-upload` for single-PDF uploads. `ingest_service.py` exposes the same upload endpoint on port `5001` without the CLI/versioned-index machinery — it's the entrypoint used by `Dockerfile.ingest`. Both share their extraction and indexing logic via `pdf_ingest.py`.

## API overview

Most chat and admin endpoints are protected by the internal API key middleware. When `ASSISTX_INTERNAL_API_KEY` is set, include this header:

```http
X-AssistX-Internal-Key: <your internal key>
```

### Health

```http
GET /health
```

Returns service health details.

### Start a chat session

```http
POST /chat/start
Content-Type: application/json

{
  "username": "user@example.com"
}
```

### Send a message

```http
POST /chat/send
Content-Type: application/json

{
  "session_id": "<session id>",
  "username": "user@example.com",
  "message": "How do I resolve MCUBETECH-6807?"
}
```

### Set chat preferences

```http
POST /chat/prefs
Content-Type: application/json

{
  "session_id": "<session id>",
  "version": "v1",
  "filename": "manual.pdf"
}
```

### Feedback

```http
POST /feedback
Content-Type: application/json

{
  "answer_id": "<answer id>",
  "rating": "like",
  "comment": "Helpful answer"
}
```

### Other endpoints

- `GET /diagram/<filename>`: Download a diagram file.
- `GET /ppt/<filename>`: Download a generated PowerPoint file.
- `POST /user/isadmin`: Check whether a user is an administrator.
- `GET /usage/summary`: Return token usage summary data.
- `GET /users`: List users.
- `POST /users`: Create a user.
- `PUT /users/<user_id>`: Update a user.

## Docker

Build the image:

```bash
docker build -t assistx .
```

Run the service with an environment file:

```bash
docker run --env-file .env -p 7001:7001 assistx
```

Or use Docker Compose after reviewing `docker-compose.yaml` for your deployment target:

```bash
docker compose up
```

## Development checks

Run a syntax check before committing Python changes:

```bash
python -m py_compile chat_service.py ingestor.py ingest_service.py pdf_ingest.py llm_providers.py
```

## Notes

- Keep secrets in `.env` or your deployment secret manager; do not commit credentials.
- The chat service and ingestor currently use different Elasticsearch URL variables (`ES_BASE_URL` and `ES_HOST`), so configure both when running both processes.
- Ensure MariaDB tables expected by `chat_service.py` exist before using feedback, user, audit, or usage endpoints.
- Mixing providers is expected, not a fallback: e.g. `LLM_PROVIDER=anthropic` with `EMBED_PROVIDER=openai` runs chat on Claude and embeddings on OpenAI in the same deployment.
