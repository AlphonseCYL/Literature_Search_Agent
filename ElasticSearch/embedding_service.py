from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None

from sentence_transformers import SentenceTransformer

if load_dotenv:
    load_dotenv()


EMBEDDING_MODEL_NAME = (
    os.getenv("ES_TEXT_EMBEDDING_MODEL_ID")
    or os.getenv("TEXT_EMBEDDING_MODEL")
    or "paraphrase-multilingual-MiniLM-L12-v2"
).strip()
EMBEDDING_DIMS = int(os.getenv("ES_TEXT_EMBEDDING_DIMS", "384"))


def normalize_embedding_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


@lru_cache(maxsize=1)
def get_embedding_model() -> SentenceTransformer:
    return SentenceTransformer(EMBEDDING_MODEL_NAME)


def embed_text(text: Any) -> list[float]:
    normalized_text = normalize_embedding_text(text)
    if not normalized_text:
        return [0.0] * EMBEDDING_DIMS

    vector = get_embedding_model().encode(
        normalized_text,
        normalize_embeddings=True,
    )
    return vector.astype(float).tolist()


def embed_literature_fields(title: Any, snippet: Any) -> dict[str, list[float]]:
    return {
        "title_embedding": embed_text(title),
        "snippet_embedding": embed_text(snippet),
    }
