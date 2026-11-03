"""Cache disque des réponses LLM validées."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

CACHE_PATH = Path("data/cache/llm_cache.json")


def cle_cache(modele: str, version_prompt: str, entree: str, schema: str = "") -> str:
    """Calcule une clé SHA-256 stable pour le cache."""
    contenu = "\0".join([modele, version_prompt, schema, entree])
    return hashlib.sha256(contenu.encode("utf-8")).hexdigest()


class CacheDisque:
    """Petit cache JSON, écrit de façon atomique."""

    def __init__(self, chemin: str | Path = CACHE_PATH):
        self.chemin = Path(chemin)

    def lire(self, cle: str) -> Any | None:
        """Retourne la valeur associée à la clé, ou None si absente."""
        return self._charger().get(cle)

    def ecrire(self, cle: str, valeur: Any) -> None:
        """Enregistre une valeur et remplace le fichier atomiquement."""
        donnees = self._charger()
        donnees[cle] = valeur
        self.chemin.parent.mkdir(parents=True, exist_ok=True)
        temporaire = self.chemin.with_name(self.chemin.name + ".tmp")
        with open(temporaire, "w", encoding="utf-8") as fichier:
            json.dump(donnees, fichier, ensure_ascii=False, indent=1)
        os.replace(temporaire, self.chemin)

    def _charger(self) -> dict:
        try:
            with open(self.chemin, encoding="utf-8") as fichier:
                donnees = json.load(fichier)
            return donnees if isinstance(donnees, dict) else {}
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return {}
