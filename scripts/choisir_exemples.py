#!/usr/bin/env python3
"""Propose des articles candidats pour les exemples few-shot de l'extraction.

Script jetable : aucune écriture, aucun appel réseau.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from load_neo4j import build_rows


def extrait(texte: str, taille: int = 180) -> str:
    """Retourne un extrait compact du texte de l'article."""
    texte = " ".join((texte or "").split())
    return texte[:taille] + ("…" if len(texte) > taille else "")


def numero_base(numero: str) -> int:
    """Retourne le numéro principal d'un article (ex. '18-1' -> 18)."""
    correspondance = re.match(r"(\d+)", str(numero))
    return int(correspondance.group(1)) if correspondance else 0


def est_livre_ii(article: dict) -> bool:
    """Vrai pour un article du Livre II (à partir de l'article 102)."""
    return numero_base(article.get("numero", "")) >= 102


def est_puni(texte: str) -> bool:
    """Vrai si le texte énonce une sanction pénale."""
    return bool(re.search(r"\bpun(?:i|ie|is|ies)\b|\bpunissable\b", texte.lower()))


def est_peine_simple(texte: str, article: dict) -> bool:
    """Article du Livre II avec une peine sans fourchette, mort, vie ni renvoi."""
    texte = texte.lower()
    if not est_livre_ii(article) or not est_puni(texte):
        return False
    if not ("emprisonnement" in texte or "amende" in texte):
        return False
    if ("emprisonnement" in texte) == ("amende" in texte):
        return False
    if est_fourchette(texte):
        return False
    if "mort" in texte or "à vie" in texte or "perpétuité" in texte:
        return False
    if est_renvoi_peine(texte):
        return False
    return True


def est_fourchette(texte: str, article: dict | None = None) -> bool:
    """Article contenant une fourchette de durée de peine."""
    if article is not None and not est_livre_ii(article):
        return False
    if article is not None and not est_puni(texte):
        return False
    return bool(re.search(
        r"\b(?:de|entre)\s+[^.;]{0,80}?\bà\b[^.;]{0,80}?"
        r"(?:ans?|mois|jours?)\b",
        texte.lower()))


def est_amende_francs(texte: str, article: dict) -> bool:
    """Article du Livre II contenant une amende exprimée en francs."""
    texte = texte.lower()
    return (est_livre_ii(article) and est_puni(texte) and "amende" in texte
            and "fcfa" not in texte and bool(re.search(r"\bfrancs?\b", texte)))


def est_mort_ou_vie(texte: str, article: dict) -> bool:
    """Article du Livre II mentionnant la mort, la perpétuité ou « à vie »."""
    texte = texte.lower()
    return (est_livre_ii(article) and est_puni(texte)
            and ("mort" in texte or "à vie" in texte or "perpétuité" in texte))


def est_renvoi_peine(texte: str, article: dict | None = None) -> bool:
    """Article qui reprend les peines d'un autre article."""
    if article is not None and not est_livre_ii(article):
        return False
    return bool(re.search(r"peines?\s+de\s+l['’]article\s+\d", texte.lower()))


CATEGORIES = [
    ("peine simple", est_peine_simple),
    ("fourchette", est_fourchette),
    ("amende en francs", est_amende_francs),
    ("mort ou à vie", est_mort_ou_vie),
    ("peine par renvoi", est_renvoi_peine),
]


def main() -> None:
    """Affiche trois candidats par catégorie."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("json_path", nargs="?", default="code_penal_structure_docx.json")
    args = parser.parse_args()

    with open(args.json_path, encoding="utf-8") as fichier:
        nodes, _ = build_rows(json.load(fichier))
    articles = [
        a for a in nodes["Article"]
        if a["numero"] != "1" and not a["abroge"] and not a["est_plage"]
        and (a.get("texte_complet") or "").strip()
    ]

    deja: set[str] = set()
    for nom, predicat in CATEGORIES:
        candidats = [a for a in articles
                     if predicat(a.get("texte_complet", ""), a)]
        uniques = [a for a in candidats if a["numero"] not in deja]
        selection = (uniques + [a for a in candidats if a["numero"] in deja])[:3]
        print(f"\n=== {nom} ===")
        for rang, article in enumerate(selection, 1):
            deja.add(article["numero"])
            titre = article.get("titre") or "(sans titre)"
            print(f"  {rang}. Article {article['numero']} — {titre}")
            print(f"     {extrait(article.get('texte_complet', ''))}")

    print("\nChoisissez 5 articles (un par catégorie de préférence).")


if __name__ == "__main__":
    main()
