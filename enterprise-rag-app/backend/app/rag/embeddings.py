"""OpenAI embedding and vision-captioning calls."""

import base64

from openai import OpenAI


def embed_texts(client: OpenAI, texts: list[str], model: str, batch_size: int = 100) -> list[list[float]]:
    if not texts:
        return []
    vectors: list[list[float]] = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        response = client.embeddings.create(model=model, input=batch)
        vectors.extend(item.embedding for item in response.data)
    return vectors


CAPTION_PROMPT = (
    "Describe this image in 1-3 sentences, focused on any factual content that would help "
    "answer questions about it - labeled diagrams, charts, tables, or text visible in the "
    "image. If it's purely decorative (a logo, icon, divider, background pattern), reply "
    "with exactly: DECORATIVE"
)


def caption_image(client: OpenAI, image_bytes: bytes, model: str) -> str | None:
    """Ask a vision-capable model to describe an extracted PDF image.

    Returns None for decorative images (so they don't get indexed as noise)
    or if the call fails for any reason - a bad caption shouldn't abort the
    whole ingestion run.
    """
    b64 = base64.b64encode(image_bytes).decode("ascii")
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": CAPTION_PROMPT},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                    ],
                }
            ],
            max_tokens=200,
        )
        caption = (response.choices[0].message.content or "").strip()
    except Exception:
        return None

    if not caption or caption.upper().startswith("DECORATIVE"):
        return None
    return caption
