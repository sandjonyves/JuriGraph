"""Contrat commun aux fournisseurs de chat (LLM).

Un fournisseur n'a qu'une méthode à implémenter : ``_generate(system, user, schema)``.
Les nouvelles tentatives sur erreurs transitoires sont mutualisées ici.
"""
from __future__ import annotations

import abc
import random
import time
from dataclasses import dataclass
from typing import Any


class ChatError(RuntimeError):
    """Erreur d'un fournisseur de chat.

    transient=True  -> nouvelle tentative utile (quota, réseau, 5xx)
    transient=False -> erreur définitive (clé invalide, modèle inconnu...)
    """

    def __init__(self, message: str, transient: bool = False):
        super().__init__(message)
        self.transient = transient


@dataclass
class ChatResult:
    """Réponse texte d'un modèle et consommation de tokens."""

    text: str
    tokens_in: int = 0
    tokens_out: int = 0


class BaseChat(abc.ABC):
    """Interface minimale d'un fournisseur de chat."""

    name = "base"
    max_retries = 6
    base_delay = 5.0                 # backoff exponentiel : 5, 10, 20, ... secondes
    max_delay = 120.0
    jitter = 1.0

    def __init__(self, model: str, api_key: str | None = None,
                 base_url: str | None = None, timeout: float = 120.0,
                 temperature: float = 0.0, max_retries: int | None = None,
                 base_delay: float | None = None, max_delay: float | None = None,
                 jitter: float | None = None):
        self.model = model
        self.api_key = api_key
        self.base_url = base_url
        self.timeout = float(timeout)
        self.temperature = float(temperature)
        if max_retries is not None:
            self.max_retries = int(max_retries)
        if base_delay is not None:
            self.base_delay = float(base_delay)
        if max_delay is not None:
            self.max_delay = float(max_delay)
        if jitter is not None:
            self.jitter = float(jitter)

    @property
    def signature(self) -> str:
        """Identité du modèle : sert de version au cache disque."""
        return f"{self.name}:{self.model}"

    def generate(self, system: str, user: str, schema: Any = None) -> ChatResult:
        """Envoie un prompt et retourne le texte, avec nouvelles tentatives."""
        for attempt in range(self.max_retries):
            try:
                return self._generate(system, user, schema)
            except ChatError as exc:
                if not exc.transient or attempt == self.max_retries - 1:
                    raise
                delay = min(self.max_delay, self.base_delay * 2 ** attempt)
                delay += random.uniform(0, self.jitter)
                print(f"  {self.name}: {exc} — nouvelle tentative dans {delay:.0f}s")
                time.sleep(delay)
        raise ChatError("Échec inattendu")  # pragma: no cover

    @abc.abstractmethod
    def _generate(self, system: str, user: str, schema: Any = None) -> ChatResult:
        """Exécute un appel unique. Lever ``ChatError(..., transient=...)``."""
