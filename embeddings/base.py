"""Contrat commun à tous les fournisseurs d'embeddings.

Un fournisseur n'a qu'une méthode à implémenter : ``_embed_batch(texts, kind)``,
où ``kind`` vaut ``"document"`` (indexation) ou ``"query"`` (recherche).
Le découpage en lots, les nouvelles tentatives, la normalisation L2 et la
vérification des dimensions sont mutualisés ici.
"""
from __future__ import annotations

import abc
import math
import random
import time
from typing import Callable, Iterable, Sequence

Vector = list[float]


class EmbeddingError(RuntimeError):
    """Erreur d'un fournisseur d'embeddings.

    transient=True  -> nouvelle tentative utile (quota, réseau, 5xx)
    transient=False -> erreur définitive (clé invalide, modèle inconnu, dimensions...)
    """

    def __init__(self, message: str, transient: bool = False):
        super().__init__(message)
        self.transient = transient


def normalize(vector: Sequence[float]) -> Vector:
    """Ramène un vecteur à la norme 1 (indispensable en cosinus, et requis par
    gemini-embedding-001 en dessous de 3072 dimensions)."""
    norm = math.sqrt(sum(x * x for x in vector)) or 1.0
    return [x / norm for x in vector]


def chunks(items: Sequence, size: int) -> Iterable[Sequence]:
    for start in range(0, len(items), size):
        yield items[start:start + size]


class BaseEmbedder(abc.ABC):
    """Interface minimale : documents (indexation) + requête (recherche).

    Pour ajouter un fournisseur : créer ``embeddings/<nom>.py`` avec une
    sous-classe définissant ``name``, les valeurs par défaut et
    ``_embed_batch``, puis l'enregistrer dans ``embeddings/__init__.py``.
    """

    name = "base"
    default_model = ""
    default_dim = 768
    default_pause = 1.0
    max_chars = 6000                 # taille max du texte envoyé au modèle
    max_retries = 6
    base_delay = 5.0                 # backoff exponentiel : 5, 10, 20, ... secondes
    max_delay = 120.0

    def __init__(self, model: str | None = None, dim: int | None = None,
                 batch_size: int = 20, pause: float | None = None,
                 normalize_vectors: bool = True):
        self.model = model or self.default_model
        self.dim = int(dim or self.default_dim)
        self.batch_size = max(1, int(batch_size))
        self.pause = self.default_pause if pause is None else float(pause)
        self.normalize_vectors = normalize_vectors

    @property
    def signature(self) -> str:
        """Identité de la configuration : sert de version au cache disque."""
        return f"{self.name}:{self.model}:{self.dim}"

    def embed_documents(self, texts: Sequence[str],
                        on_batch: Callable[[int, list[Vector]], None] | None = None) -> list[Vector]:
        """Vectorise des textes par lots. ``on_batch(done, vecteurs)`` est appelé
        après chaque lot réussi : permet de sauvegarder le cache au fil de l'eau."""
        result: list[Vector] = []
        batches = list(chunks(texts, self.batch_size))
        for index, batch in enumerate(batches, 1):
            result.extend(self._embed_batch_retry(batch, "document"))
            if on_batch is not None:
                on_batch(len(result), result)
            if self.pause and index < len(batches):
                time.sleep(self.pause)
        self._check_dimensions(result)
        return result

    def embed_query(self, text: str) -> Vector:
        vector = self._embed_batch_retry([text], "query")[0]
        self._check_dimensions([vector])
        return vector

    def _embed_batch_retry(self, texts: Sequence[str], kind: str) -> list[Vector]:
        for attempt in range(self.max_retries):
            try:
                vectors = self._embed_batch(list(texts), kind)
                if len(vectors) != len(texts):
                    raise EmbeddingError(
                        f"{len(vectors)} vecteurs reçus pour {len(texts)} textes", transient=True)
                return [normalize(v) for v in vectors] if self.normalize_vectors else vectors
            except EmbeddingError as exc:
                if not exc.transient or attempt == self.max_retries - 1:
                    raise
                delay = min(self.max_delay, self.base_delay * 2 ** attempt) + random.uniform(0, 1)
                print(f"  {self.name}: {exc} — nouvelle tentative dans {delay:.0f}s")
                time.sleep(delay)
        raise EmbeddingError("Échec inattendu")  # pragma: no cover

    def _check_dimensions(self, vectors: Sequence[Vector]) -> None:
        for vector in vectors:
            if len(vector) != self.dim:
                raise EmbeddingError(
                    f"{self.model} renvoie {len(vector)} dimensions, {self.dim} attendues "
                    f"(ajuster EMBEDDING_DIM / --dim, ou supprimer l'index vectoriel existant).")

    @abc.abstractmethod
    def _embed_batch(self, texts: Sequence[str], kind: str) -> list[Vector]:
        """Calcule les vecteurs d'un lot. ``kind`` : 'document' ou 'query'.

        En cas d'erreur, lever ``EmbeddingError(..., transient=...)``.
        """
