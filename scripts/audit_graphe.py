"""Audit en lecture seule du graphe Neo4j avant la recherche hybride.

Vérifie que les renvois en base correspondent exactement à ``renvois.json``,
décrit la hiérarchie, et teste le comportement de l'index plein texte
(accents, pluriels). Aucune écriture n'est faite dans Neo4j.

Usage :
    python scripts/audit_graphe.py              # audit complet
    python scripts/audit_graphe.py --dry-run    # affiche le plan sans se connecter
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
REQUETES_ACCENTS = [("delit", "délit"), ("meurtre", "meurtres"),
                    ("evasion", "évasion"), ("vol", "vols")]


def charger_renvois(chemin: Path) -> set[tuple[str, str]]:
    """Lit renvois.json et renvoie l'ensemble des paires (source, cible)."""
    donnees = json.loads(chemin.read_text(encoding="utf-8"))
    return {(str(r["source"]), str(r["cible"])) for r in donnees}


def comparer_paires(fichier: set[tuple[str, str]],
                    base: set[tuple[str, str]]) -> dict[str, list]:
    """Compare deux ensembles de renvois et liste les écarts."""
    return {"absents_en_base": sorted(fichier - base),
            "en_trop_en_base": sorted(base - fichier)}


def recouvrement(a: list[str], b: list[str]) -> float:
    """Indice de Jaccard entre deux listes de résultats."""
    sa, sb = set(a), set(b)
    return len(sa & sb) / len(sa | sb) if sa | sb else 1.0


def _paires_en_base(session) -> set[tuple[str, str]]:
    """Lit les relations RENVOIE_A en base."""
    res = session.run("MATCH (a:Article)-[:RENVOIE_A]->(b:Article) "
                      "RETURN a.numero AS s, b.numero AS c")
    return {(str(r["s"]), str(r["c"])) for r in res}


def _plein_texte(session, requete: str, k: int = 10) -> list[str]:
    """Renvoie les identifiants des k premiers articles pour une requête."""
    res = session.run("CALL db.index.fulltext.queryNodes('article_texte', $q) "
                      "YIELD node, score RETURN node.id AS id LIMIT $k",
                      q=requete, k=k)
    return [r["id"] for r in res]


def _hierarchie(session) -> list[tuple[str, int]]:
    """Compte les nœuds par label de la hiérarchie."""
    sortie = []
    for label in ("Code", "Livre", "Titre", "Chapitre", "Section", "Article", "Alinea"):
        n = session.run(f"MATCH (n:{label}) RETURN count(n) AS n").single()["n"]
        sortie.append((label, n))
    return sortie


def _articles_sans_parent(session) -> int:
    """Compte les articles qui ne sont rattachés à aucun parent."""
    return session.run("MATCH (a:Article) WHERE NOT ()-[:CONTIENT]->(a) "
                       "RETURN count(a) AS n").single()["n"]


def _taille_sections(session) -> list[int]:
    """Nombre d'articles par parent direct d'article."""
    res = session.run("MATCH (p)-[:CONTIENT]->(a:Article) "
                      "WITH p, count(a) AS n RETURN n ORDER BY n")
    return [r["n"] for r in res]


def _version(session) -> str:
    """Version du serveur Neo4j."""
    r = session.run("CALL dbms.components() YIELD versions "
                    "RETURN versions[0] AS v LIMIT 1").single()
    return r["v"]


def auditer(driver, database: str, renvois: set[tuple[str, str]]) -> int:
    """Lance l'audit et affiche le rapport ; renvoie le code de sortie."""
    with driver.session(database=database) as s:
        print(f"Version Neo4j : {_version(s)}")
        print("\n== Hiérarchie ==")
        for label, n in _hierarchie(s):
            print(f"{label:9s} {n}")
        print(f"Articles sans parent : {_articles_sans_parent(s)}")
        tailles = _taille_sections(s)
        print(f"Parents d'articles : {len(tailles)} ; articles par parent : "
              f"min {tailles[0]}, médiane {tailles[len(tailles) // 2]}, max {tailles[-1]}")

        print("\n== Renvois ==")
        base = _paires_en_base(s)
        ecarts = comparer_paires(renvois, base)
        print(f"renvois.json : {len(renvois)} ; en base : {len(base)}")
        print(f"Absents en base : {len(ecarts['absents_en_base'])} ; "
              f"en trop en base : {len(ecarts['en_trop_en_base'])}")
        for cle, liste in ecarts.items():
            if liste:
                print(f"  {cle} (10 premiers) : {liste[:10]}")

        print("\n== Plein texte : accents et pluriels (top 10) ==")
        for a, b in REQUETES_ACCENTS:
            ra, rb = _plein_texte(s, a), _plein_texte(s, b)
            print(f"{a!r:12s} -> {len(ra):2d} rés. | {b!r:12s} -> {len(rb):2d} rés. | "
                  f"Jaccard = {recouvrement(ra, rb):.2f}")
    return 0 if not any(ecarts.values()) else 1


def main() -> int:
    """Point d'entrée."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true",
                        help="affiche le plan sans se connecter")
    parser.add_argument("--renvois", default=str(RACINE / "renvois.json"))
    args = parser.parse_args()
    renvois = charger_renvois(Path(args.renvois))
    if args.dry_run:
        print(f"[dry-run] {len(renvois)} renvois à comparer ; "
              f"{len(REQUETES_ACCENTS)} paires de requêtes plein texte. Aucune connexion.")
        return 0

    from dotenv import load_dotenv
    from neo4j import GraphDatabase
    load_dotenv(RACINE / ".env")
    mdp = os.environ.get("NEO4J_PASSWORD")
    if not mdp:
        print("NEO4J_PASSWORD absent : renseignez .env", file=sys.stderr)
        return 2
    driver = GraphDatabase.driver(os.environ.get("NEO4J_URI", "bolt://localhost:7687"),
                                  auth=(os.environ.get("NEO4J_USER", "neo4j"), mdp),
                                  notifications_min_severity="OFF")
    try:
        return auditer(driver, os.environ.get("NEO4J_DATABASE", "neo4j"), renvois)
    finally:
        driver.close()


if __name__ == "__main__":
    sys.exit(main())
