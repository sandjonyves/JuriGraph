#!/usr/bin/env python3
"""
Charge le JSON du Code pénal (produit par parse_code_penal_docx.py) dans Neo4j.

    pip install neo4j
    python load_neo4j.py code_penal_structure_docx.json
    python load_neo4j.py code_penal_structure_docx.json --dry-run   # sans Neo4j

Le script est rejouable : il utilise MERGE, donc relancer ne crée pas de doublons.
Mot de passe : variable d'environnement NEO4J_PASSWORD, sinon il est demandé.
"""
import argparse
import getpass
import json
import os
from pathlib import Path

ENV_PATH = Path(__file__).resolve().parent / ".env"
try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=ENV_PATH)
except ImportError:
    pass

LABELS = ["Code", "Livre", "Titre", "Chapitre", "Section", "Article", "Alinea"]


def build_rows(data):
    """Aplatit l'arbre JSON en lignes par type de noeud + liens parent -> enfant."""
    nodes = {l: [] for l in LABELS}
    links = []  # (label_parent, id_parent, label_enfant, id_enfant, ordre)

    code_id = "CODE"
    nodes["Code"].append({"id": code_id, "nom": data["code"]})

    def add_article(art, parent_label, parent_id, ordre):
        aid = f"ART-{art['numero']}"
        alineas = art.get("alineas", [])
        parts = [art.get("texte_brut", "")] + [f"({a['numero']}) {a['texte']}" for a in alineas]
        nodes["Article"].append({
            "id": aid,
            "numero": art["numero"],
            "titre": art.get("titre", ""),
            "texte_brut": art.get("texte_brut", ""),
            "texte_complet": "\n".join(p for p in parts if p),
            "abroge": bool(art.get("abroge", False)),
            "est_plage": bool(art.get("est_plage", False)),
        })
        links.append((parent_label, parent_id, "Article", aid, ordre))
        for k, al in enumerate(alineas, 1):
            alid = f"{aid}-AL{k}"
            nodes["Alinea"].append({"id": alid, "numero": al["numero"], "texte": al["texte"]})
            links.append(("Article", aid, "Alinea", alid, k))

    for li, livre in enumerate(data["livres"], 1):
        lid = f"L{livre['numero']}"
        nodes["Livre"].append({"id": lid, "numero": livre["numero"], "titre_texte": livre.get("titre_texte", "")})
        links.append(("Code", code_id, "Livre", lid, li))
        for ti, titre in enumerate(livre["titres"], 1):
            tid = f"{lid}-T{titre['numero']}"
            nodes["Titre"].append({"id": tid, "numero": titre["numero"], "titre_texte": titre.get("titre_texte", "")})
            links.append(("Livre", lid, "Titre", tid, ti))
            for ci, chap in enumerate(titre["chapitres"], 1):
                cid = f"{tid}-C{ci}"  # index : certains Titres n'ont pas de numero de chapitre
                nodes["Chapitre"].append({"id": cid, "numero": chap.get("numero", ""), "titre_texte": chap.get("titre", "")})
                links.append(("Titre", tid, "Chapitre", cid, ci))
                ordre = 0
                for art in chap.get("articles", []):
                    ordre += 1
                    add_article(art, "Chapitre", cid, ordre)
                for si, sec in enumerate(chap.get("sections", []), 1):
                    sid = f"{cid}-S{si}"
                    nodes["Section"].append({"id": sid, "numero": sec["numero"], "titre_texte": sec.get("titre", "")})
                    links.append(("Chapitre", cid, "Section", sid, si))
                    for ai, art in enumerate(sec.get("articles", []), 1):
                        add_article(art, "Section", sid, ai)
    return nodes, links


def load(driver, nodes, links):
    with driver.session() as s:
        for label in LABELS:
            s.run(f"CREATE CONSTRAINT {label.lower()}_id IF NOT EXISTS "
                  f"FOR (n:{label}) REQUIRE n.id IS UNIQUE")
        for label in LABELS:
            rows = nodes[label]
            for i in range(0, len(rows), 500):
                s.run(f"UNWIND $rows AS r MERGE (n:{label} {{id: r.id}}) SET n += r",
                      rows=rows[i:i + 500])
            print(f"  {label}: {len(rows)} noeuds")
        groups = {}
        for pl, pid, cl, cid, ordre in links:
            groups.setdefault((pl, cl), []).append({"p": pid, "c": cid, "o": ordre})
        for (pl, cl), rows in groups.items():
            for i in range(0, len(rows), 500):
                s.run(
                    f"UNWIND $rows AS r MATCH (p:{pl} {{id: r.p}}) MATCH (c:{cl} {{id: r.c}}) "
                    f"MERGE (p)-[rel:CONTIENT]->(c) SET rel.ordre = r.o",
                    rows=rows[i:i + 500])
            print(f"  (:{pl})-[:CONTIENT]->(:{cl}): {len(rows)}")
        # index plein texte pour la recherche par mots-cles juridiques
        s.run("CREATE FULLTEXT INDEX article_texte IF NOT EXISTS "
              "FOR (a:Article) ON EACH [a.titre, a.texte_complet] "
              "OPTIONS {indexConfig: {`fulltext.analyzer`: 'french'}}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("json_path")
    ap.add_argument("--uri", default=os.environ.get("NEO4J_URI", "bolt://localhost:7687"))
    ap.add_argument("--user", default=os.environ.get("NEO4J_USER", "neo4j"))
    ap.add_argument("--password", default=os.environ.get("NEO4J_PASSWORD"), help="Mot de passe Neo4j (ou variable NEO4J_PASSWORD)")
    ap.add_argument("--dry-run", action="store_true", help="n'ecrit rien, affiche seulement les comptes")
    args = ap.parse_args()

    with open(args.json_path, encoding="utf-8") as f:
        data = json.load(f)
    nodes, links = build_rows(data)

    if args.dry_run:
        for l in LABELS:
            print(f"  {l}: {len(nodes[l])} noeuds")
        print(f"  relations CONTIENT: {len(links)}")
        return

    from neo4j import GraphDatabase
    password = args.password or os.environ.get("NEO4J_PASSWORD") or getpass.getpass("Mot de passe Neo4j : ")
    with GraphDatabase.driver(args.uri, auth=(args.user, password)) as driver:
        driver.verify_connectivity()
        print("Connecte a Neo4j. Chargement...")
        load(driver, nodes, links)
    print("Termine.")


if __name__ == "__main__":
    main()
