# How RAG Works — A Step-by-Step Walkthrough

This document explains every concept behind this project, in the
order the code actually executes. Read it next to `rag_core.py` —
each section names the function it's describing.

If you only remember one sentence: **RAG means "search first, then
ask the AI to answer using only what was found."**

## The big picture

```
 ┌──────────────┐   chunk_text()   ┌───────────┐   embed_texts()   ┌────────────┐
 │  Your files   │ ───────────────▶ │  Chunks   │ ─────────────────▶ │ Embeddings │
 │ (.txt/.md/pdf)│                  │ (short    │                    │ (vectors of│
 └──────────────┘                  │  passages)│                    │  numbers)  │
                                    └───────────┘                    └─────┬──────┘
                                                                            │ store
                                                                            ▼
                                                                   ┌────────────────┐
                                                                   │   VectorStore   │
                                                                   │ (embeddings.npy │
                                                                   │  + chunks.json) │
                                                                   └────────┬────────┘
                                                                            │ search()
  When you ask a question:                                                 │
 ┌──────────────┐   embed_texts()   ┌────────────┐   cosine similarity     │
 │   Question    │ ─────────────────▶ │  Query    │ ────────────────────────┘
 └──────┬───────┘                    │ embedding  │
        │                            └────────────┘
        │                                                     top_k best chunks
        ▼                                                            │
 ┌──────────────────────────────────────────────────────────────────▼──┐
 │  Prompt = system instructions + numbered context passages + question │
 └───────────────────────────────────┬────────────────────────────────┘
                                      │ chat.completions.create()
                                      ▼
                              ┌───────────────┐
                              │  LLM answer,  │
                              │ with citations │
                              └───────────────┘
```

Everything above the dashed line ("indexing") happens once, when the
app first starts or when you click **Rebuild index**. Everything
below it ("retrieval + generation") happens every time you ask a
question, and takes well under a second for the vector search part.

## Step 1 — Loading documents (`load_documents`)

We read every `.txt`, `.md`, and `.pdf` file in `sample_docs/` into
plain text strings. PDFs need a library (`pypdf`) because their files
store text as drawing instructions, not plain text — the library
figures out what text was drawn on each page.

## Step 2 — Chunking (`chunk_text`)

Why not just hand the model the entire handbook? Two reasons:

1. **Cost and limits.** Models charge (and have hard limits) per
   token processed. Sending every document on every question wastes
   money and eventually won't fit.
2. **Precision.** If you paste in an entire 10-page manual, the
   embedding for "the whole document" is a blurry average of
   everything in it — very different topics get squashed into one
   vector, which makes similarity search much less accurate. Splitting
   into short, focused chunks means each chunk's embedding actually
   represents *one* idea.

This project chunks by **words**, using a sliding window: take the
first 180 words as chunk 1, then step forward 150 words (180 minus 30
words of overlap) and take the next 180 as chunk 2, and so on. The
overlap exists so a sentence that happens to fall right at a chunk
boundary still appears whole in at least one chunk.

Production systems (like `ingestor.py` in this repo) chunk more
carefully — by token count, respecting sentence and page boundaries,
and sometimes keeping table structure intact — but the goal is
identical: many small, coherent, independently-meaningful passages.

## Step 3 — Embeddings (`embed_texts`)

An embedding is a list of numbers (for OpenAI's `text-embedding-3-small`,
1,536 of them) that represents the *meaning* of a piece of text as a
point in space. The key property: texts with similar meaning end up
as points that are close together, regardless of the exact words used.

```
embed("How do I return a product?")
  ≈ [0.0123, -0.0456, 0.0891, ...]   (1,536 numbers)

embed("What's your refund policy?")
  ≈ [0.0119, -0.0440, 0.0902, ...]   (a very similar list of numbers,
                                       because the meaning is similar,
                                       even though barely any words match)
```

This is the trick that makes RAG work better than plain keyword
search (like Ctrl+F): a question phrased differently from the
document can still find the right passage, because we're matching
meaning, not exact words.

## Step 4 — Storing and searching vectors (`VectorStore`)

Once every chunk has an embedding, we need to find, for a new
question's embedding, which chunk embeddings are closest to it. This
project does that with **cosine similarity**: treat each embedding as
an arrow from the origin, and measure the angle between two arrows.
Arrows pointing the same direction (similar meaning) score close to 1;
unrelated arrows score close to 0.

```python
doc_norms = self.embeddings / np.linalg.norm(self.embeddings, axis=1, keepdims=True)
query_norm = query_embedding / np.linalg.norm(query_embedding)
scores = doc_norms @ query_norm   # one similarity score per chunk
```

We then take the `top_k` highest-scoring chunks (`np.argsort(-scores)[:top_k]`)
— by default the 4 most relevant passages across all your documents.

This is a **vector database** in its simplest possible form: an array
of numbers plus a similarity search over it. Real deployments swap
this NumPy array for a dedicated vector database (Chroma, FAISS,
Pinecone) or a search engine with vector support (Elasticsearch, which
the production `chat_service.py` in this repo uses) because those can
index millions of vectors and stay fast — the *math* is the same idea
you just read.

## Step 5 — Building the prompt and generating an answer (`answer_question`)

We take the retrieved chunks and lay them out as numbered context,
then hand the model a system message with ground rules:

```
You are a helpful assistant that answers questions using ONLY the
context provided below... If the answer isn't in the context, say you
don't know... cite it inline like [1].
```

This instruction is what makes the answer "grounded" instead of a
free-form guess — the model is told explicitly not to use outside
knowledge and to show its work by citing which passage it used. It's
the same reason the UI shows a **Sources used** panel: you should
always be able to check the model's homework.

`temperature=0.2` is a knob that controls how "creative" vs.
deterministic the model's wording is. We keep it low here because we
want consistent, factual answers, not creative writing.

## Step 6 — The UI loop (`app.py`)

Streamlit re-runs the entire `app.py` script from top to bottom every
time you interact with the page. Two things make that workable for a
chat app:

- **`st.session_state`** is a dictionary that survives across
  re-runs, so we store the chat history and index version there
  instead of losing it every time the script restarts.
- **`st.cache_resource`** remembers expensive objects (the OpenAI
  client, the loaded vector store) across re-runs so we don't
  reconnect or re-embed everything on every keystroke.

The flow on each question:

1. `st.chat_input` returns the typed question once the user presses Enter.
2. We append it to `st.session_state.history` and display it.
3. We call `rag_core.answer_question(...)`, which does Steps 3-5 above
   for this one question.
4. We display the answer and, in an expander, the exact source
   passages that were retrieved.

## Glossary

| Term | Meaning |
| --- | --- |
| **LLM** | Large Language Model — the AI model (e.g. GPT-4o-mini) that generates the final text answer. |
| **Embedding** | A list of numbers representing the meaning of a piece of text. |
| **Vector** | Another word for that list of numbers — a point in many-dimensional space. |
| **Vector store / vector database** | Something that stores embeddings and can quickly find the ones most similar to a new one. |
| **Cosine similarity** | A way to measure how similar two vectors' *directions* are, ignoring their length. Ranges from -1 (opposite) to 1 (identical direction). |
| **Chunk** | A short passage of text, small enough to embed and retrieve precisely. |
| **Retrieval** | The step of searching for the most relevant chunks for a given question. |
| **Grounding** | Restricting the model's answer to only use the retrieved context, so it can't "make things up" (hallucinate). |
| **Hallucination** | When an LLM states something false or unsupported as if it were fact. RAG's main purpose is reducing this. |
| **Prompt** | The full text sent to the LLM — here, the system instructions + retrieved context + question. |
| **Token** | The unit LLMs actually process text in (roughly 3/4 of a word on average). Pricing and limits are measured in tokens. |

## Things to try (exercises)

1. Change `top_k` from 4 to 1 and ask a question that needs facts from
   two different documents — watch the answer get worse. This shows
   why `top_k` matters.
2. Change `chunk_size` from 180 to 40 words, delete `index_store/`,
   and rebuild. Notice the citations get more precise but sometimes
   lose surrounding context.
3. Add a new document to `sample_docs/` about a topic not covered
   elsewhere, rebuild the index, and ask about it — confirm the
   answer cites your new file.
4. Ask a question with no answer in any document (e.g. "Who is the
   CEO?") and confirm the model says it doesn't know instead of
   guessing.
5. Read `chat_service.py`'s retrieval code in the root of this repo
   and find the equivalent of `VectorStore.search()` — it's doing the
   same job against Elasticsearch instead of NumPy.
