#!/usr/bin/env python3
"""
Calcule les embeddings des articles avec l'API Gemini (gemini-embedding-001, offre gratuite),
les stocke dans Neo4j et crée l'index vectoriel.

Préparation :
    pip install google-genai neo4j
    Clé gratuite : https://aistudio.google.com/apikey   ->   variable d'environnement GEMINI_API_KEY

Usage :
    python embed_articles.py code_penal_structure_docx.json --dry-run            # sans API ni Neo4j
    python embed_articles.py code_penal_structure_docx.json                       # calcule + charge dans Neo4j
    python embed_articles.py code_penal_structure_docx.json --query "quelqu'un tue volontairement une personne"

Les vecteurs calculés sont sauvegardés dans embeddings_cache.json : si le quota gratuit
est atteint, relance simplement le script plus tard, il reprend où il s'était arrêté.
"""
import argparse, getpass, json, math, os, sys, time
from pathlib import Path

ENV_PATH = Path(__file__).resolve().parent / ".env"
try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=ENV_PATH)
except ImportError:
    pass

MODEL = "gemini-embedding-001"
DIM = 768
MAX_CHARS = 6000          # limite du modèle ~2048 tokens
BATCH = 20
CACHE = "embeddings_cache.json"


def articles_avec_contexte(data):
    """Un texte par article : Livre / Titre / Chapitre / Section en préfixe, puis l'article."""
    out = []
    for livre in data["livres"]:
        for titre in livre["titres"]:
            for chap in titre["chapitres"]:
                groupes = [(chap["titre"], chap["articles"])] + [
                    (f"{chap['titre']} / {s['titre']}", s["articles"]) for s in chap["sections"]]
                for ctx_chap, arts in groupes:
                    for a in arts:
                        corps = "\n".join(x for x in (
                            a["texte_brut"],
                            "\n".join(f"({al['numero']}) {al['texte']}" for al in a["alineas"])) if x)
                        if not corps or a.get("abroge") or a.get("est_plage"):
                            continue
                        contexte = f"Livre {livre['numero']} — {titre['titre_texte']} — {ctx_chap}".strip(" —")
                        texte = f"{contexte}\nArticle {a['numero']} — {a['titre']}\n{corps}"
                        out.append({"id": f"ART-{a['numero']}", "texte": texte[:MAX_CHARS],
                                    "tronque": len(texte) > MAX_CHARS})
    return out


def normaliser(v):
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def embed(client, textes, task):
    from google.genai import types
    for essai in range(6):
        try:
            r = client.models.embed_content(
                model=MODEL, contents=textes,
                config=types.EmbedContentConfig(task_type=task, output_dimensionality=DIM))
            return [normaliser(e.values) for e in r.embeddings]
        except Exception as e:                      # quota (429) ou erreur réseau
            attente = 15 * (essai + 1)
            print(f"  erreur ({str(e)[:90]}) — nouvelle tentative dans {attente}s")
            time.sleep(attente)
    raise SystemExit("Échec répété : quota gratuit probablement atteint. Relance plus tard (le cache est conservé).")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("json_path")
    ap.add_argument("--uri", default=os.environ.get("NEO4J_URI", "bolt://localhost:7687"))
    ap.add_argument("--user", default=os.environ.get("NEO4J_USER", "neo4j"))
    ap.add_argument("--database", default=os.environ.get("NEO4J_DATABASE", "neo4j"))
    ap.add_argument("--password", default=os.environ.get("NEO4J_PASSWORD"), help="Mot de passe Neo4j (ou variable NEO4J_PASSWORD)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--query")
    ap.add_argument("--api-key", default=os.environ.get("GEMINI_API_KEY"), help="Clé API Gemini (ou variable GEMINI_API_KEY)")
    args = ap.parse_args()

    data = json.load(open(args.json_path, encoding="utf-8"))
    items = articles_avec_contexte(data)
    print(f"{len(items)} articles à vectoriser ({sum(i['tronque'] for i in items)} tronqués à {MAX_CHARS} caractères)")
    if args.dry_run:
        print("Exemple :\n" + items[200]["texte"][:400])
        return

    key = args.api_key or os.environ.get("GEMINI_API_KEY") or sys.exit("Définis GEMINI_API_KEY (clé gratuite sur aistudio.google.com/apikey).")
    from google import genai
    client = genai.Client(api_key=key)
    pwd = args.password or os.environ.get("NEO4J_PASSWORD") or getpass.getpass("Mot de passe Neo4j : ")
    from neo4j import GraphDatabase
    driver = GraphDatabase.driver(args.uri, auth=(args.user, pwd))
    run = lambda q, **p: driver.execute_query(q, database_=args.database, **p)

    if args.query:
        v = embed(client, [args.query], "RETRIEVAL_QUERY")[0]
        res, _, _ = run("CALL db.index.vector.queryNodes('article_embedding', 5, $v) YIELD node, score "
                        "RETURN node.numero AS n, node.titre AS titre, score", v=v)
        for r in res:
            print(f"Article {r['n']} — {r['titre']}  (score {r['score']:.3f})")
        return

    cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}
    todo = [i for i in items if i["id"] not in cache]
    print(f"{len(cache)} déjà en cache, {len(todo)} à calculer")
    for k in range(0, len(todo), BATCH):
        lot = todo[k:k + BATCH]
        vecs = embed(client, [i["texte"] for i in lot], "RETRIEVAL_DOCUMENT")
        for i, v in zip(lot, vecs):
            cache[i["id"]] = v
        json.dump(cache, open(CACHE, "w"))
        print(f"  {min(k + BATCH, len(todo))}/{len(todo)}")
        time.sleep(2)

    rows = [{"id": i, "v": v} for i, v in cache.items()]
    for k in range(0, len(rows), 100):
        run("UNWIND $rows AS r MATCH (a:Article {id: r.id}) SET a.embedding = r.v",
            rows=rows[k:k + 100])
    run("CREATE VECTOR INDEX article_embedding IF NOT EXISTS FOR (a:Article) ON (a.embedding) "
        f"OPTIONS {{indexConfig: {{`vector.dimensions`: {DIM}, `vector.similarity_function`: 'cosine'}}}}")
    print(f"{len(rows)} embeddings enregistrés, index 'article_embedding' créé.")
    driver.close()


if __name__ == "__main__":
    main()
