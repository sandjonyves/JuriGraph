"""Fournisseurs d'embeddings interchangeables.

Changer de modèle sans toucher au pipeline, via l'environnement (.env) ou la CLI :

    # Gemini (défaut)
    EMBEDDING_PROVIDER=gemini
    EMBEDDING_MODEL=gemini-embedding-001
    EMBEDDING_DIM=768

    # Serveur local compatible OpenAI (Ollama, vLLM, LM Studio...)
    EMBEDDING_PROVIDER=openai
    EMBEDDING_MODEL=nomic-embed-text
    EMBEDDING_DIM=768
    EMBEDDING_BASE_URL=http://localhost:11434/v1

    # OpenRouter (passerelle multi-modèles)
    EMBEDDING_PROVIDER=openrouter
    OPENROUTER_API_KEY=sk-or-v1-...
    EMBEDDING_MODEL=openai/text-embedding-3-small
    EMBEDDING_DIM=1536

Ajouter un fournisseur :
    1. créer ``embeddings/<nom>.py`` avec une sous-classe de ``BaseEmbedder``
       qui définit ``name``, ``default_model``, ``default_dim``, ``max_chars``
       et implémente ``_embed_batch(texts, kind)`` ;
    2. l'enregistrer dans ``PROVIDERS`` ci-dessous.
"""
from __future__ import annotations

import os

from .base import BaseEmbedder, EmbeddingError, chunks, normalize
from .gemini import GeminiEmbedder
from .openai_compat import OpenAICompatibleEmbedder
from .openrouter import OpenRouterEmbedder

PROVIDERS: dict[str, type[BaseEmbedder]] = {
    "gemini": GeminiEmbedder,
    "openrouter": OpenRouterEmbedder,
    "openai": OpenAICompatibleEmbedder,
}


def create_embedder(provider: str | None = None, model: str | None = None,
                    dim: int | None = None, **kwargs) -> BaseEmbedder:
    """Construit le fournisseur demandé (CLI > environnement > défaut).

    Ne fait aucun appel réseau : la connexion est établie au premier embedding,
    ce qui permet d'utiliser --dry-run sans clé API.
    """
    name = (provider or os.environ.get("EMBEDDING_PROVIDER") or "gemini").strip().lower()
    try:
        factory = PROVIDERS[name]
    except KeyError:
        raise SystemExit(
            f"Fournisseur d'embeddings inconnu : {name!r}. "
            f"Disponibles : {', '.join(sorted(PROVIDERS))}.") from None

    model = model or os.environ.get("EMBEDDING_MODEL") or None
    dim = dim or os.environ.get("EMBEDDING_DIM") or None
    return factory(model=model, dim=dim, **kwargs)


__all__ = [
    "BaseEmbedder", "EmbeddingError", "GeminiEmbedder", "OpenAICompatibleEmbedder",
    "OpenRouterEmbedder", "PROVIDERS", "chunks", "create_embedder", "normalize",
]
