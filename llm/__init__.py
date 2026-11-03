"""Fournisseurs de chat interchangeables.

Changer de modèle sans toucher au pipeline, via l'environnement (.env) ou la CLI :

    LLM_PROVIDER=openrouter
    LLM_MODEL=<identifiant du modèle>
    OPENROUTER_API_KEY=...

    LLM_PROVIDER=ollama
    LLM_MODEL=<identifiant du modèle>
    LLM_BASE_URL=http://localhost:11434/v1

    LLM_PROVIDER=gemini
    LLM_MODEL=<identifiant du modèle>
    GEMINI_API_KEY=...

Ajouter un fournisseur :
    1. créer ``llm/<nom>.py`` avec une sous-classe de ``BaseChat``
       qui implémente ``_generate(system, user, schema)`` ;
    2. l'enregistrer dans ``PROVIDERS`` ci-dessous.
"""
from __future__ import annotations

import os

from .base import BaseChat, ChatError, ChatResult
from .cache import CacheDisque, cle_cache
from .gemini import GeminiChat
from .openai_compat import OllamaChat, OpenAIChat, OpenRouterChat
from .validation import LLMValidationError, ValidatedResult, generate_validated

PROVIDERS: dict[str, type[BaseChat]] = {
    "openrouter": OpenRouterChat,
    "openai": OpenAIChat,
    "ollama": OllamaChat,
    "gemini": GeminiChat,
}


def create_chat(provider: str | None = None, model: str | None = None,
                **kwargs) -> BaseChat:
    """Construit le fournisseur demandé (CLI > environnement).

    Aucun nom de modèle n'est codé en dur : ``LLM_MODEL`` doit être renseigné.
    """
    name = (provider or os.environ.get("LLM_PROVIDER") or "").strip().lower()
    if not name:
        raise SystemExit(
            "LLM_PROVIDER est vide : renseignez-le dans .env "
            f"(disponibles : {', '.join(sorted(PROVIDERS))}).")
    try:
        factory = PROVIDERS[name]
    except KeyError:
        raise SystemExit(
            f"Fournisseur de chat inconnu : {name!r}. "
            f"Disponibles : {', '.join(sorted(PROVIDERS))}.") from None

    model = (model or os.environ.get("LLM_MODEL") or "").strip()
    if not model:
        raise SystemExit(
            "LLM_MODEL est vide : renseignez le modèle dans .env "
            "ou passez --model.")
    return factory(model=model, **kwargs)


__all__ = [
    "BaseChat", "CacheDisque", "ChatError", "ChatResult", "GeminiChat",
    "LLMValidationError", "OllamaChat", "OpenAIChat", "OpenRouterChat",
    "PROVIDERS", "ValidatedResult", "cle_cache", "create_chat",
    "generate_validated",
]
