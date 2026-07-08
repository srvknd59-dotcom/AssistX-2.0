# llm_providers.py
# Provider-agnostic chat, embedding, and vision-captioning layer.
#
# Chat/completions and embeddings are configured independently
# (LLM_PROVIDER vs EMBED_PROVIDER) because not every chat provider also
# offers embeddings (e.g. Anthropic has no embeddings API).
#
# Supported providers:
#   - azure      : Azure OpenAI (chat, embeddings, vision)
#   - openai     : Any OpenAI-compatible API (OpenAI, Groq, Together, Mistral,
#                  DeepSeek, Ollama, vLLM, OpenRouter, ...) via OPENAI_BASE_URL
#   - anthropic  : Anthropic Claude (chat, vision) - no embeddings
#   - gemini     : Google Gemini (chat, embeddings, vision)
#
# All calls use plain HTTP via `requests` (no extra SDK dependencies), mirroring
# how this codebase already talked to Azure/OpenAI.

import os
import re
import base64
import logging
from typing import Dict, List, Optional, Tuple

import requests
from tenacity import retry, wait_exponential, stop_after_attempt

log = logging.getLogger("llm_providers")

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "azure").strip().lower()
EMBED_PROVIDER = os.getenv("EMBED_PROVIDER", LLM_PROVIDER).strip().lower()

# ---- OpenAI-compatible (OpenAI, Groq, Together, Mistral, DeepSeek, Ollama, vLLM, OpenRouter, ...) ----
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")
OPENAI_EMBED_MODEL = os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-large")
OPENAI_VISION_MODEL = os.getenv("OPENAI_VISION_MODEL", OPENAI_CHAT_MODEL)

# ---- Azure OpenAI ----
AZURE_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT", "").rstrip("/")
AZURE_API_KEY = os.getenv("AZURE_OPENAI_API_KEY", "")
AZURE_CHAT_DEPLOYMENT = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-4o-mini")
AZURE_EMBED_DEPLOYMENT = os.getenv("AZURE_OPENAI_EMBED_DEPLOYMENT", "")
AZURE_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
AZURE_VISION_DEPLOYMENT = os.getenv("AZURE_OPENAI_VISION_DEPLOYMENT", AZURE_CHAT_DEPLOYMENT)

# ---- Anthropic (chat + vision only, no embeddings) ----
ANTHROPIC_BASE_URL = os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com").rstrip("/")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_CHAT_MODEL = os.getenv("ANTHROPIC_CHAT_MODEL", "claude-sonnet-5")
ANTHROPIC_API_VERSION = os.getenv("ANTHROPIC_API_VERSION", "2023-06-01")

# ---- Google Gemini ----
GEMINI_BASE_URL = os.getenv("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta").rstrip("/")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_CHAT_MODEL = os.getenv("GEMINI_CHAT_MODEL", "gemini-2.0-flash")
GEMINI_EMBED_MODEL = os.getenv("GEMINI_EMBED_MODEL", "text-embedding-004")


def active_chat_model() -> str:
    return {
        "azure": AZURE_CHAT_DEPLOYMENT,
        "openai": OPENAI_CHAT_MODEL,
        "anthropic": ANTHROPIC_CHAT_MODEL,
        "gemini": GEMINI_CHAT_MODEL,
    }.get(LLM_PROVIDER, LLM_PROVIDER)


def active_embed_model() -> str:
    return {
        "azure": AZURE_EMBED_DEPLOYMENT,
        "openai": OPENAI_EMBED_MODEL,
        "gemini": GEMINI_EMBED_MODEL,
    }.get(EMBED_PROVIDER, EMBED_PROVIDER)


def _raise_for_status_logged(r: requests.Response, label: str) -> None:
    if not r.ok:
        try:
            log.error("%s error %s: %s", label, r.status_code, r.json())
        except Exception:
            log.error("%s error %s: %s", label, r.status_code, r.text)
        r.raise_for_status()


def _norm_chat_usage(usage_raw: dict) -> Dict:
    pt = usage_raw.get("prompt_tokens") or usage_raw.get("input_tokens") or 0
    ct = usage_raw.get("completion_tokens") or usage_raw.get("output_tokens") or 0
    tt = usage_raw.get("total_tokens") or (pt + ct)
    return {"prompt_tokens": int(pt), "completion_tokens": int(ct), "total_tokens": int(tt), "raw": usage_raw}


def _norm_embed_usage(usage_raw: dict) -> Dict:
    pt = usage_raw.get("prompt_tokens") or usage_raw.get("input_tokens") or 0
    tt = usage_raw.get("total_tokens") or pt
    return {"prompt_tokens": int(pt), "total_tokens": int(tt), "raw": usage_raw}


def _b64_file(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


# --------------------- Chat / completions ---------------------
def _openai_chat(messages: List[Dict], temperature: float, max_tokens: int) -> Tuple[str, Dict]:
    if not OPENAI_API_KEY:
        raise RuntimeError("OpenAI-compatible chat not configured (OPENAI_API_KEY missing)")
    url = f"{OPENAI_BASE_URL}/chat/completions"
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
    body = {"model": OPENAI_CHAT_MODEL, "messages": messages, "temperature": temperature, "max_tokens": max_tokens}
    r = requests.post(url, headers=headers, json=body, timeout=120)
    _raise_for_status_logged(r, "OpenAI-compatible LLM")
    data = r.json()
    content = data["choices"][0]["message"]["content"]
    usage = _norm_chat_usage(data.get("usage") or {})
    log.info("LLM USAGE (openai): prompt=%s completion=%s total=%s",
              usage["prompt_tokens"], usage["completion_tokens"], usage["total_tokens"])
    return content, usage


def _azure_chat(messages: List[Dict], temperature: float, max_tokens: int) -> Tuple[str, Dict]:
    if not (AZURE_ENDPOINT and AZURE_CHAT_DEPLOYMENT and AZURE_API_KEY):
        raise RuntimeError("Azure chat not configured")
    url = f"{AZURE_ENDPOINT}/openai/deployments/{AZURE_CHAT_DEPLOYMENT}/chat/completions?api-version={AZURE_API_VERSION}"
    headers = {"api-key": AZURE_API_KEY, "Content-Type": "application/json"}
    body = {"messages": messages, "temperature": temperature, "max_tokens": max_tokens}
    r = requests.post(url, headers=headers, json=body, timeout=120)
    _raise_for_status_logged(r, "Azure LLM")
    data = r.json()
    content = data["choices"][0]["message"]["content"]
    usage = _norm_chat_usage(data.get("usage") or {})
    log.info("LLM USAGE (azure): prompt=%s completion=%s total=%s",
              usage["prompt_tokens"], usage["completion_tokens"], usage["total_tokens"])
    return content, usage


def _split_system_and_turns(messages: List[Dict]) -> Tuple[str, List[Dict]]:
    system_parts, turns = [], []
    for m in messages:
        role, content = m.get("role"), m.get("content")
        if role == "system":
            if isinstance(content, str):
                system_parts.append(content)
            continue
        turns.append({"role": role, "content": content})
    return "\n\n".join(system_parts), turns


def _anthropic_chat(messages: List[Dict], temperature: float, max_tokens: int) -> Tuple[str, Dict]:
    if not ANTHROPIC_API_KEY:
        raise RuntimeError("Anthropic chat not configured (ANTHROPIC_API_KEY missing)")
    system_text, turns = _split_system_and_turns(messages)
    url = f"{ANTHROPIC_BASE_URL}/v1/messages"
    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": ANTHROPIC_API_VERSION,
        "Content-Type": "application/json",
    }
    body = {"model": ANTHROPIC_CHAT_MODEL, "max_tokens": max_tokens, "temperature": temperature, "messages": turns}
    if system_text:
        body["system"] = system_text
    r = requests.post(url, headers=headers, json=body, timeout=120)
    _raise_for_status_logged(r, "Anthropic LLM")
    data = r.json()
    content = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
    usage_raw = data.get("usage") or {}
    pt, ct = int(usage_raw.get("input_tokens") or 0), int(usage_raw.get("output_tokens") or 0)
    usage = {"prompt_tokens": pt, "completion_tokens": ct, "total_tokens": pt + ct, "raw": usage_raw}
    log.info("LLM USAGE (anthropic): prompt=%s completion=%s total=%s", pt, ct, pt + ct)
    return content, usage


def _gemini_chat(messages: List[Dict], temperature: float, max_tokens: int) -> Tuple[str, Dict]:
    if not GEMINI_API_KEY:
        raise RuntimeError("Gemini chat not configured (GEMINI_API_KEY missing)")
    system_text, turns = _split_system_and_turns(messages)
    contents = [{"role": ("model" if t["role"] == "assistant" else "user"),
                 "parts": [{"text": t["content"]}]} for t in turns]
    url = f"{GEMINI_BASE_URL}/models/{GEMINI_CHAT_MODEL}:generateContent?key={GEMINI_API_KEY}"
    body = {"contents": contents, "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens}}
    if system_text:
        body["systemInstruction"] = {"parts": [{"text": system_text}]}
    r = requests.post(url, json=body, timeout=120)
    _raise_for_status_logged(r, "Gemini LLM")
    data = r.json()
    candidates = data.get("candidates") or []
    parts = candidates[0].get("content", {}).get("parts", []) if candidates else []
    content = "".join(p.get("text", "") for p in parts)
    usage_raw = data.get("usageMetadata") or {}
    pt = int(usage_raw.get("promptTokenCount") or 0)
    ct = int(usage_raw.get("candidatesTokenCount") or 0)
    tt = int(usage_raw.get("totalTokenCount") or (pt + ct))
    usage = {"prompt_tokens": pt, "completion_tokens": ct, "total_tokens": tt, "raw": usage_raw}
    log.info("LLM USAGE (gemini): prompt=%s completion=%s total=%s", pt, ct, tt)
    return content, usage


_CHAT_DISPATCH = {
    "azure": _azure_chat,
    "openai": _openai_chat,
    "anthropic": _anthropic_chat,
    "gemini": _gemini_chat,
}


def chat_completion(messages: List[Dict], temperature: float = 0.0, max_tokens: int = 900) -> Tuple[str, Dict]:
    fn = _CHAT_DISPATCH.get(LLM_PROVIDER)
    if not fn:
        raise RuntimeError(f"Unsupported LLM_PROVIDER: {LLM_PROVIDER}")
    return fn(messages, temperature, max_tokens)


# --------------------- Embeddings ---------------------
def _openai_embed(texts: List[str]) -> Tuple[List[List[float]], Dict]:
    if not OPENAI_API_KEY:
        raise RuntimeError("OpenAI-compatible embeddings not configured (OPENAI_API_KEY missing)")
    url = f"{OPENAI_BASE_URL}/embeddings"
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
    r = requests.post(url, headers=headers, json={"model": OPENAI_EMBED_MODEL, "input": texts}, timeout=90)
    _raise_for_status_logged(r, "OpenAI-compatible embeddings")
    data = r.json()
    vecs = [item["embedding"] for item in sorted(data["data"], key=lambda x: x["index"])]
    usage = _norm_embed_usage(data.get("usage") or {})
    log.info("EMBEDDING USAGE (openai): total=%s", usage["total_tokens"])
    return vecs, usage


def _azure_embed(texts: List[str]) -> Tuple[List[List[float]], Dict]:
    if not (AZURE_ENDPOINT and AZURE_EMBED_DEPLOYMENT and AZURE_API_KEY):
        raise RuntimeError("Azure embeddings not configured")
    url = f"{AZURE_ENDPOINT}/openai/deployments/{AZURE_EMBED_DEPLOYMENT}/embeddings?api-version={AZURE_API_VERSION}"
    headers = {"api-key": AZURE_API_KEY, "Content-Type": "application/json"}
    r = requests.post(url, headers=headers, json={"input": texts}, timeout=90)
    _raise_for_status_logged(r, "Azure embeddings")
    data = r.json()
    vecs = [item["embedding"] for item in sorted(data["data"], key=lambda x: x["index"])]
    usage = _norm_embed_usage(data.get("usage") or {})
    log.info("EMBEDDING USAGE (azure): total=%s", usage["total_tokens"])
    return vecs, usage


def _gemini_embed(texts: List[str]) -> Tuple[List[List[float]], Dict]:
    if not GEMINI_API_KEY:
        raise RuntimeError("Gemini embeddings not configured (GEMINI_API_KEY missing)")
    model_path = f"models/{GEMINI_EMBED_MODEL}"
    url = f"{GEMINI_BASE_URL}/{model_path}:batchEmbedContents?key={GEMINI_API_KEY}"
    body = {"requests": [{"model": model_path, "content": {"parts": [{"text": t}]}} for t in texts]}
    r = requests.post(url, json=body, timeout=90)
    _raise_for_status_logged(r, "Gemini embeddings")
    data = r.json()
    vecs = [e["values"] for e in data.get("embeddings", [])]
    # Gemini's embedContent API does not report token usage.
    usage = {"prompt_tokens": 0, "total_tokens": 0, "raw": {}}
    return vecs, usage


def _anthropic_embed(texts: List[str]) -> Tuple[List[List[float]], Dict]:
    raise RuntimeError(
        "Anthropic has no embeddings API. Set EMBED_PROVIDER to 'openai', 'azure', or 'gemini'."
    )


_EMBED_DISPATCH = {
    "azure": _azure_embed,
    "openai": _openai_embed,
    "gemini": _gemini_embed,
    "anthropic": _anthropic_embed,
}


@retry(wait=wait_exponential(min=1, max=20), stop=stop_after_attempt(6))
def embed_texts(texts: List[str]) -> Tuple[List[List[float]], Dict]:
    fn = _EMBED_DISPATCH.get(EMBED_PROVIDER)
    if not fn:
        raise RuntimeError(f"Unsupported EMBED_PROVIDER: {EMBED_PROVIDER}")
    return fn(texts)


def embed_text(text: str) -> Tuple[List[float], Dict]:
    vecs, usage = embed_texts([text])
    return vecs[0], usage


# --------------------- Vision captioning ---------------------
def _openai_style_vision_payload(system_prompt: str, user_prompt: str, b64_png: str, max_tokens: int = 80) -> Dict:
    return {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": [
                {"type": "text", "text": user_prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64_png}"}},
            ]},
        ],
        "temperature": 0.0,
        "max_tokens": max_tokens,
    }


def _azure_vision_caption(image_path: str, system_prompt: str, user_prompt: str) -> str:
    if not (AZURE_ENDPOINT and AZURE_API_KEY and AZURE_VISION_DEPLOYMENT):
        raise RuntimeError("Azure vision not configured")
    b64 = _b64_file(image_path)
    url = f"{AZURE_ENDPOINT}/openai/deployments/{AZURE_VISION_DEPLOYMENT}/chat/completions?api-version={AZURE_API_VERSION}"
    headers = {"api-key": AZURE_API_KEY, "Content-Type": "application/json"}
    r = requests.post(url, headers=headers, json=_openai_style_vision_payload(system_prompt, user_prompt, b64), timeout=60)
    _raise_for_status_logged(r, "Azure vision")
    return (r.json()["choices"][0]["message"]["content"] or "").strip()


def _openai_vision_caption(image_path: str, system_prompt: str, user_prompt: str) -> str:
    if not OPENAI_API_KEY:
        raise RuntimeError("OpenAI-compatible vision not configured (OPENAI_API_KEY missing)")
    b64 = _b64_file(image_path)
    url = f"{OPENAI_BASE_URL}/chat/completions"
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
    payload = _openai_style_vision_payload(system_prompt, user_prompt, b64)
    payload["model"] = OPENAI_VISION_MODEL
    r = requests.post(url, headers=headers, json=payload, timeout=60)
    _raise_for_status_logged(r, "OpenAI-compatible vision")
    return (r.json()["choices"][0]["message"]["content"] or "").strip()


def _anthropic_vision_caption(image_path: str, system_prompt: str, user_prompt: str) -> str:
    if not ANTHROPIC_API_KEY:
        raise RuntimeError("Anthropic vision not configured (ANTHROPIC_API_KEY missing)")
    b64 = _b64_file(image_path)
    url = f"{ANTHROPIC_BASE_URL}/v1/messages"
    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": ANTHROPIC_API_VERSION,
        "Content-Type": "application/json",
    }
    body = {
        "model": ANTHROPIC_CHAT_MODEL,
        "max_tokens": 80,
        "system": system_prompt,
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": user_prompt},
            {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": b64}},
        ]}],
    }
    r = requests.post(url, headers=headers, json=body, timeout=60)
    _raise_for_status_logged(r, "Anthropic vision")
    data = r.json()
    return "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text").strip()


def _gemini_vision_caption(image_path: str, system_prompt: str, user_prompt: str) -> str:
    if not GEMINI_API_KEY:
        raise RuntimeError("Gemini vision not configured (GEMINI_API_KEY missing)")
    b64 = _b64_file(image_path)
    url = f"{GEMINI_BASE_URL}/models/{GEMINI_CHAT_MODEL}:generateContent?key={GEMINI_API_KEY}"
    body = {
        "contents": [{"role": "user", "parts": [
            {"text": user_prompt},
            {"inline_data": {"mime_type": "image/png", "data": b64}},
        ]}],
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "generationConfig": {"temperature": 0.0, "maxOutputTokens": 80},
    }
    r = requests.post(url, json=body, timeout=60)
    _raise_for_status_logged(r, "Gemini vision")
    data = r.json()
    candidates = data.get("candidates") or []
    parts = candidates[0].get("content", {}).get("parts", []) if candidates else []
    return "".join(p.get("text", "") for p in parts).strip()


_VISION_DISPATCH = {
    "azure": _azure_vision_caption,
    "openai": _openai_vision_caption,
    "anthropic": _anthropic_vision_caption,
    "gemini": _gemini_vision_caption,
}


def caption_image(image_path: str, system_prompt: str, user_prompt: str) -> Optional[str]:
    """Returns a caption, or None if the active provider's vision call is unavailable/fails.

    Callers are expected to fall back to a filename-derived caption on None,
    matching the previous Azure-only behavior.
    """
    fn = _VISION_DISPATCH.get(LLM_PROVIDER)
    if not fn:
        return None
    try:
        caption = fn(image_path, system_prompt, user_prompt)
        return re.sub(r"\s+", " ", caption).strip() or None
    except Exception as e:
        log.warning("Vision caption via %s failed: %s", LLM_PROVIDER, e)
        return None
