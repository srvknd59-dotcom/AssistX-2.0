# One-Day Plan: RAG + Enterprise React UI on Windows

Goal for the day: by the end, there is a working app on her Windows laptop —
a real vector database (Chroma) holding a set of ingested documents, a
FastAPI backend that retrieves from it and asks an LLM, and a React chat UI
talking to that backend. No Docker, no external services besides the
OpenAI API.

This assumes the code in `enterprise-rag-app/` (this folder) is already on
the machine — either by cloning this repo or copying the folder over. Total
time: roughly 7-8 hours including breaks. Times are guidelines, not a clock
to watch.

**Running this as a training session for someone else, using Elasticsearch
instead of Chroma?** Read [`TRAINER_GUIDE.md`](./TRAINER_GUIDE.md) first —
it's written for the facilitator and covers pacing, what to say, and how
this plan changes for Hour 2-3 when Elasticsearch is the vector database
(see [`backend/README_ELASTICSEARCH.md`](./backend/README_ELASTICSEARCH.md)
for the install steps). The rest of this document works unchanged either
way — the vector database is a one-line config swap, not a different app.

---

## Before the day (15 minutes, do this the night before)

Get the two accounts/installs that take unpredictable time out of the way:

1. **OpenAI API key** — create one at https://platform.openai.com/api-keys.
   New accounts get free trial credit; this whole day of experimentation
   costs a few cents to a couple of dollars in API usage.
2. **Node.js 18+** — download the Windows installer from https://nodejs.org
   (choose the "LTS" version) and run it, accepting the defaults.
3. **Python 3.10+** — download from https://python.org/downloads. **Important:**
   on the first installer screen, check the box **"Add python.exe to PATH"**
   before clicking Install.
4. **Git for Windows** (if the code will be cloned rather than copied) —
   https://git-scm.com/download/win, defaults are fine.
5. **VS Code** (optional but recommended for reading the code) —
   https://code.visualstudio.com.

Verify all four installed correctly by opening **PowerShell** (Start menu →
type "PowerShell") and running:

```powershell
python --version
node --version
npm --version
git --version
```

Each should print a version number. If `python --version` fails, restart
PowerShell (PATH changes need a fresh terminal) — if it still fails, reinstall
Python and make sure "Add to PATH" was checked.

---

## Hour 1 — Orient: what are we building and why

Before touching a keyboard, read together:

- This file's [Architecture](./README.md#architecture) section — the four
  boxes (React UI → FastAPI → Chroma vector DB → OpenAI) and how a question
  flows through them.
- `rag-ui-tutorial/HOW_RAG_WORKS.md` in the repo root — the concepts
  (chunking, embeddings, retrieval, grounding) that this project's backend
  implements, just against a real database instead of a NumPy array.

**Checkpoint:** she can explain, in her own words, what happens between
typing a question and seeing an answer with citations. If not, re-read
`HOW_RAG_WORKS.md` — this hour is the foundation for everything after it.

---

## Hour 2 — Backend: get the API running

Open PowerShell and allow scripts to run for your user account (one-time,
only needed if PowerShell blocks `.ps1` files):

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Then:

```powershell
cd path\to\AssistX-2.0\enterprise-rag-app\backend
.\setup.ps1
```

This creates a virtual environment and installs FastAPI, Chroma, and the
OpenAI SDK. It will stop and tell you to edit `.env` — open
`backend\.env` in Notepad or VS Code and paste in the API key from last
night:

```
OPENAI_API_KEY=sk-...your real key...
```

Save the file, then run setup again to confirm, and start the server:

```powershell
.\setup.ps1
.\run.ps1
```

You should see `Uvicorn running on http://127.0.0.1:8000`. Leave this
window open — this is your backend, and it needs to keep running.

**Checkpoint:** open http://localhost:8000/docs in a browser. This is
FastAPI's auto-generated interactive API explorer — you should see the
`/health`, `/ingest`, `/documents/upload`, `/chat/start`, `/chat/send`
endpoints listed. Click on `POST /ingest`, then "Try it out", then
"Execute" — this builds the Chroma vector database from the sample
documents in `backend/data/documents/`. You should get back something like:

```json
{"documents_indexed": 3, "chunks_indexed": 5}
```

If this fails with an authentication error, double check `.env` has the
real API key (not the placeholder) and that you re-ran `.\run.ps1` after
editing it (environment variables are only read on startup).

---

## Hour 3 — Backend: see retrieval and grounding in action

Still in `/docs`, try `POST /chat/start` (Execute with no input) — copy the
`session_id` it returns. Then try `POST /chat/send` with:

```json
{
  "session_id": "paste-it-here",
  "message": "How do I pair the GlowMug with the app?"
}
```

Look at the response's `sources` array — this is retrieval working: Chroma
found the passages in `product_faq.md` most similar to the question, and the
model's `answer` is grounded in them.

**Try this exercise:** ask a question the sample data can't answer (e.g.
*"What's the company's stock price?"*) and confirm the model says it doesn't
know instead of guessing. Then open `backend/app/rag/pipeline.py` and find
`SYSTEM_PROMPT` — that's the instruction responsible for this behavior.

**Checkpoint:** she has made at least 3 different `/chat/send` calls through
the docs UI and can point to which file in `data/documents/` each answer's
sources came from.

## Lunch break

---

## Hour 4 — Frontend: get the React UI running

Open a **second** PowerShell window (keep the backend running in the first):

```powershell
cd path\to\AssistX-2.0\enterprise-rag-app\frontend
.\setup.ps1
.\run.ps1
```

You should see Vite print `Local: http://localhost:5173/`. Open that URL —
this is the real chat UI, talking to the backend that's been running since
Hour 2.

**Checkpoint:** the sidebar shows the 3 sample documents with chunk counts
(if it shows "Not indexed yet," go back and run `/ingest` from Hour 2
again). Ask a question in the chat box and confirm the answer appears with
an expandable "Show sources" link, matching what you saw in the API docs in
Hour 3 — same backend, now with a real UI in front of it. Also try the file
picker under "Add a document" in the sidebar — upload a small `.txt` file,
click **Rebuild index**, and confirm it shows up in the document list.

From now on, `.\start-all.ps1` (from the `enterprise-rag-app` folder) will
launch both windows at once, so this two-terminal dance is only needed once.

---

## Hour 5 — Walk the code

With the app running, open the project in VS Code (`code .` from the
`enterprise-rag-app` folder, or File → Open Folder) and read through, in
this order:

1. `backend/app/rag/chunking.py` — the simplest file, ~30 lines.
2. `backend/app/rag/vector_store.py` — the Chroma wrapper. Compare it to
   `rag-ui-tutorial/rag_core.py`'s `VectorStore` class — same job, real
   database.
3. `backend/app/rag/pipeline.py` — where retrieval and generation happen.
   `retrieve()` queries the Chroma collection; `answer()` builds the prompt
   and calls OpenAI.
4. `backend/app/main.py` — the FastAPI routes; each one is a thin wrapper
   around a `pipeline` method.
5. `frontend/src/hooks/useChat.ts` — how the UI keeps track of messages
   and calls the backend.
6. `frontend/src/components/ChatWindow.tsx` and `MessageBubble.tsx` — how
   that state becomes the chat bubbles on screen.

**Exercise:** in `frontend/src/components/ChatInput.tsx`, change the
placeholder text, save, and watch the browser auto-reload (Vite's hot
reload) — a small, safe way to confirm she can find and change UI code.

---

## Hour 6 — Make it hers

Pick 2-3 of these, in order of how much time is left:

- **Swap the data**: replace the files in `backend/data/documents/` with
  something she's interested in (a hobby, a school subject, a game's rules)
  written as `.md`/`.txt` files — or use the sidebar's upload button instead
  of touching the filesystem at all. Click **Rebuild index** in the UI and
  ask questions about the new content.
- **Change the branding**: edit `frontend/src/components/Header.tsx` — the
  title, subtitle, and the "RA" logo badge.
- **Change retrieval behavior**: in `backend/app/config.py`, change
  `top_k` (how many passages come back per question) and restart the
  backend; compare answer quality with 1 vs. 8.
- **Add a manual test to the system prompt**: edit `SYSTEM_PROMPT` in
  `pipeline.py` to require a specific answer format (e.g. always end with a
  one-line summary) and see the model follow it.

---

## Hour 7 — Make sure it survives a restart

The real test of "it's set up on her machine" is that it still works after
closing everything and starting fresh:

1. Close both PowerShell windows (backend and frontend) and the browser tab.
2. Reopen PowerShell, `cd` into `enterprise-rag-app`, run `.\start-all.ps1`.
3. Open http://localhost:5173 again and ask a question.

If that works without re-running `setup.ps1`, the environment is durably
installed (the `.venv` and `node_modules` folders persist on disk).

Then walk through the [Troubleshooting](#windows-troubleshooting) section
below together so she knows what to do if something breaks after you leave.

---

## Optional stretch goals (if time remains)

- Read `GET /chat/{session_id}/history` in `/docs` and explain why chat
  history disappears when the backend restarts (it's stored in a Python
  dictionary in memory — see the `_sessions` variable in `main.py`) versus
  how the production `chat_service.py` in the repo root persists it to
  MariaDB instead.
- Try `backend/ingest.py` directly (`python ingest.py` from an activated
  venv) instead of the `/ingest` endpoint — same code path, run as a script.
- Skim `chat_service.py` and `ingestor.py` in the repo root and find the
  production equivalents of `retrieve()` and `chunk_text()` — same ideas,
  more scale.

---

## Windows troubleshooting

| Symptom | Fix |
| --- | --- |
| `.\setup.ps1` errors with "running scripts is disabled on this system" | Run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, then retry. |
| A script errors with "is not digitally signed" / `UnauthorizedAccess` | Windows flags files extracted from a downloaded ZIP as "from the internet." Run once from the `enterprise-rag-app` folder: `Get-ChildItem -Recurse -Filter *.ps1 \| Unblock-File`, then retry. |
| `python` / `py` not recognized | Install Python 3.10+ from python.org and check "Add python.exe to PATH" on the first install screen; open a **new** PowerShell window afterward. Confirm with `py --list`. |
| `npm` not recognized | Reinstall Node.js from nodejs.org; open a new PowerShell window afterward. |
| Setup keeps failing in confusing ways even after fixing the above | The `.venv` folder may be left over from a broken earlier attempt (it's permanently bound to whatever Python created it). Delete it and let `.\setup.ps1` rebuild it: `Remove-Item -Recurse -Force backend\.venv`, then `.\setup.ps1` again. |
| Backend fails with an OpenAI authentication error | Open `backend\.env`, confirm `OPENAI_API_KEY` is a real key (starts `sk-`), save, then stop (Ctrl+C) and re-run `.\run.ps1` — env vars are only read at startup. |
| Frontend loads but shows "Backend unreachable" | Make sure the backend PowerShell window is still open and shows `Uvicorn running`. Check it's on port 8000: http://localhost:8000/health should return JSON directly in a browser. |
| Browser console shows a CORS error | Confirm `backend\.env` has `CORS_ORIGIN=http://localhost:5173,http://127.0.0.1:5173` and restart the backend. Make sure the frontend URL you're opening matches one of those origins exactly. |
| `Address already in use` on port 8000 or 5173 | Something is already using that port — close old PowerShell windows running `run.ps1`, or change the port: backend with `uvicorn app.main:app --port 8001` (and update `frontend/.env`'s `VITE_API_BASE_URL` to match), frontend with `npm run dev -- --port 5174`. |
| Windows Defender / antivirus flags `node_modules` or slows install | This is a known false-positive pattern with npm on Windows; it's safe to allow. If installs are very slow, add the project folder to Defender's exclusion list. |
| `pip install` fails partway through | Usually a flaky network blip — just run `.\setup.ps1` again; pip resumes from cached packages. |

---

## End-of-day checklist

- [ ] `.\start-all.ps1` opens two windows and both stay running without errors
- [ ] http://localhost:5173 loads and the sidebar shows the indexed documents
- [ ] A question about the sample data returns an answer with visible sources
- [ ] A question outside the sample data gets an honest "I don't know"
- [ ] She's edited at least one file (data, branding, or a config value) and seen the result
- [ ] She can explain the four boxes in the architecture diagram in her own words
