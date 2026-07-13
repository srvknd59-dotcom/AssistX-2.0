# RAG + UI Tutorial Project

A small, complete example of a **Retrieval-Augmented Generation (RAG)**
chat app: a document search engine plus a chat UI, in about 250 lines
of Python you can read in one sitting.

It runs entirely on your own laptop (Mac or Linux) with a single
command — **no Docker, no database server, no cloud infrastructure**.
The only external dependency is the OpenAI API, which is what
actually generates the answers.

This project is intentionally simplified for learning. The rest of
this repository (`chat_service.py`, `ingestor.py`) contains a real
production RAG service that does the same thing at a much larger
scale — see [How this relates to the full app](#how-this-relates-to-the-full-assistx-app) below.

## What you'll end up with

A chat window where you can ask questions about a folder of documents,
and get answers that quote exactly which document (and which passage)
they came from — instead of the model just making things up.

```
You:       How long is the GlowMug warranty?
Assistant: The GlowMug comes with a 1-year limited warranty covering
           manufacturing defects [1].

           Sources: [1] return_policy.md
```

## What is RAG, in one paragraph?

Large language models (LLMs) like GPT only know what they were trained
on — they've never seen your company's handbook or your product's
FAQ. RAG fixes that without retraining the model: before asking the
question, the app **searches your own documents** for the most
relevant passages, and pastes those passages into the prompt alongside
the question. The model then answers using that pasted-in context,
the same way you'd answer a question faster if someone handed you the
right page of a manual first. This is why it's called an "open book"
approach — the model isn't memorizing, it's looking things up.

For the full step-by-step breakdown of *how* each piece works, read
**[HOW_RAG_WORKS.md](./HOW_RAG_WORKS.md)** — it's written as a
companion to this README and goes through every function in
`rag_core.py`.

## Project structure

| File | Purpose |
| --- | --- |
| `rag_core.py` | The actual RAG pipeline: load docs, chunk, embed, store, retrieve, generate. No UI code here. |
| `app.py` | The Streamlit chat UI. Imports `rag_core.py` and displays the results. |
| `sample_docs/` | A few example `.md` files (a fictional company's handbook, product FAQ, and return policy) so the app works immediately without you providing your own files. |
| `requirements.txt` | The 5 Python packages this project needs. |
| `run.sh` | One-command setup + launch script for Mac/Linux. |
| `.env.example` | Template for your API key and model settings. |
| `HOW_RAG_WORKS.md` | Deep-dive explanation of every concept and step. |

## Prerequisites

- **Python 3.10 or newer.** Check with `python3 --version`.
- **An OpenAI API key.** Create one at https://platform.openai.com/api-keys.
  Using the API costs a small amount of money per request (a few
  cents at most for this tutorial) — OpenAI gives new accounts free
  trial credit, which is enough to run this many times over.
- **macOS or Linux.** (Windows users: run this inside
  [WSL](https://learn.microsoft.com/windows/wsl/install), which gives
  you a Linux terminal — the steps below then work unchanged.)

No Docker, no database, no extra services to install.

## Setup

1. Open a terminal and go into this folder:

   ```bash
   cd rag-ui-tutorial
   ```

2. Run the setup script:

   ```bash
   ./run.sh
   ```

   The first run will:
   - create a Python virtual environment (`.venv/`)
   - install the dependencies
   - create a `.env` file for you from `.env.example`, then stop and
     ask you to add your API key

3. Open `.env` in any text editor and paste your key:

   ```
   OPENAI_API_KEY=sk-...your-real-key...
   ```

4. Run the script again:

   ```bash
   ./run.sh
   ```

   This time it starts the app and opens it in your browser at
   `http://localhost:8501`. The first load will take a few seconds
   while it builds the search index over the sample documents — after
   that it's saved to disk (`index_store/`) and reused instantly.

## Using the app

- Type a question in the chat box at the bottom, e.g. *"Can I work
  remotely?"* or *"How do I pair the GlowMug?"*
- Click **Sources used** under any answer to see exactly which
  document and passage the model based its answer on.
- Use the sidebar to:
  - see which documents are currently indexed
  - upload your own `.txt` or `.md` file
  - click **Rebuild index** after adding files so they're included
  - adjust how many passages are retrieved per question

Try asking something that's *not* in the documents (e.g. "What's the
company's stock price?") — the app is instructed to say it doesn't
know rather than invent an answer. That's the difference between a
grounded RAG answer and a plain chatbot guess.

## How this relates to the full Assistx app

This tutorial and the production app at the root of this repository
solve the same problem, at different scales:

| | This tutorial | `chat_service.py` + `ingestor.py` |
| --- | --- | --- |
| Vector search | NumPy array, in-memory/on-disk | Elasticsearch cluster |
| Retrieval strategy | Vector similarity only | Hybrid BM25 + vector, HyDE, multi-query expansion |
| Documents | A few `.md`/`.txt`/`.pdf` files | PDF manuals, diagrams, JSM tickets |
| Users/feedback | None | MariaDB-backed users, feedback, usage tracking |
| Deployment | `streamlit run app.py` | Docker + Flask + Elasticsearch + MariaDB |
| Lines of pipeline code | ~250 | Several thousand |

Once the concepts here make sense — chunking, embeddings, retrieval,
grounded prompts — the production code in `chat_service.py` and
`ingestor.py` is the same ideas with more scale, more data sources,
and more production concerns (auth, retries, monitoring) layered on.

## Customizing

- **Use your own documents:** drop `.txt`, `.md`, or `.pdf` files into
  `sample_docs/` (or upload them from the sidebar), then click
  **Rebuild index**.
- **Change the chunk size:** edit the `chunk_size`/`overlap` arguments
  passed to `build_index()` in `app.py`. Smaller chunks give more
  precise citations; larger chunks give the model more surrounding
  context per passage.
- **Change the models:** edit `EMBED_MODEL` / `CHAT_MODEL` in `.env`.
  Any OpenAI chat and embedding model names work.
- **Change how many passages are retrieved:** use the slider in the
  sidebar, or change the default `top_k` in `app.py`.

## Troubleshooting

| Problem | Fix |
| --- | --- |
| `No OPENAI_API_KEY found` | Make sure `.env` exists (not just `.env.example`) and contains a real key, then restart `./run.sh`. |
| `python3: command not found` | Install Python 3.10+ from https://python.org or via your system package manager (`brew install python3`, `apt install python3`, etc.). |
| Answers seem wrong or made up | Click **Sources used** — if no relevant passage was retrieved, the app should say it doesn't know. If it didn't, try rephrasing the question or increasing "Passages to retrieve." |
| Added a file but the app ignores it | Click **Rebuild index** in the sidebar after uploading — the index isn't rebuilt automatically. |
| Want to start over completely | Delete the `index_store/` folder and restart the app; it will rebuild from scratch. |

## A note on cost and secrets

- Every question you ask makes a small number of paid API calls to
  OpenAI (one embedding call for your question, one chat call for the
  answer). Keep an eye on usage at platform.openai.com if you're on a
  budget.
- **Never commit your `.env` file or share your API key.** `.env` is
  already listed in `.gitignore` in this folder so `git` won't pick it
  up by accident.
