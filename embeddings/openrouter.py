"""Fournisseur OpenRouter (passerelle multi-modèles, endpoint compatible OpenAI).

    EMBEDDING_PROVIDER=openrouter
    OPENROUTER_API_KEY=sk-or-v1-...
    EMBEDDING_MODEL=openai/text-embedding-3-small
    EMBEDDING_DIM=1536

Le catalogue d'embeddings est distinct du catalogue de chat :
    curl https://openrouter.ai/api/v1/embeddings/models \\
         -H "Authorization: Bearer $OPENROUTER_API_KEY"

Deux options sont désactivées par défaut, car tous les modèles ne les acceptent pas :
    OPENROUTER_DIMENSIONS=1   # envoie {"dimensions": EMBEDDING_DIM} (réduction de dimension)
    OPENROUTER_INPUT_TYPE=1   # envoie search_document / search_query (modèles de retrieval)
"""
from __future__ import annotations

import os
from typing import Sequence

from .base import EmbeddingError
from .openai_compat import OpenAICompatibleEmbedder


def _flag(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class OpenRouterEmbedder(OpenAICompatibleEmbedder):
    name = "openrouter"
    default_model = "openai/text-embedding-3-small"
    default_dim = 1536
    max_chars = 8000

    def __init__(self, model: str | None = None, dim: int | None = None,
                 api_key: str | None = None, base_url: str | None = None,
                 site_url: str | None = None, app_name: str | None = None,
                 send_dimensions: bool | None = None,
                 input_type: bool | None = None, **kwargs):
        super().__init__(
            model=model, dim=dim,
            api_key=api_key or os.environ.get("OPENROUTER_API_KEY"),
            base_url=base_url or os.environ.get("OPENROUTER_BASE_URL")
            or "https://openrouter.ai/api/v1",
            **kwargs)
        self.site_url = site_url or os.environ.get("OPENROUTER_SITE_URL")
        self.app_name = app_name or os.environ.get("OPENROUTER_APP_NAME") or "JuriGraph"
        self.send_dimensions = (_flag("OPENROUTER_DIMENSIONS")
                                if send_dimensions is None else send_dimensions)
        self.send_input_type = (_flag("OPENROUTER_INPUT_TYPE")
                                if input_type is None else input_type)

    def _headers(self) -> dict[str, str]:
        if not self.api_key:
            raise EmbeddingError(
                "OPENROUTER_API_KEY manquante (clé sur https://openrouter.ai/keys).")
        headers = super()._headers()
        headers["X-Title"] = self.app_name
        if self.site_url:
            headers["HTTP-Referer"] = self.site_url
        return headers

    def _payload(self, texts: Sequence[str], kind: str) -> dict:
        payload = super()._payload(texts, kind)
        if self.send_dimensions:
            payload["dimensions"] = self.dim
        if self.send_input_type:
            payload["input_type"] = ("search_document" if kind == "document"
                                     else "search_query")
        return payload
