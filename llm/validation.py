"""Génération JSON validée, cache disque et journal des appels LLM."""
from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, ValidationError

from .base import BaseChat, ChatResult
from .cache import CacheDisque, cle_cache

LOG_PATH = Path("data/logs/llm_runs.jsonl")


class LLMValidationError(RuntimeError):
    """La réponse du LLM reste invalide après les tentatives de réparation."""


@dataclass
class ValidatedResult:
    """Réponse validée et métadonnées d'usage."""

    data: BaseModel
    text: str
    tokens_in: int = 0
    tokens_out: int = 0
    cached: bool = False


def nettoyer_json(texte: str) -> str:
    """Retire les balises Markdown ```json ... ``` encadrant un JSON."""
    texte = texte.strip().lstrip("\ufeff")
    bloc = re.search(r"```[A-Za-z0-9_-]*\s*(.*?)```", texte, re.S)
    if bloc:
        texte = bloc.group(1)
    return texte.strip()


def _parser_et_valider(texte: str, modele: type[BaseModel]) -> BaseModel:
    """Parse le JSON nettoyé et le valide avec le modèle pydantic."""
    donnees = json.loads(nettoyer_json(texte))
    return modele.model_validate(donnees)


def _cout(tokens_in: int, tokens_out: int) -> float | None:
    """Estime le coût à partir des tarifs éventuels du .env."""
    entree = os.environ.get("LLM_COST_INPUT_PER_MILLION")
    sortie = os.environ.get("LLM_COST_OUTPUT_PER_MILLION")
    if entree is None or sortie is None:
        return None
    try:
        return ((tokens_in / 1_000_000) * float(entree)
                + (tokens_out / 1_000_000) * float(sortie))
    except ValueError:
        return None


def _journaliser(chemin: Path, chat: BaseChat, resultat: ChatResult, duree: float,
                 cache_hit: bool, tentatives: int, schema: str) -> None:
    """Ajoute une ligne JSONL, sans jamais écrire la clé API."""
    chemin.parent.mkdir(parents=True, exist_ok=True)
    ligne = {
        "date": datetime.now(timezone.utc).isoformat(),
        "provider": chat.name,
        "model": chat.model,
        "schema": schema,
        "tokens_in": resultat.tokens_in,
        "tokens_out": resultat.tokens_out,
        "cout_estime": _cout(resultat.tokens_in, resultat.tokens_out),
        "duree_s": round(duree, 3),
        "cache_hit": cache_hit,
        "tentatives": tentatives,
    }
    with open(chemin, "a", encoding="utf-8") as fichier:
        fichier.write(json.dumps(ligne, ensure_ascii=False) + "\n")


def generate_validated(chat: BaseChat, system: str, user: str,
                       model_pydantic: type[BaseModel], max_repairs: int = 1,
                       *, cache: CacheDisque | None = None,
                       cache_path: str | Path | None = None,
                       log_path: str | Path | None = None,
                       prompt_version: str = "") -> ValidatedResult:
    """Génère, nettoie, valide et met en cache une réponse JSON.

    ``prompt_version`` et le texte du prompt système composent la version de
    prompt utilisée dans la clé de cache. Le cache est actif par défaut.
    """
    cache = cache or CacheDisque(cache_path or "data/cache/llm_cache.json")
    journal = Path(log_path or LOG_PATH)
    version = f"{prompt_version}\n{system}" if prompt_version else system
    schema_nom = model_pydantic.__name__
    cle = cle_cache(chat.model, version, user, schema_nom)

    debut = time.monotonic()
    valeur = cache.lire(cle)
    if valeur is not None:
        try:
            data = model_pydantic.model_validate(valeur)
            resultat = ChatResult(text=data.model_dump_json())
            _journaliser(journal, chat, resultat, time.monotonic() - debut,
                         True, 0, schema_nom)
            return ValidatedResult(data=data, text=resultat.text, cached=True)
        except ValidationError:
            pass  # cache provenant d'un ancien schéma : on recalcule

    schema_json = model_pydantic.model_json_schema()
    tokens_in = 0
    tokens_out = 0
    tentatives = 0
    dernier_texte = ""
    derniere_erreur: Exception | None = None

    for tentative in range(max_repairs + 1):
        if tentative == 0:
            demande = user
        else:
            demande = (
                f"{user}\n\nRéponse précédente :\n{dernier_texte}\n\n"
                f"Erreur de validation : {derniere_erreur}\n"
                "Corrige la réponse et renvoie uniquement le JSON valide, sans balises."
            )
        resultat = chat.generate(system, demande, schema=schema_json)
        tentatives += 1
        tokens_in += resultat.tokens_in
        tokens_out += resultat.tokens_out
        dernier_texte = resultat.text
        try:
            data = _parser_et_valider(dernier_texte, model_pydantic)
        except (json.JSONDecodeError, ValidationError) as exc:
            derniere_erreur = exc
            if tentative < max_repairs:
                continue
        else:
            cache.ecrire(cle, data.model_dump(mode="json"))
            total = ChatResult(text=dernier_texte, tokens_in=tokens_in,
                               tokens_out=tokens_out)
            _journaliser(journal, chat, total, time.monotonic() - debut,
                         False, tentatives, schema_nom)
            return ValidatedResult(data=data, text=dernier_texte,
                                   tokens_in=tokens_in, tokens_out=tokens_out)

    total = ChatResult(text=dernier_texte, tokens_in=tokens_in, tokens_out=tokens_out)
    _journaliser(journal, chat, total, time.monotonic() - debut,
                 False, tentatives, schema_nom)
    raise LLMValidationError(
        f"réponse invalide après {tentatives} tentative(s) : {derniere_erreur}")
