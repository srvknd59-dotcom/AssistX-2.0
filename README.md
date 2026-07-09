# Assistx

Assistx is a Flask-based retrieval-augmented generation (RAG) service for mcube support content. It searches indexed product manuals, diagrams, and Jira Service Management (JSM) tickets in Elasticsearch, sends the retrieved context to OpenAI or Azure OpenAI, and returns grounded chat answers with source references.

> **New to RAG?** See [`rag-ui-tutorial/`](./rag-ui-tutorial) for a small, self-contained
> RAG + chat UI project (no Docker, no Elasticsearch, one setup script) with a
> step-by-step explanation of every concept, written as a teaching companion to
> the full service documented below.

## Features

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
| `ingestor.py` | PDF and diagram ingestion pipeline that chunks manuals, captions diagrams, embeds content, and indexes documents into Elasticsearch. |
| `requirements.txt` | Python runtime dependencies. |
| `Dockerfile` | Container image definition for the chat service. |
| `docker-compose.yaml` | Minimal compose configuration for running the service with an `.env` file. |

## Requirements

- Python 3.10+
- Elasticsearch 8.x
- MariaDB or MySQL-compatible database for feedback, audit, user, and usage tables
- Azure OpenAI or OpenAI API credentials
- Optional system tools for full PDF/table/OCR support:
  - Poppler
  - Ghostscript
  - Tesseract OCR

## Configuration

The application reads configuration from environment variables and an optional `.env` file.

### LLM provider

| Variable | Default | Description |
| --- | --- | --- |
| `LLM_PROVIDER` | `azure` | Use `azure` or `openai`. |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | OpenAI-compatible API base URL. |
| `OPENAI_API_KEY` | empty | OpenAI API key. |
| `OPENAI_CHAT_MODEL` | `gpt-4o-mini` | OpenAI chat model. |
| `OPENAI_EMBED_MODEL` | `text-embedding-3-large` | OpenAI embedding model. |
| `AZURE_OPENAI_ENDPOINT` | empty | Azure OpenAI resource endpoint. |
| `AZURE_OPENAI_API_KEY` | empty | Azure OpenAI API key. |
| `AZURE_OPENAI_CHAT_DEPLOYMENT` | `gpt-4o-mini` | Azure chat deployment name. |
| `AZURE_OPENAI_EMBED_DEPLOYMENT` | empty | Azure embedding deployment name. |
| `AZURE_OPENAI_API_VERSION` | `2024-02-15-preview` | Azure OpenAI API version. |
| `AZURE_OPENAI_VISION_DEPLOYMENT` | chat deployment | Optional Azure vision-capable deployment for diagram captions during ingestion. |

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

Run the ingestor after configuring Elasticsearch and Azure OpenAI embedding credentials:

```bash
python ingestor.py --root /path/to/manuals --recreate-index
```

Useful options:

- `--root`: Manual root directory. Defaults to `DOCS_ROOT`.
- `--only`: Ingest a single matching document or path.
- `--recreate-index`: Recreate the target index before ingesting.

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
python -m py_compile chat_service.py ingestor.py
```

## Notes

- Keep secrets in `.env` or your deployment secret manager; do not commit credentials.
- The chat service and ingestor currently use different Elasticsearch URL variables (`ES_BASE_URL` and `ES_HOST`), so configure both when running both processes.
- Ensure MariaDB tables expected by `chat_service.py` exist before using feedback, user, audit, or usage endpoints.
