#!/usr/bin/env python3
"""Affiche l'état de la base Neo4j JuriGraph (lecture seule)."""
import argparse
import os
from pathlib import Path

ENV_PATH = Path(__file__).resolve().parent / ".env"
try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=ENV_PATH)
except ImportError:
    pass

REQUETES = [
    ("Articles", "MATCH (a:Article) RETURN count(a) AS n"),
    ("Articles avec embedding", "MATCH (a:Article) WHERE a.embedding IS NOT NULL RETURN count(a) AS n"),
    ("Relations RENVOIE_A", "MATCH ()-[r:RENVOIE_A]->() RETURN count(r) AS n"),
]

LABELS_COMPTES = [
    ("Infractions", "Infraction"),
    ("Peines", "Peine"),
    ("Extractions", "Extraction"),
]


def afficher_plan() -> None:
    """Décrit les lectures prévues sans se connecter à Neo4j."""
    print("Mode --dry-run : aucune connexion à Neo4j, aucune écriture.")
    print(f"URI prévue : {os.environ.get('NEO4J_URI', 'bolt://localhost:7687')}")
    print(f"Base prévue : {os.environ.get('NEO4J_DATABASE', 'neo4j')}")
    print("Lectures prévues :")
    for libelle, _ in REQUETES:
        print(f"  - {libelle}")
    for libelle, _ in LABELS_COMPTES:
        print(f"  - {libelle} (0 si le label n'existe pas)")
    print("  - index : name, type, state, options (analyseur de article_texte)")


def connecter():
    """Ouvre une connexion Neo4j ou retourne None avec un message clair."""
    from neo4j import GraphDatabase
    uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    user = os.environ.get("NEO4J_USER", "neo4j")
    password = os.environ.get("NEO4J_PASSWORD")
    if not password:
        print("ERREUR : NEO4J_PASSWORD est absente (fichier .env).")
        return None
    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))
        driver.verify_connectivity()
        return driver
    except Exception as exc:
        print(f"ERREUR : Neo4j est injoignable sur {uri} : {exc}")
        print("Démarrez Neo4j puis relancez le script.")
        return None


def compter(driver, requete: str, database: str) -> int:
    """Exécute une requête de comptage et retourne le résultat."""
    records, _, _ = driver.execute_query(requete, database=database)
    return records[0]["n"]


def compter_label(driver, label: str, database: str, labels_existants: set[str]) -> int:
    """Compte les nœuds d'un label, ou retourne 0 s'il n'existe pas."""
    if label not in labels_existants:
        return 0
    return compter(driver, f"MATCH (n:{label}) RETURN count(n) AS n", database)


def afficher_index(driver, database: str) -> None:
    """Affiche les index et l'analyseur de l'index plein texte."""
    records, _, _ = driver.execute_query(
        "SHOW INDEXES YIELD name, type, state, options RETURN name, type, state, options",
        database=database,
    )
    print("\nIndex :")
    for r in records:
        options = r["options"] or {}
        ligne = f"- {r['name']} | type={r['type']} | state={r['state']}"
        if r["name"] == "article_texte":
            analyseur = (options.get("indexConfig") or {}).get("fulltext.analyzer")
            ligne += f" | analyseur={analyseur}"
        print(ligne)


def main() -> int:
    """Point d'entrée : affiche l'état de la base ou le plan du dry-run."""
    parser = argparse.ArgumentParser(description="État de la base Neo4j JuriGraph (lecture seule).")
    parser.add_argument("--dry-run", action="store_true", help="affiche le plan sans se connecter")
    args = parser.parse_args()
    if args.dry_run:
        afficher_plan()
        return 0
    driver = connecter()
    if driver is None:
        return 1
    database = os.environ.get("NEO4J_DATABASE", "neo4j")
    try:
        print("=== État de la base Neo4j ===")
        for libelle, requete in REQUETES:
            print(f"{libelle} : {compter(driver, requete, database)}")
        labels_existants = {
            r["label"]
            for r in driver.execute_query("CALL db.labels() YIELD label RETURN label", database=database)[0]
        }
        for libelle, label in LABELS_COMPTES:
            print(f"{libelle} : {compter_label(driver, label, database, labels_existants)}")
        afficher_index(driver, database)
    except Exception as exc:
        print(f"ERREUR pendant la lecture : {exc}")
        return 1
    finally:
        driver.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
