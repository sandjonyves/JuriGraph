#!/usr/bin/env python3
"""
Calcule les embeddings des articles, les stocke dans Neo4j et crée l'index vectoriel.

Le modèle est interchangeable (voir embeddings/) et se choisit par l'environnement
ou la ligne de commande :

    # Gemini (défaut) — clé gratuite sur https://aistudio.google.com/apikey
    python embed_articles.py code_penal_structure_docx.json

    # Serveur local compatible OpenAI (Ollama, vLLM, LM Studio...) — sans clé
    python embed_articles.py code_penal_structure_docx.json \
        --provider openai --model nomic-embed-text --base-url http://localhost:11434/v1 --dim 768

    # OpenRouter (clé sur https://openrouter.ai/keys)
    python embed_articles.py code_penal_structure_docx.json \
        --provider openrouter --model openai/text-embedding-3-small --dim 1536

Préparation :
    pip install google-genai neo4j        # pour Gemini
    # pour un serveur local compatible OpenAI : seule la bibliothèque standard est utilisée

Usage :
    python embed_articles.py code_penal_structure_docx.json --dry-run
    python embed_articles.py code_penal_structure_docx.json
    python embed_articles.py code_penal_structure_docx.json --query "quelqu'un tue volontairement une personne"

Les vecteurs sont mis en cache dans embeddings_cache.json, indexé par
(provider, modèle, dimension, texte). Changer de modèle ou de texte invalide
automatiquement les entrées concernées ; si le quota gratuit est atteint,
relance le script plus tard : il reprend où il s'était arrêté.
"""
import argparse
import getpass
import hashlib
import json
import os
import re
import sys
from pathlib import Path

from embeddings import PROVIDERS, EmbeddingError, chunks, create_embedder

ENV_PATH = Path(__file__).resolve().parent / ".env"
try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=ENV_PATH)
except ImportError:
    pass

CACHE = Path(os.environ.get("EMBEDDING_CACHE") or Path(__file__).resolve().parent / "embeddings_cache.json")
CACHE_VERSION = 1
BATCH_WRITE = 100


def articles_avec_contexte(data, max_chars):
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
                        out.append({"id": f"ART-{a['numero']}", "texte": texte[:max_chars],
                                    "tronque": len(texte) > max_chars})
    return out


# --------------------------------------------------------------------------- cache

def cache_key(signature, texte):
    return hashlib.sha256(f"{signature}\x00{texte}".encode("utf-8")).hexdigest()


def charger_cache(signature):
    """Retourne {clé: vecteur} pour cette configuration, ou {} si le cache
    provient d'un autre modèle/format (il sera alors recalculé et réécrit)."""
    if not CACHE.exists():
        return {}
    try:
        with open(CACHE, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Cache illisible ({exc}) — il sera recalculé.")
        return {}
    if data.get("version") != CACHE_VERSION or data.get("signature") != signature:
        print("Cache d'un autre modèle ou d'un ancien format — recalcul complet.")
        return {}
    return data.get("vectors", {})


def sauver_cache(signature, vectors):
    """Écriture atomique : un arrêt brutal ne corrompt pas le cache existant."""
    payload = {"version": CACHE_VERSION, "signature": signature, "vectors": vectors}
    tmp = CACHE.with_name(CACHE.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f)
    os.replace(tmp, CACHE)


# --------------------------------------------------------------------------- Neo4j

def _valid_index_name(name):
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
        raise SystemExit(f"Nom d'index invalide : {name!r}")
    return name


def _index_dimensions(run, name):
    records, _, _ = run(
        "SHOW VECTOR INDEXES YIELD name, options WHERE name = $name RETURN options AS options",
        name=name)
    if not records:
        return None
    config = (records[0]["options"] or {}).get("indexConfig") or {}
    dimensions = config.get("vector.dimensions")
    return int(dimensions) if dimensions is not None else None


def ensure_vector_index(run, name, dim, create=True):
    """Vérifie la compatibilité de l'index existant, le crée au besoin."""
    _valid_index_name(name)
    existing = _index_dimensions(run, name)
    if existing is not None:
        if existing != int(dim):
            raise SystemExit(
                f"L'index '{name}' existe en {existing} dimensions mais le modèle en produit {dim}.\n"
                f"Supprime-le avant de relancer :  DROP INDEX {name}")
        return
    if not create:
        raise SystemExit(f"Index vectoriel '{name}' absent : lance d'abord l'indexation.")
    run(f"CREATE VECTOR INDEX {name} IF NOT EXISTS FOR (a:Article) ON (a.embedding) "
        f"OPTIONS {{indexConfig: {{`vector.dimensions`: {int(dim)}, "
        f"`vector.similarity_function`: 'cosine'}}}}")
    run("CALL db.awaitIndexes(300)")


def _supports_search(run):
    """SEARCH (Cypher 25) existe depuis Neo4j 2026.01 ; la procédure reste le
    repli compatible 5.x (et pour Aura, qui masque sa version sous 5.27)."""
    records, _, _ = run("CALL dbms.components() YIELD versions RETURN versions[0] AS v")
    match = re.match(r"(\d+)\.(\d+)", records[0]["v"] if records else "")
    return bool(match) and (int(match[1]), int(match[2])) >= (2026, 1)


def vector_search(run, name, k, vector):
    _valid_index_name(name)
    if _supports_search(run):
        records, _, _ = run(
            "CYPHER 25 MATCH (a:Article) "
            f"SEARCH a IN (VECTOR INDEX {name} FOR $v LIMIT $k) SCORE AS score "
            "RETURN a.numero AS n, a.titre AS titre, score ORDER BY score DESC",
            v=vector, k=k)
        return records
    records, _, _ = run(
        "CALL db.index.vector.queryNodes($index, $k, $v) YIELD node, score "
        "RETURN node.numero AS n, node.titre AS titre, score ORDER BY score DESC",
        index=name, k=k, v=vector)
    return records


# --------------------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description="Embeddings des articles + index vectoriel Neo4j.")
    ap.add_argument("json_path")
    ap.add_argument("--provider", default=os.environ.get("EMBEDDING_PROVIDER"),
                    help=f"Fournisseur d'embeddings : {', '.join(sorted(PROVIDERS))}")
    ap.add_argument("--model", default=os.environ.get("EMBEDDING_MODEL"), help="Nom du modèle")
    ap.add_argument("--dim", type=int, default=os.environ.get("EMBEDDING_DIM"), help="Dimensions des vecteurs")
    ap.add_argument("--batch-size", type=int,
                    default=int(os.environ.get("EMBEDDING_BATCH_SIZE", 20)), help="Textes par requête")
    ap.add_argument("--base-url", default=os.environ.get("EMBEDDING_BASE_URL"),
                    help="URL de base pour un serveur compatible OpenAI")
    ap.add_argument("--api-key", help="Clé API du fournisseur (sinon variable d'environnement)")
    ap.add_argument("--uri", default=os.environ.get("NEO4J_URI", "bolt://localhost:7687"))
    ap.add_argument("--user", default=os.environ.get("NEO4J_USER", "neo4j"))
    ap.add_argument("--database", default=os.environ.get("NEO4J_DATABASE", "neo4j"))
    ap.add_argument("--password", default=os.environ.get("NEO4J_PASSWORD"),
                    help="Mot de passe Neo4j (ou variable NEO4J_PASSWORD)")
    ap.add_argument("--index", default=os.environ.get("NEO4J_VECTOR_INDEX", "article_embedding"),
                    help="Nom de l'index vectoriel")
    ap.add_argument("--top-k", type=int, default=5, help="Nombre de résultats en mode --query")
    ap.add_argument("--dry-run", action="store_true", help="Affiche un exemple sans API ni Neo4j")
    ap.add_argument("--query", help="Recherche en langage naturel (aucune écriture)")
    args = ap.parse_args()

    with open(args.json_path, encoding="utf-8") as f:
        data = json.load(f)

    kwargs = {}
    if args.base_url:
        kwargs["base_url"] = args.base_url
    if args.api_key:
        kwargs["api_key"] = args.api_key
    embedder = create_embedder(args.provider, model=args.model, dim=args.dim,
                               batch_size=args.batch_size, **kwargs)

    items = None
    if not args.query:
        items = articles_avec_contexte(data, embedder.max_chars)
        print(f"{len(items)} articles à vectoriser ({sum(i['tronque'] for i in items)} tronqués "
              f"à {embedder.max_chars} caractères) — modèle {embedder.signature}")
        if args.dry_run:
            exemple = items[min(200, len(items) - 1)] if items else {"texte": "(aucun article)"}
            print("Exemple :\n" + exemple["texte"][:400])
            return

    from neo4j import GraphDatabase
    pwd = args.password or getpass.getpass("Mot de passe Neo4j : ")
    driver = GraphDatabase.driver(args.uri, auth=(args.user, pwd))

    def run(query, **params):
        return driver.execute_query(query, database_=args.database, **params)

    try:
        if args.query:
            ensure_vector_index(run, args.index, embedder.dim, create=False)
            vector = embedder.embed_query(args.query)
            records = vector_search(run, args.index, args.top_k, vector)
            if not records:
                print("Aucun résultat (la base est-elle indexée ?).")
            for r in records:
                print(f"Article {r['n']} — {r['titre']}  (score {r['score']:.3f})")
            return

        ensure_vector_index(run, args.index, embedder.dim, create=True)

        vectors = charger_cache(embedder.signature)
        todo = [i for i in items if cache_key(embedder.signature, i["texte"]) not in vectors]
        print(f"{len(items) - len(todo)} déjà en cache, {len(todo)} à calculer")

        def enregistrer_lot(done, calculees):
            for item, vector in zip(todo[:done], calculees):
                vectors[cache_key(embedder.signature, item["texte"])] = vector
            sauver_cache(embedder.signature, vectors)
            print(f"  {done}/{len(todo)}")

        embedder.embed_documents([i["texte"] for i in todo], on_batch=enregistrer_lot)

        rows = [{"id": i["id"], "v": vectors[cache_key(embedder.signature, i["texte"])]}
                for i in items if cache_key(embedder.signature, i["texte"]) in vectors]
        updated = 0
        for lot in chunks(rows, BATCH_WRITE):
            records, _, _ = run(
                "UNWIND $rows AS r MATCH (a:Article {id: r.id}) "
                "SET a.embedding = r.v RETURN count(a) AS n", rows=lot)
            updated += records[0]["n"]
        run("CALL db.awaitIndexes(300)")
        print(f"{updated}/{len(rows)} articles mis à jour, index '{args.index}' prêt.")
    finally:
        driver.close()


if __name__ == "__main__":
    try:
        main()
    except EmbeddingError as exc:
        sys.exit(f"Erreur d'embeddings : {exc}")
