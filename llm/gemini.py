"""Fournisseur Google Gemini pour le chat."""
from __future__ import annotations

import os
from typing import Any

from .base import BaseChat, ChatError, ChatResult

TRANSIENT_CODES = {408, 409, 429, 500, 502, 503, 504}


class GeminiChat(BaseChat):
    """Client Gemini via google-genai."""

    name = "gemini"

    def __init__(self, model: str, api_key: str | None = None, **kwargs):
        super().__init__(model=model, api_key=api_key, **kwargs)
        self.api_key = (self.api_key or os.environ.get("GEMINI_API_KEY")
                        or os.environ.get("LLM_API_KEY"))
        self._client = None
        self._types = None

    def _ensure_client(self):
        """Connexion paresseuse : un --dry-run ne nécessite pas de clé API."""
        if self._client is not None:
            return
        if not self.api_key:
            raise ChatError(
                "GEMINI_API_KEY manquante (clé gratuite : https://aistudio.google.com/apikey).",
                transient=False)
        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:
            raise ChatError(
                "google-genai n'est pas installé : pip install google-genai",
                transient=False) from exc
        self._client = genai.Client(api_key=self.api_key)
        self._types = types

    def _generate(self, system: str, user: str, schema: Any = None) -> ChatResult:
        self._ensure_client()
        options = {
            "system_instruction": system,
            "temperature": self.temperature,
        }
        if schema is not None:
            options["response_mime_type"] = "application/json"
        config = self._types.GenerateContentConfig(**options)
        try:
            response = self._client.models.generate_content(
                model=self.model, contents=user, config=config)
        except Exception as exc:
            code = getattr(exc, "code", None)
            raise ChatError(
                f"gemini {code if code is not None else type(exc).__name__}: {str(exc)[:200]}",
                transient=code is None or code in TRANSIENT_CODES) from exc

        usage = getattr(response, "usage_metadata", None)
        return ChatResult(
            text=getattr(response, "text", None) or "",
            tokens_in=int(getattr(usage, "prompt_token_count", 0) or 0) if usage else 0,
            tokens_out=int(getattr(usage, "candidates_token_count", 0) or 0) if usage else 0,
        )
