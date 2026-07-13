"""OpenAI embedding calls, batched."""

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
