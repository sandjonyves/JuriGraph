"""Contrôle hors ligne du jeu d'évaluation « faits → articles ».

Vérifie que chaque article attendu ou acceptable existe et n'est ni abrogé ni
une plage, compte les scénarios par split et par catégorie, et mesure le
recouvrement lexical entre les faits et le texte des articles attendus : un
recouvrement élevé signale un scénario qui recopie la loi (biais en faveur du
plein texte). Peut générer la grille de relecture humaine.

Usage :
    python scripts/verifier_gold_set.py
    python scripts/verifier_gold_set.py --grille data/eval/grille_relecture_scenarios.csv
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
SEUIL_RECOUVREMENT = 0.5
LONGUEUR_RACINE = 6
MOTS_VIDES = {"a", "à", "au", "aux", "avec", "ce", "ces", "cet", "cette", "d", "de", "des", "du", "elle", "elles", "en", "est", "et", "etre", "eu", "il", "ils", "je", "l", "la", "le", "les", "leur", "leurs", "lui", "m", "ma", "mais", "me", "meme", "mes", "mon", "n", "ne", "ni", "nos", "notre", "nous", "on", "ou", "où", "par", "pas", "pour", "qu", "que", "qui", "s", "sa", "sans", "se", "ses", "si", "son", "sont", "sur", "t", "ta", "te", "tes", "ton", "tu", "un", "une", "vos", "votre", "vous", "y", "ont", "ete", "etait", "avait", "apres", "plus", "tout", "tous", "toute", "toutes", "dont", "lors", "puis", "deja", "chez", "sous", "entre", "comme", "fait", "faire"}


def normaliser(texte: str) -> str:
    """Minuscules, sans accents, apostrophes et ponctuation remplacées par des espaces."""
    texte = unicodedata.normalize("NFKD", texte.lower())
    texte = "".join(c for c in texte if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", texte)


def racines(texte: str) -> set[str]:
    """Ensemble des racines (préfixes) des mots pleins d'un texte."""
    return {mot[:LONGUEUR_RACINE] for mot in normaliser(texte).split()
            if len(mot) > 2 and mot not in MOTS_VIDES and not mot.isdigit()}


def recouvrement_lexical(faits: str, article: str) -> float:
    """Part des racines des faits présentes dans le texte de l'article."""
    rf = racines(faits)
    return len(rf & racines(article)) / len(rf) if rf else 0.0


def est_plage(numero: str) -> bool:
    """Vrai pour une plage d'articles (« 362-370 »), faux pour « 18-1 »."""
    morceaux = numero.split("-")
    return (len(morceaux) == 2 and all(m.isdigit() for m in morceaux)
            and int(morceaux[1]) > int(morceaux[0]))


def charger_articles(chemin: Path) -> dict[str, dict]:
    """Indexe les articles du corpus par numéro, avec texte complet."""
    donnees = json.loads(chemin.read_text(encoding="utf-8"))
    articles: dict[str, dict] = {}

    def parcourir(noeud: dict) -> None:
        for art in noeud.get("articles", []):
            alineas = " ".join(al.get("texte", "") for al in art.get("alineas", []))
            articles[str(art["numero"])] = {
                "titre": art.get("titre") or "",
                "texte": f"{art.get('texte_brut') or ''} {alineas}".strip(),
                "abroge": bool(art.get("abroge")),
                "est_plage": est_plage(str(art["numero"])),
            }
        for cle, valeur in noeud.items():
            if isinstance(valeur, list) and cle not in ("articles", "alineas"):
                for enfant in valeur:
                    if isinstance(enfant, dict):
                        parcourir(enfant)

    for livre in donnees["livres"]:
        parcourir(livre)
    return articles


def charger_scenarios(chemin: Path) -> list[dict]:
    """Lit le fichier JSONL des scénarios."""
    return [json.loads(ligne) for ligne in chemin.read_text(encoding="utf-8").splitlines()
            if ligne.strip()]


def controler(scenarios: list[dict], articles: dict[str, dict]) -> tuple[list[str], list[dict]]:
    """Renvoie les erreurs bloquantes et une ligne de mesure par scénario."""
    erreurs, mesures, ids = [], [], set()
    for sc in scenarios:
        if sc["id"] in ids:
            erreurs.append(f"{sc['id']} : identifiant en double")
        ids.add(sc["id"])
        if sc.get("split") not in ("dev", "test"):
            erreurs.append(f"{sc['id']} : split invalide {sc.get('split')!r}")
        if set(sc["attendus"]) & set(sc["acceptables"]):
            erreurs.append(f"{sc['id']} : article à la fois attendu et acceptable")
        for num in sc["attendus"] + sc["acceptables"]:
            art = articles.get(num)
            if art is None:
                erreurs.append(f"{sc['id']} : article {num} inexistant")
            elif art["abroge"] or art["est_plage"]:
                erreurs.append(f"{sc['id']} : article {num} abrogé ou plage")
        scores = [recouvrement_lexical(sc["faits"], articles[n]["texte"])
                  for n in sc["attendus"] if n in articles]
        mesures.append({"id": sc["id"], "recouvrement": max(scores) if scores else None})
    return erreurs, mesures


def ecrire_grille(chemin: Path, scenarios: list[dict], articles: dict[str, dict]) -> None:
    """Écrit la grille CSV de relecture humaine."""
    def libelle(nums: list[str]) -> str:
        return " ; ".join(f"{n} ({articles[n]['titre']})" for n in nums if n in articles)

    with chemin.open("w", encoding="utf-8", newline="") as f:
        ecrivain = csv.writer(f)
        ecrivain.writerow(["id", "split", "categorie", "faits", "attendus", "acceptables",
                           "decision (garder/modifier/rejeter)", "attendus_corriges",
                           "acceptables_corriges", "commentaire"])
        for sc in scenarios:
            ecrivain.writerow([sc["id"], sc["split"], sc["categorie"], sc["faits"],
                               libelle(sc["attendus"]), libelle(sc["acceptables"]),
                               "", "", "", ""])


def main() -> int:
    """Point d'entrée."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--scenarios", default=str(RACINE / "data/eval/faits_articles.jsonl"))
    parser.add_argument("--corpus", default=str(RACINE / "code_penal_structure_docx.json"))
    parser.add_argument("--grille", help="chemin de la grille CSV à générer")
    args = parser.parse_args()

    articles = charger_articles(Path(args.corpus))
    scenarios = charger_scenarios(Path(args.scenarios))
    erreurs, mesures = controler(scenarios, articles)

    print(f"Scénarios : {len(scenarios)}")
    print("Par split :", dict(Counter(s["split"] for s in scenarios)))
    print("Par catégorie :", dict(Counter(s["categorie"] for s in scenarios)))
    valeurs = sorted(m["recouvrement"] for m in mesures if m["recouvrement"] is not None)
    if valeurs:
        print(f"Recouvrement lexical faits/article attendu : min {valeurs[0]:.2f}, "
              f"médiane {valeurs[len(valeurs) // 2]:.2f}, max {valeurs[-1]:.2f}")
    trop = [m["id"] for m in mesures
            if m["recouvrement"] is not None and m["recouvrement"] > SEUIL_RECOUVREMENT]
    print(f"Scénarios au-dessus du seuil {SEUIL_RECOUVREMENT} : {trop or 'aucun'}")
    for e in erreurs:
        print("ERREUR :", e)
    if args.grille:
        ecrire_grille(Path(args.grille), scenarios, articles)
        print(f"Grille écrite : {args.grille}")
    return 1 if erreurs else 0


if __name__ == "__main__":
    sys.exit(main())
