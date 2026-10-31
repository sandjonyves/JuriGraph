"""Fournisseur Google Gemini (offre gratuite : https://aistudio.google.com/apikey)."""
from __future__ import annotations

import os
from typing import Sequence

from .base import BaseEmbedder, EmbeddingError, Vector

TRANSIENT_CODES = {408, 409, 429, 500, 502, 503, 504}
TASKS = {"document": "RETRIEVAL_DOCUMENT", "query": "RETRIEVAL_QUERY"}


class GeminiEmbedder(BaseEmbedder):
    name = "gemini"
    default_model = "gemini-embedding-001"
    default_dim = 768
    max_chars = 6000                 # ~2048 tokens

    def __init__(self, model: str | None = None, dim: int | None = None,
                 api_key: str | None = None, **kwargs):
        super().__init__(model=model, dim=dim, **kwargs)
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self._client = None
        self._types = None

    def _ensure_client(self):
        """Connexion paresseuse : un --dry-run ne nécessite pas de clé API."""
        if self._client is not None:
            return
        if not self.api_key:
            raise EmbeddingError(
                "GEMINI_API_KEY manquante (clé gratuite : https://aistudio.google.com/apikey).")
        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:
            raise EmbeddingError("google-genai n'est pas installé : pip install google-genai") from exc
        self._client = genai.Client(api_key=self.api_key)
        self._types = types

    def _embed_batch(self, texts: Sequence[str], kind: str) -> list[Vector]:
        self._ensure_client()
        try:
            response = self._client.models.embed_content(
                model=self.model,
                contents=texts,
                config=self._types.EmbedContentConfig(
                    task_type=TASKS[kind], output_dimensionality=self.dim))
        except Exception as exc:
            code = getattr(exc, "code", None)
            raise EmbeddingError(
                f"gemini {code if code is not None else type(exc).__name__}: {str(exc)[:140]}",
                transient=code is None or code in TRANSIENT_CODES) from exc
        return [list(e.values) for e in (response.embeddings or [])]
