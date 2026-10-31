"""Fournisseur générique « API compatible OpenAI » (/v1/embeddings).

Fonctionne avec Ollama, vLLM, LM Studio, llama.cpp, OpenAI, Mistral, etc.
Aucune dépendance externe : utilise la bibliothèque standard.

Exemples :
    Ollama       EMBEDDING_BASE_URL=http://localhost:11434/v1  EMBEDDING_MODEL=nomic-embed-text
    vLLM         EMBEDDING_BASE_URL=http://localhost:8000/v1   EMBEDDING_MODEL=BAAI/bge-m3
    OpenAI       EMBEDDING_BASE_URL=https://api.openai.com/v1  EMBEDDING_MODEL=text-embedding-3-small
                 (OPENAI_API_KEY requis)
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Sequence

from .base import BaseEmbedder, EmbeddingError, Vector

TRANSIENT_CODES = {408, 409, 429, 500, 502, 503, 504, 529}


class OpenAICompatibleEmbedder(BaseEmbedder):
    name = "openai"
    default_model = "nomic-embed-text"
    default_dim = 768
    max_chars = 8000

    def __init__(self, model: str | None = None, dim: int | None = None,
                 api_key: str | None = None, base_url: str | None = None,
                 timeout: float = 60.0, **kwargs):
        super().__init__(model=model, dim=dim, **kwargs)
        self.base_url = (base_url or os.environ.get("EMBEDDING_BASE_URL")
                         or "http://localhost:11434/v1").rstrip("/")
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.timeout = float(timeout)

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _payload(self, texts: Sequence[str], kind: str) -> dict:
        return {"model": self.model, "input": list(texts)}

    def _embed_batch(self, texts: Sequence[str], kind: str) -> list[Vector]:
        payload = json.dumps(self._payload(texts, kind)).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}/embeddings", data=payload, method="POST",
            headers=self._headers())
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                data = json.load(response)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")[:200]
            raise EmbeddingError(
                f"{self.name} {exc.code} ({self.base_url}) : {body}",
                transient=exc.code in TRANSIENT_CODES) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise EmbeddingError(
                f"{self.name} injoignable ({self.base_url}) : {exc}", transient=True) from exc

        try:
            rows = sorted(data["data"], key=lambda r: r.get("index", 0))
            return [list(r["embedding"]) for r in rows]
        except (KeyError, TypeError) as exc:
            raise EmbeddingError(
                f"réponse inattendue de {self.base_url} : {str(data)[:200]}") from exc
