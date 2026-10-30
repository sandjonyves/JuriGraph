#!/usr/bin/env python3
"""
Détecte les renvois entre articles ("conformément à l'article 30 ci-dessus",
"les articles 277 et 280", ...) et crée (:Article)-[:RENVOIE_A]->(:Article).

    python extract_renvois.py code_penal_structure_docx.json            # écrit renvois.json + rapport
    python extract_renvois.py code_penal_structure_docx.json --load     # + charge dans Neo4j (mot de passe: NEO4J_PASSWORD ou invite)

Les renvois vers d'autres textes (Code de procédure pénale, lois, Actes uniformes...) sont ignorés
et listés dans le rapport. Les plages courtes ("articles 201 à 209") sont déroulées ; les autres sont listées pour relecture.
"""
import argparse, getpass, json, os, re
from pathlib import Path
from load_neo4j import build_rows

ENV_PATH = Path(__file__).resolve().parent / ".env"
try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=ENV_PATH)
except ImportError:
    pass

NUM = r"\d+(?:-\d+)?(?:\s*\(\d+\))*"
LISTE = re.compile(rf"\b[Aa]rticles?\s+({NUM}(?:\s*(?:,|et|ou|à)\s*{NUM})*)")
EXTERNE = re.compile(
    r"^\s*(?:,\s*)?(?:du|de la|de l[’']|des)\s+(?:Code (?!pénal)|loi|décret|Acte|Convention|Constitution|Règlement|ordonnance)",
    re.I)


def parse_refs(bloc):
    """'218, 219-1 et 220' -> (liste de numéros, liste de plages)"""
    plages = [(a, b) for a, b in re.findall(rf"({NUM})\s+à\s+({NUM})", bloc)]
    if plages:
        bloc_sans = re.sub(rf"{NUM}\s+à\s+{NUM}", " ", bloc)
    else:
        bloc_sans = bloc
    nums = [re.sub(r"\s*\(\d+\)", "", x) for x in re.findall(NUM, bloc_sans)]
    return nums, plages


def extraire(data):
    nodes, _ = build_rows(data)
    ordre = [a["numero"] for a in nodes["Article"]]
    existants = set(ordre)
    relations, externes, inconnus, plages_rep = {}, [], [], []
    for a in nodes["Article"]:
        if a["numero"] in ("1", "362-370"):   # articles qui décrivent la structure du Code, pas des renvois juridiques
            continue
        texte = a["texte_complet"]
        for m in LISTE.finditer(texte):
            suite = texte[m.end():m.end() + 60]
            contexte = texte[max(0, m.start() - 10):m.end() + 40].replace("\n", " ")
            if EXTERNE.match(suite):
                externes.append((a["numero"], contexte)); continue
            nums, plages = parse_refs(m.group(1))
            for p in plages:
                d, f = re.sub(r"\s*\(\d+\)", "", p[0]), re.sub(r"\s*\(\d+\)", "", p[1])
                if d in existants and f in existants and 0 <= ordre.index(f) - ordre.index(d) <= 15:
                    nums += ordre[ordre.index(d):ordre.index(f) + 1]   # plage courte : déroulée dans l'ordre du Code
                else:
                    plages_rep.append((a["numero"], f"{d} à {f}"))
            for n in nums:
                if n == a["numero"]:
                    continue
                if n not in existants:
                    inconnus.append((a["numero"], n)); continue
                relations.setdefault((a["numero"], n), contexte)
    return relations, externes, inconnus, plages_rep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("json_path")
    ap.add_argument("--out", default="renvois.json")
    ap.add_argument("--load", action="store_true")
    ap.add_argument("--uri", default=os.environ.get("NEO4J_URI", "bolt://localhost:7687"))
    ap.add_argument("--user", default=os.environ.get("NEO4J_USER", "neo4j"))
    ap.add_argument("--password", default=os.environ.get("NEO4J_PASSWORD"), help="Mot de passe Neo4j (ou variable NEO4J_PASSWORD)")
    args = ap.parse_args()
    data = json.load(open(args.json_path, encoding="utf-8"))
    rel, ext, inc, pl = extraire(data)
    rows = [{"source": s, "cible": c, "contexte": ctx} for (s, c), ctx in sorted(rel.items())]
    json.dump(rows, open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{len(rows)} renvois internes -> {args.out}")
    print(f"{len(ext)} renvois vers d'autres textes ignorés, {len(pl)} plages à relire, {len(inc)} numéros introuvables")
    for s, c in inc[:10]: print("  introuvable:", s, "->", c)
    for s, p in pl[:10]: print("  plage:", s, "->", p)
    if args.load:
        from neo4j import GraphDatabase
        pwd = args.password or os.environ.get("NEO4J_PASSWORD") or getpass.getpass("Mot de passe Neo4j : ")
        with GraphDatabase.driver(args.uri, auth=(args.user, pwd)) as d:
            d.execute_query(
                "UNWIND $rows AS r MATCH (a:Article {numero: r.source}) MATCH (b:Article {numero: r.cible}) "
                "MERGE (a)-[x:RENVOIE_A]->(b) SET x.contexte = r.contexte", rows=rows)
        print("Chargé dans Neo4j.")

if __name__ == "__main__":
    main()
