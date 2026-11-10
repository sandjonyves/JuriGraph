#!/usr/bin/env python3
"""Extrait les fiches Infraction / Peine d'un ou plusieurs articles.

Le modèle et le fournisseur viennent de l'environnement (.env) :

    LLM_PROVIDER=openrouter
    LLM_MODEL=<identifiant du modèle>
    OPENROUTER_API_KEY=...

Usage :
    python extract_infractions.py --dry-run --numero 275
    python extract_infractions.py --numero 275
    python extract_infractions.py --limit 5
    python extract_infractions.py --run          # tous les articles extractibles

``--dry-run`` ne fait aucun appel API et n'écrit rien. Sans ``--dry-run``,
``--numero`` ou ``--limit`` lance une extraction réelle ; ``--run`` lance le
corpus complet et n'est jamais implicite.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent
sys.path.insert(0, str(RACINE))

ENV_PATH = RACINE / ".env"
try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=ENV_PATH)
except ImportError:
    pass

from llm import (  # noqa: E402
    ChatError,
    LLMValidationError,
    create_chat,
    generate_validated,
)
from load_neo4j import build_rows  # noqa: E402
from schemas.extraction import Fiche  # noqa: E402
from verify_extraction import verifier  # noqa: E402

CORPUS_PATH = RACINE / "code_penal_structure_docx.json"
PROMPT_PATH = RACINE / "prompts/extraction_v4.md"
CACHE_PATH = RACINE / "data/cache/llm_cache.json"
LOG_PATH = RACINE / "data/logs/llm_runs.jsonl"
PROMPT_VERSION = "extraction_v4"


def _livres_par_article(data: dict) -> dict[str, str]:
    """Associe chaque numéro d'article au numéro de son Livre."""
    livres: dict[str, str] = {}
    for livre in data.get("livres", []):
        numero_livre = str(livre.get("numero") or "")
        for titre in livre.get("titres", []):
            for chapitre in titre.get("chapitres", []):
                for article in chapitre.get("articles", []):
                    livres[str(article["numero"])] = numero_livre
                for section in chapitre.get("sections", []):
                    for article in section.get("articles", []):
                        livres[str(article["numero"])] = numero_livre
    return livres


def charger_articles(chemin: Path = CORPUS_PATH) -> tuple[list[dict], set[str]]:
    """Charge les articles et retourne aussi tous les numéros existants."""
    with open(chemin, encoding="utf-8") as fichier:
        data = json.load(fichier)
    nodes, _ = build_rows(data)
    livres = _livres_par_article(data)
    articles = nodes["Article"]
    for article in articles:
        article["livre"] = livres.get(str(article["numero"]))
    return articles, {str(article["numero"]) for article in articles}


def articles_extractibles(articles: list[dict]) -> list[dict]:
    """Retourne les articles à extraire (hors article 1, abrogés et plages)."""
    return [
        article for article in articles
        if str(article.get("numero")) != "1"
        and not article.get("abroge")
        and not article.get("est_plage")
        and (article.get("texte_complet") or article.get("texte_brut") or "").strip()
    ]


def selectionner_articles(articles: list[dict], numero: str | None = None,
                          limit: int | None = None,
                          run: bool = False) -> list[dict]:
    """Sélectionne un article, les N premiers, ou tout le corpus."""
    if numero is not None:
        for article in articles:
            if str(article["numero"]) == str(numero):
                return [article]
        raise ValueError(f"Article {numero!r} introuvable ou non extractible.")
    if limit is not None:
        if limit <= 0:
            raise ValueError("--limit doit être strictement positif.")
        return articles[:limit]
    if run:
        return articles
    raise ValueError("Précisez --numero, --limit ou --run.")


def construire_message(article: dict) -> str:
    """Construit le message utilisateur contenant le texte exact de l'article."""
    titre = article.get("titre") or "(sans titre)"
    texte = article.get("texte_complet") or article.get("texte_brut") or ""
    return (
        "Extrais la fiche de l'article ci-dessous. "
        "Réponds uniquement avec le JSON.\n\n"
        f"Article {article['numero']} — {titre}\n{texte}"
    )


def charger_prompt() -> str:
    """Lit le prompt d'extraction versionné."""
    texte = PROMPT_PATH.read_text(encoding="utf-8")
    if not texte.strip():
        raise SystemExit(f"Prompt vide : {PROMPT_PATH}")
    return texte


def verifier_configuration_llm() -> None:
    """Vérifie que le fournisseur, le modèle et la clé sont configurés."""
    provider = (os.environ.get("LLM_PROVIDER") or "").strip().lower()
    modele = (os.environ.get("LLM_MODEL") or "").strip()
    manquants: list[str] = []
    if not provider:
        manquants.append("LLM_PROVIDER")
    if not modele:
        manquants.append("LLM_MODEL")
    if provider == "openrouter" and not os.environ.get("OPENROUTER_API_KEY"):
        manquants.append("OPENROUTER_API_KEY")
    elif provider == "gemini" and not (
            os.environ.get("GEMINI_API_KEY") or os.environ.get("LLM_API_KEY")):
        manquants.append("GEMINI_API_KEY ou LLM_API_KEY")
    elif provider == "openai" and not (
            os.environ.get("LLM_API_KEY") or os.environ.get("OPENAI_API_KEY")):
        manquants.append("LLM_API_KEY ou OPENAI_API_KEY")
    if manquants:
        raise SystemExit(
            "Configuration LLM incomplète : " + ", ".join(manquants)
            + ". Renseignez .env puis relancez.")


def extraire_article(article: dict, chat, prompt: str, existants: set[str],
                     cache_path: Path = CACHE_PATH,
                     log_path: Path = LOG_PATH) -> tuple[Fiche, dict, bool]:
    """Extrait, valide et vérifie la fiche d'un article."""
    resultat = generate_validated(
        chat,
        prompt,
        construire_message(article),
        Fiche,
        cache_path=cache_path,
        log_path=log_path,
        prompt_version=PROMPT_VERSION,
    )
    fiche = resultat.data
    if not isinstance(fiche, Fiche):
        fiche = Fiche.model_validate(fiche)
    verification = verifier(fiche, article, existants)
    return fiche, verification, resultat.cached


def afficher_fiche(fiche: Fiche, verification: dict, cache_hit: bool = False) -> None:
    """Affiche la fiche complète et son statut de vérification."""
    suffixe = " (cache)" if cache_hit else ""
    print(f"\n=== Article {fiche.article} ===")
    print(f"Statut : {verification['statut']}{suffixe}")
    if verification["erreurs"]:
        print("Erreurs :")
        for erreur in verification["erreurs"]:
            print(f"  - {erreur}")
    print(json.dumps(fiche.model_dump(mode="json"), ensure_ascii=False, indent=2))


def main() -> int:
    """Point d'entrée : dry-run, sélection partielle ou corpus complet."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="aucun appel API, aucune écriture")
    choix = parser.add_mutually_exclusive_group()
    choix.add_argument("--numero", help="extraire un seul article")
    choix.add_argument("--limit", type=int,
                       help="extraire les N premiers articles")
    choix.add_argument("--run", action="store_true",
                       help="extraire tous les articles extractibles")
    args = parser.parse_args()

    articles, existants = charger_articles()
    extractibles = articles_extractibles(articles)

    try:
        selection = selectionner_articles(
            extractibles, numero=args.numero, limit=args.limit, run=args.run)
    except ValueError as exc:
        parser.error(str(exc))

    if not selection and not args.dry_run:
        parser.error("Précisez --numero, --limit ou --run.")

    if args.dry_run:
        print("Mode --dry-run : aucun appel API, aucune écriture.")
        print(f"Articles extractibles : {len(extractibles)} / {len(articles)}.")
        if not selection:
            print("Aucune sélection : utilisez --numero, --limit ou --run.")
            return 0
        if args.run:
            numeros = [str(article["numero"]) for article in selection]
            print(f"{len(selection)} articles seraient traités (--run).")
            print("Premiers numéros : " + ", ".join(numeros[:12]))
            return 0
        prompt = charger_prompt()
        print(f"Prompt : {PROMPT_PATH} ({len(prompt)} caractères).")
        for article in selection:
            texte = article.get("texte_complet") or article.get("texte_brut") or ""
            titre = article.get("titre") or "(sans titre)"
            print(f"\n=== Article {article['numero']} — {titre} ===")
            print(f"Livre : {article.get('livre') or '?'}")
            print(f"Texte ({len(texte)} caractères) :")
            print(texte)
        return 0

    verifier_configuration_llm()
    chat = create_chat()
    prompt = charger_prompt()
    print(f"Modèle : {chat.signature} — prompt {PROMPT_VERSION}")
    print(f"{len(selection)} article(s) à extraire.")

    statuts: dict[str, int] = {}
    echecs = 0
    for article in selection:
        try:
            fiche, verification, cache_hit = extraire_article(
                article, chat, prompt, existants)
        except (ChatError, LLMValidationError) as exc:
            print(f"\n=== Article {article['numero']} ===\nÉchec : {exc}")
            echecs += 1
            continue
        afficher_fiche(fiche, verification, cache_hit)
        statut = verification["statut"]
        statuts[statut] = statuts.get(statut, 0) + 1

    print(f"\nRésumé : {len(selection) - echecs} fiche(s) affichée(s), "
          f"{echecs} échec(s).")
    for statut in sorted(statuts):
        print(f"  {statut} : {statuts[statut]}")
    return 1 if echecs else 0


if __name__ == "__main__":
    raise SystemExit(main())
