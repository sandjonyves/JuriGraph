#!/usr/bin/env python3
"""Évaluation de la recherche hybride sur le jeu « faits → articles ».

Mesure Recall@5, Recall@10, MRR et nDCG@10 pour plusieurs configurations
(ablations), règle les paramètres sur le split ``dev`` uniquement, puis
rapporte le split ``test`` avec intervalles de confiance (bootstrap) et un
test de permutation apparié contre la voie vectorielle seule.

Les scénarios sans article attendu (« sans infraction ») sont exclus des
métriques : ils relèvent de l'abstention, évaluée en phase 3.

Usage :
    python evaluate_search.py --dry-run
    python evaluate_search.py                     # ablations + réglage + test
    python evaluate_search.py --sans-reglage
"""
from __future__ import annotations

import argparse
import itertools
import json
import math
import random
import statistics
import sys
import time
from dataclasses import asdict, replace
from datetime import date
from pathlib import Path

from search_hybrid import Config, decouper_requetes

RACINE = Path(__file__).resolve().parent
SCENARIOS = RACINE / "data/eval/faits_articles.jsonl"
SORTIE = RACINE / "data/reports"
PROFONDEUR_EVAL = 20
GRAINE = 42

ABLATIONS = {
    "V": Config(plein_texte=False, renvois=False, section=False),
    "PT": Config(vecteur=False, renvois=False, section=False),
    "V+PT": Config(renvois=False, section=False),
    "V+PT+R": Config(section=False),
    "V+PT+S": Config(renvois=False),
    "V+PT+R+S": Config(),
    "V+PT+MQ": Config(renvois=False, section=False, multi_requetes=True),
    "V+PT+R+S+MQ": Config(multi_requetes=True),
}
GRILLE = {"k_rrf": [10, 30, 60], "poids_graphe": [0.25, 0.5, 1.0], "profondeur": [10, 20, 30]}


# --------------------------------------------------------------- métriques

def rappel(attendus: list[str], classement: list[str], k: int) -> float:
    """Part des articles attendus présents dans les k premiers."""
    return len(set(attendus) & set(classement[:k])) / len(attendus)


def rang_reciproque(attendus: list[str], classement: list[str]) -> float:
    """1 / rang du premier article attendu (0 s'il est absent)."""
    for rang, numero in enumerate(classement, 1):
        if numero in attendus:
            return 1.0 / rang
    return 0.0


def ndcg(attendus: list[str], acceptables: list[str], classement: list[str], k: int = 10) -> float:
    """nDCG@k : gain 1 pour un attendu, 0,5 pour un acceptable."""
    def gain(numero: str) -> float:
        return 1.0 if numero in attendus else 0.5 if numero in acceptables else 0.0

    dcg = sum(gain(n) / math.log2(i + 1) for i, n in enumerate(classement[:k], 1))
    ideal = sorted([1.0] * len(attendus) + [0.5] * len(acceptables), reverse=True)[:k]
    idcg = sum(g / math.log2(i + 1) for i, g in enumerate(ideal, 1))
    return dcg / idcg if idcg else 0.0


def mesurer(scenario: dict, classement: list[str]) -> dict[str, float]:
    """Toutes les métriques d'un scénario."""
    att, acc = scenario["attendus"], scenario["acceptables"]
    return {"R@5": rappel(att, classement, 5), "R@10": rappel(att, classement, 10),
            "MRR": rang_reciproque(att, classement), "nDCG@10": ndcg(att, acc, classement)}


def moyenne(valeurs: list[float]) -> float:
    """Moyenne (0 pour une liste vide)."""
    return sum(valeurs) / len(valeurs) if valeurs else 0.0


def bootstrap(valeurs: list[float], tirages: int = 2000, graine: int = GRAINE) -> tuple[float, float]:
    """Intervalle de confiance à 95 % de la moyenne (percentiles du bootstrap)."""
    if not valeurs:
        return (0.0, 0.0)
    alea = random.Random(graine)
    moyennes = sorted(moyenne([alea.choice(valeurs) for _ in valeurs]) for _ in range(tirages))
    return moyennes[int(0.025 * tirages)], moyennes[int(0.975 * tirages) - 1]


def permutation_appariee(a: list[float], b: list[float], tirages: int = 10000,
                         graine: int = GRAINE) -> float:
    """p-valeur bilatérale d'un test de permutation par inversion de signe."""
    diffs = [x - y for x, y in zip(a, b)]
    observe = abs(sum(diffs))
    if observe == 0:
        return 1.0
    alea = random.Random(graine)
    extremes = sum(abs(sum(d if alea.random() < 0.5 else -d for d in diffs)) >= observe - 1e-12
                   for _ in range(tirages))
    return (extremes + 1) / (tirages + 1)


def agreger(lignes: list[dict[str, float]]) -> dict[str, float]:
    """Moyenne de chaque métrique sur un ensemble de scénarios."""
    return {m: moyenne([ligne[m] for ligne in lignes]) for m in ("R@5", "R@10", "MRR", "nDCG@10")}


def choisir_meilleur(resultats: dict[str, dict[str, float]]) -> str:
    """Configuration au meilleur R@10, départagée par le MRR puis le nom."""
    return min(resultats, key=lambda c: (-resultats[c]["R@10"], -resultats[c]["MRR"], c))


# --------------------------------------------------------------- exécution

def charger(chemin: Path) -> list[dict]:
    """Scénarios évaluables (au moins un article attendu)."""
    tous = [json.loads(ligne) for ligne in chemin.read_text(encoding="utf-8").splitlines()
            if ligne.strip()]
    return [s for s in tous if s["attendus"]]


def evaluer(moteur, scenarios: list[dict], config: Config) -> tuple[list[dict], float]:
    """Lance une configuration ; renvoie les lignes par scénario et la latence médiane (ms)."""
    lignes, durees = [], []
    for sc in scenarios:
        debut = time.perf_counter()
        resultats = moteur.rechercher(sc["faits"], PROFONDEUR_EVAL, config)
        durees.append((time.perf_counter() - debut) * 1000)
        classement = [r.numero for r in resultats]
        lignes.append({"id": sc["id"], "categorie": sc["categorie"], "classement": classement[:10],
                       "sources": {r.numero: r.sources for r in resultats[:10]},
                       **mesurer(sc, classement)})
    return lignes, statistics.median(durees)


def prechauffer(moteur, scenarios: list[dict]) -> None:
    """Calcule à l'avance les vecteurs de toutes les requêtes (latence mesurée sans réseau)."""
    textes = {t for s in scenarios for t in decouper_requetes(s["faits"])}
    for i, texte in enumerate(sorted(textes), 1):
        moteur._vecteur(texte)
        print(f"\rEmbeddings des requêtes : {i}/{len(textes)}", end="", flush=True)
    print()


def regler(moteur, dev: list[dict], base: Config) -> tuple[Config, list[dict]]:
    """Recherche en grille sur le split dev ; renvoie la meilleure configuration."""
    essais = []
    for k_rrf, poids, prof in itertools.product(*GRILLE.values()):
        cfg = replace(base, k_rrf=k_rrf, poids_graphe=poids, profondeur=prof)
        lignes, _ = evaluer(moteur, dev, cfg)
        essais.append({"k_rrf": k_rrf, "poids_graphe": poids, "profondeur": prof, **agreger(lignes)})
    meilleur = min(essais, key=lambda e: (-e["R@10"], -e["MRR"], e["k_rrf"], e["poids_graphe"],
                                          e["profondeur"]))
    return replace(base, k_rrf=meilleur["k_rrf"], poids_graphe=meilleur["poids_graphe"],
                   profondeur=meilleur["profondeur"]), essais


def tableau(titre: str, resultats: dict[str, dict], n: int) -> list[str]:
    """Tableau Markdown d'une série de configurations."""
    lignes = [f"### {titre} (n = {n})", "",
              "| Configuration | R@5 | R@10 | MRR | nDCG@10 | IC95 R@10 | p (vs V, R@10) | Latence (ms) |",
              "|---|---:|---:|---:|---:|---|---:|---:|"]
    for nom, r in resultats.items():
        lignes.append(f"| {nom} | {r['R@5']:.3f} | {r['R@10']:.3f} | {r['MRR']:.3f} | "
                      f"{r['nDCG@10']:.3f} | [{r['ic_R@10'][0]:.2f} ; {r['ic_R@10'][1]:.2f}] | "
                      f"{r['p_R@10']:.3f} | {r['latence']:.0f} |")
    return lignes + [""]


def serie(moteur, scenarios: list[dict], configs: dict[str, Config]) -> tuple[dict, dict]:
    """Évalue plusieurs configurations sur les mêmes scénarios, avec statistiques."""
    resultats, details = {}, {}
    for nom, cfg in configs.items():
        lignes, latence = evaluer(moteur, scenarios, cfg)
        details[nom] = lignes
        resultats[nom] = {**agreger(lignes), "latence": latence,
                          "ic_R@10": bootstrap([x["R@10"] for x in lignes]),
                          "ic_MRR": bootstrap([x["MRR"] for x in lignes])}
    reference = details.get("V")
    for nom, mesures in resultats.items():
        if reference is not None:
            mesures["p_R@10"] = permutation_appariee(
                [x["R@10"] for x in details[nom]], [x["R@10"] for x in reference])
            mesures["p_MRR"] = permutation_appariee(
                [x["MRR"] for x in details[nom]], [x["MRR"] for x in reference])
        else:
            mesures["p_R@10"] = mesures["p_MRR"] = float("nan")
    return resultats, details


def main() -> int:
    """Point d'entrée."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--scenarios", default=str(SCENARIOS))
    parser.add_argument("--sans-reglage", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    scenarios = charger(Path(args.scenarios))
    dev = [s for s in scenarios if s["split"] == "dev"]
    test = [s for s in scenarios if s["split"] == "test"]
    print(f"Scénarios évaluables : {len(scenarios)} (dev {len(dev)}, test {len(test)})")
    if args.dry_run:
        print("Configurations :", ", ".join(ABLATIONS))
        print("Grille de réglage :", GRILLE)
        return 0

    from search_hybrid import construire
    moteur, driver = construire()
    try:
        prechauffer(moteur, scenarios)
        res_dev, det_dev = serie(moteur, dev, ABLATIONS)
        res_test, det_test = serie(moteur, test, ABLATIONS)
        rapport = {"date": date.today().isoformat(), "statut": "provisoire_jeu_non_valide",
                   "n_dev": len(dev), "n_test": len(test),
                   "ablations": {"dev": res_dev, "test": res_test},
                   "details": {"dev": det_dev, "test": det_test}}
        md = ["# Évaluation de la recherche hybride", "",
              f"Date : {rapport['date']} — **PROVISOIRE : jeu de scénarios non validé**", "",
              "Paramètres par défaut : " + json.dumps(
                  {k: v for k, v in asdict(Config()).items()
                   if k in ("profondeur", "graines", "k_rrf", "poids_graphe", "max_voisins")}), "",
              *tableau("Ablations — dev", res_dev, len(dev)),
              *tableau("Ablations — test", res_test, len(test))]

        if not args.sans_reglage:
            meilleure = choisir_meilleur(res_dev)
            cfg_reglee, essais = regler(moteur, dev, ABLATIONS[meilleure])
            res_final, det_final = serie(moteur, test, {"V": ABLATIONS["V"],
                                                        f"{meilleure} (défaut)": ABLATIONS[meilleure],
                                                        f"{meilleure} (réglée)": cfg_reglee})
            rapport["reglage"] = {"base": meilleure, "config": asdict(cfg_reglee), "essais": essais,
                                  "test": res_final, "details_test": det_final}
            md += [f"## Réglage sur dev de « {meilleure} »", "",
                   (f"Meilleurs paramètres : k_rrf = {cfg_reglee.k_rrf}, poids_graphe = "
                    f"{cfg_reglee.poids_graphe}, profondeur = {cfg_reglee.profondeur}"), "",
                   *tableau("Mesure finale — test", res_final, len(test))]
    finally:
        driver.close()

    SORTIE.mkdir(parents=True, exist_ok=True)
    (SORTIE / "eval_recherche.json").write_text(
        json.dumps(rapport, ensure_ascii=False, indent=1), encoding="utf-8")
    (SORTIE / "eval_recherche.md").write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md))
    print(f"Résultats : {SORTIE / 'eval_recherche.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
