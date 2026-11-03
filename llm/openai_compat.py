"""Fournisseurs de chat compatibles OpenAI (/chat/completions).

Fonctionne avec OpenRouter, Ollama, vLLM, LM Studio, OpenAI, etc.
Aucune dépendance externe : utilise la bibliothèque standard.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

from .base import BaseChat, ChatError, ChatResult

TRANSIENT_CODES = {408, 409, 429, 500, 502, 503, 504, 529}


class OpenAICompatibleChat(BaseChat):
    """Client générique pour une API de chat compatible OpenAI."""

    name = "openai"

    def __init__(self, model: str, api_key: str | None = None,
                 base_url: str | None = None, **kwargs):
        super().__init__(model=model, api_key=api_key, base_url=base_url, **kwargs)
        self.base_url = (self.base_url or os.environ.get("LLM_BASE_URL")
                         or "http://localhost:11434/v1").rstrip("/")

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _payload(self, system: str, user: str, schema: Any) -> dict:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": self.temperature,
        }
        if schema is not None:
            payload["response_format"] = {"type": "json_object"}
        return payload

    def _generate(self, system: str, user: str, schema: Any = None) -> ChatResult:
        payload = json.dumps(self._payload(system, user, schema)).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions", data=payload, method="POST",
            headers=self._headers())
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                data = json.load(response)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")[:300]
            raise ChatError(
                f"{self.name} {exc.code} ({self.base_url}) : {body}",
                transient=exc.code in TRANSIENT_CODES) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise ChatError(
                f"{self.name} injoignable ({self.base_url}) : {exc}", transient=True) from exc

        try:
            text = data["choices"][0]["message"]["content"] or ""
            usage = data.get("usage") or {}
            return ChatResult(
                text=text,
                tokens_in=int(usage.get("prompt_tokens") or 0),
                tokens_out=int(usage.get("completion_tokens") or 0),
            )
        except (KeyError, IndexError, TypeError) as exc:
            raise ChatError(
                f"réponse inattendue de {self.base_url} : {str(data)[:300]}") from exc


class OpenAIChat(OpenAICompatibleChat):
    """API OpenAI officielle."""

    name = "openai"

    def __init__(self, model: str, api_key: str | None = None,
                 base_url: str | None = None, **kwargs):
        super().__init__(
            model=model,
            api_key=api_key or os.environ.get("LLM_API_KEY") or os.environ.get("OPENAI_API_KEY"),
            base_url=base_url or os.environ.get("LLM_BASE_URL") or "https://api.openai.com/v1",
            **kwargs)


class OllamaChat(OpenAICompatibleChat):
    """Serveur local compatible OpenAI (Ollama, vLLM, LM Studio...)."""

    name = "ollama"

    def __init__(self, model: str, api_key: str | None = None,
                 base_url: str | None = None, **kwargs):
        super().__init__(
            model=model,
            api_key=api_key or os.environ.get("LLM_API_KEY"),
            base_url=base_url or os.environ.get("LLM_BASE_URL") or "http://localhost:11434/v1",
            **kwargs)


class OpenRouterChat(OpenAICompatibleChat):
    """Passerelle OpenRouter (endpoint compatible OpenAI)."""

    name = "openrouter"

    def __init__(self, model: str, api_key: str | None = None,
                 base_url: str | None = None, site_url: str | None = None,
                 app_name: str | None = None, **kwargs):
        super().__init__(
            model=model,
            api_key=api_key or os.environ.get("OPENROUTER_API_KEY"),
            base_url=base_url or os.environ.get("OPENROUTER_BASE_URL")
            or "https://openrouter.ai/api/v1",
            **kwargs)
        self.site_url = site_url or os.environ.get("OPENROUTER_SITE_URL")
        self.app_name = app_name or os.environ.get("OPENROUTER_APP_NAME") or "JuriGraph"

    def _headers(self) -> dict[str, str]:
        if not self.api_key:
            raise ChatError(
                "OPENROUTER_API_KEY manquante (clé sur https://openrouter.ai/keys).",
                transient=False)
        headers = super()._headers()
        headers["X-Title"] = self.app_name
        if self.site_url:
            headers["HTTP-Referer"] = self.site_url
        return headers
