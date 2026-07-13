"""
app.py — the chat UI, built with Streamlit.

Streamlit turns a plain Python script into a web page: every time you
interact with a widget (type a question, click a button), Streamlit
re-runs this whole file top to bottom and redraws the page. `st.session_state`
is how we remember things (like chat history) across those re-runs.

Run it with: streamlit run app.py  (or just ./run.sh)
"""

import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI

import rag_core

load_dotenv()

DOCS_DIR = Path(__file__).parent / "sample_docs"
STORE_DIR = Path(__file__).parent / "index_store"
EMBED_MODEL = os.getenv("EMBED_MODEL", "text-embedding-3-small")
CHAT_MODEL = os.getenv("CHAT_MODEL", "gpt-4o-mini")

st.set_page_config(page_title="RAG Tutorial", page_icon="🔎", layout="centered")
st.title("🔎 RAG Tutorial — Ask Your Documents")
st.caption(
    "A small, readable Retrieval-Augmented Generation app. "
    "Read HOW_RAG_WORKS.md alongside this UI to see how each answer is built."
)

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    st.error(
        "No OPENAI_API_KEY found. Copy `.env.example` to `.env` and add your key, "
        "then restart the app."
    )
    st.stop()

client = st.cache_resource(lambda: OpenAI(api_key=api_key))()


@st.cache_resource(show_spinner=False)
def get_store(_client: OpenAI, version: int):
    """Load the saved index, or build it the first time. `version` busts the cache on rebuild."""
    if rag_core.VectorStore.exists(STORE_DIR):
        return rag_core.VectorStore.load(STORE_DIR), None
    store, stats = rag_core.build_index(_client, DOCS_DIR, STORE_DIR, embed_model=EMBED_MODEL)
    return store, stats


if "index_version" not in st.session_state:
    st.session_state.index_version = 0
if "history" not in st.session_state:
    st.session_state.history = []

with st.sidebar:
    st.header("Your documents")
    doc_files = sorted(p.name for p in DOCS_DIR.glob("*") if p.is_file())
    for name in doc_files:
        st.write(f"- {name}")

    uploaded = st.file_uploader("Add a .txt or .md file", type=["txt", "md"])
    if uploaded is not None:
        target = DOCS_DIR / uploaded.name
        target.write_bytes(uploaded.getvalue())
        st.success(f"Saved {uploaded.name}. Click 'Rebuild index' to include it.")

    if st.button("🔁 Rebuild index"):
        for f in STORE_DIR.glob("*"):
            f.unlink()
        st.session_state.index_version += 1
        st.session_state.history = []

    top_k = st.slider("Passages to retrieve per question", min_value=1, max_value=8, value=4)

with st.spinner("Building the search index the first time this runs..."):
    store, build_stats = get_store(client, st.session_state.index_version)

if build_stats:
    st.sidebar.info(f"Indexed {build_stats['documents']} document(s) into {build_stats['chunks']} chunk(s).")

for turn in st.session_state.history:
    with st.chat_message(turn["role"]):
        st.write(turn["content"])
        if turn.get("sources"):
            with st.expander("Sources used"):
                for i, s in enumerate(turn["sources"], start=1):
                    st.markdown(f"**[{i}] {s['source']}** (similarity {s['score']:.2f})")
                    st.text(s["chunk"])

question = st.chat_input("Ask something about the documents in sample_docs/...")
if question:
    st.session_state.history.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.write(question)

    with st.chat_message("assistant"):
        with st.spinner("Retrieving context and asking the model..."):
            result = rag_core.answer_question(
                client, store, question, chat_model=CHAT_MODEL, embed_model=EMBED_MODEL, top_k=top_k
            )
        st.write(result["answer"])
        if result["sources"]:
            with st.expander("Sources used"):
                for i, s in enumerate(result["sources"], start=1):
                    st.markdown(f"**[{i}] {s['source']}** (similarity {s['score']:.2f})")
                    st.text(s["chunk"])

    st.session_state.history.append(
        {"role": "assistant", "content": result["answer"], "sources": result["sources"]}
    )
