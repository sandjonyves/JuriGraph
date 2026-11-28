#!/usr/bin/env python3
"""Recherche hybride d'articles du Code pénal à partir de faits en texte libre.

Trois voies, fusionnées par Reciprocal Rank Fusion (RRF) :
  1. vectorielle (index ``article_embedding``) ;
  2. plein texte (index ``article_texte``, titre pondéré) ;
  3. graphe, à partir des meilleurs articles : renvois ``RENVOIE_A`` (dans les
     deux sens) et articles voisins sous le même parent (``CONTIENT``).

Chaque résultat garde sa provenance. Les articles abrogés et les plages sont
exclus. Aucun texte de loi n'est généré : seuls des identifiants d'articles
existants sont renvoyés.

Usage :
    python search_hybrid.py "Il a volé une moto avec un couteau" --k 10
    python search_hybrid.py "..." --sans-renvois --sans-section
    python search_hybrid.py "..." --dry-run
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

RACINE = Path(__file__).resolve().parent
CACHE_REQUETES = RACINE / "data/cache/requetes_embeddings.json"
INDEX_VECTEUR = "article_embedding"
INDEX_PLEIN_TEXTE = "article_texte"
CARACTERES_LUCENE = re.compile(r'([+\-&|!(){}\[\]^"~*?:\\/])')
MOTS_VIDES = {
    "a", "au", "aux", "avec", "ce", "ces", "cet", "cette", "d", "de", "des", "du",
    "elle", "elles", "en", "est", "et", "il", "ils", "je", "l", "la", "le", "les",
    "leur", "leurs", "lui", "m", "ma", "mais", "me", "mes", "mon", "n", "ne", "ni",
    "nos", "notre", "nous", "on", "ou", "par", "pas", "pour", "qu", "que", "qui",
    "s", "sa", "se", "ses", "si", "son", "sont", "sur", "t", "un", "une", "y",
    "été", "était", "avait", "ont", "après", "plus", "tout", "tous", "dont", "puis",
    "chez", "sous", "comme", "fait", "très", "and", "or", "not", "to",
}

Executeur = Callable[..., list]


@dataclass
class Config:
    """Paramètres d'une configuration de recherche (utilisés pour les ablations)."""

    vecteur: bool = True
    plein_texte: bool = True
    renvois: bool = True
    section: bool = True
    multi_requetes: bool = False
    profondeur: int = 20
    graines: int = 5
    k_rrf: int = 60
    poids_graphe: float = 0.5
    max_voisins: int = 10

    def nom(self) -> str:
        """Nom court lisible de la configuration."""
        voies = [n for n, actif in (("V", self.vecteur), ("PT", self.plein_texte),
                                    ("R", self.renvois), ("S", self.section)) if actif]
        return "+".join(voies) + ("+MQ" if self.multi_requetes else "")


@dataclass
class Resultat:
    """Un article retrouvé, avec son rang, son score de fusion et sa provenance."""

    numero: str
    rang: int
    score: float
    sources: list[str] = field(default_factory=list)
    titre: str = ""


# --------------------------------------------------------------- fonctions pures

def echapper_lucene(mot: str) -> str:
    """Échappe les caractères spéciaux de la syntaxe Lucene."""
    return CARACTERES_LUCENE.sub(r"\\\1", mot)


def mots_pleins(texte: str) -> list[str]:
    """Mots significatifs d'un texte, dans l'ordre, sans doublon."""
    mots = re.findall(r"[0-9A-Za-zÀ-ÖØ-öø-ÿŒœ]+", texte.lower())
    vus: list[str] = []
    for mot in mots:
        if len(mot) > 2 and mot not in MOTS_VIDES and not mot.isdigit() and mot not in vus:
            vus.append(mot)
    return vus


def requete_lucene(texte: str) -> str:
    """Construit une requête Lucene OU, avec le titre pondéré deux fois."""
    termes = " ".join(echapper_lucene(m) for m in mots_pleins(texte))
    if not termes:
        return ""
    return f"titre:({termes})^2 OR texte_complet:({termes})"


def decouper_requetes(faits: str, maximum: int = 4) -> list[str]:
    """Faits complets + chaque phrase significative, pour la recherche multi-requêtes."""
    phrases = [p.strip() for p in re.split(r"(?<=[.!?;])\s+", faits) if p.strip()]
    requetes = [faits.strip()]
    for phrase in phrases:
        if len(mots_pleins(phrase)) >= 3 and phrase not in requetes:
            requetes.append(phrase)
    return requetes[:maximum]


def fusion_rrf(listes: list[tuple[str, list[str], float]], k: int = 60) -> list[Resultat]:
    """Fusionne des classements : score = somme des poids / (k + rang)."""
    scores: dict[str, float] = {}
    sources: dict[str, list[str]] = {}
    for nom, classement, poids in listes:
        for rang, numero in enumerate(classement, 1):
            scores[numero] = scores.get(numero, 0.0) + poids / (k + rang)
            if nom not in sources.setdefault(numero, []):
                sources[numero].append(nom)
    ordre = sorted(scores, key=lambda n: (-scores[n], n))
    return [Resultat(numero=n, rang=i, score=scores[n], sources=sources[n])
            for i, n in enumerate(ordre, 1)]


# --------------------------------------------------------------- cache d'embeddings

class CacheRequetes:
    """Cache disque des vecteurs de requêtes (évite les appels répétés)."""

    def __init__(self, chemin: Path | None, signature: str):
        self.chemin, self.signature = chemin, signature
        self.donnees: dict[str, list[float]] = {}
        if chemin and chemin.exists():
            self.donnees = json.loads(chemin.read_text(encoding="utf-8"))

    def cle(self, texte: str) -> str:
        """Clé = hash(signature du modèle + texte)."""
        return hashlib.sha256(f"{self.signature}\n{texte}".encode()).hexdigest()

    def obtenir(self, texte: str, calculer: Callable[[str], list[float]]) -> list[float]:
        """Renvoie le vecteur en cache ou le calcule puis l'enregistre."""
        cle = self.cle(texte)
        if cle not in self.donnees:
            self.donnees[cle] = list(calculer(texte))
            self._sauver()
        return self.donnees[cle]

    def _sauver(self) -> None:
        """Écriture atomique du cache."""
        if not self.chemin:
            return
        self.chemin.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.chemin.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.donnees), encoding="utf-8")
        tmp.replace(self.chemin)


# --------------------------------------------------------------- moteur

class RechercheHybride:
    """Moteur de recherche hybride ; ``executer(requete, **params)`` renvoie des enregistrements."""

    def __init__(self, executer: Executeur, embed_query: Callable[[str], list[float]] | None,
                 cache: CacheRequetes | None = None):
        self.executer = executer
        self.embed_query = embed_query
        self.cache = cache
        self._valides: set[str] | None = None
        self._titres: dict[str, str] = {}

    def articles_valides(self) -> set[str]:
        """Numéros des articles ni abrogés ni plages (chargés une fois)."""
        if self._valides is None:
            lignes = self.executer(
                "MATCH (a:Article) WHERE coalesce(a.abroge, false) = false "
                "AND coalesce(a.est_plage, false) = false "
                "RETURN a.numero AS n, a.titre AS titre")
            self._valides = {str(r["n"]) for r in lignes}
            self._titres = {str(r["n"]): r["titre"] or "" for r in lignes}
        return self._valides

    def _vecteur(self, texte: str) -> list[float]:
        """Vecteur de la requête, via le cache si disponible."""
        if self.embed_query is None:
            raise RuntimeError("aucun modèle d'embedding configuré")
        if self.cache:
            return self.cache.obtenir(texte, self.embed_query)
        return self.embed_query(texte)

    def voie_vecteur(self, texte: str, k: int) -> list[str]:
        """Classement par similarité cosinus."""
        from embed_articles import vector_search

        def run(requete, **params):
            return self.executer(requete, **params), None, None

        lignes = vector_search(run, INDEX_VECTEUR, k + 5, self._vecteur(texte))
        valides = self.articles_valides()
        return [str(r["n"]) for r in lignes if str(r["n"]) in valides][:k]

    def voie_plein_texte(self, texte: str, k: int) -> list[str]:
        """Classement Lucene (analyseur français)."""
        requete = requete_lucene(texte)
        if not requete:
            return []
        lignes = self.executer(
            f"CALL db.index.fulltext.queryNodes('{INDEX_PLEIN_TEXTE}', $q) "
            "YIELD node, score RETURN node.numero AS n, score LIMIT $k",
            q=requete, k=k + 5)
        valides = self.articles_valides()
        return [str(r["n"]) for r in lignes if str(r["n"]) in valides][:k]

    def voie_renvois(self, graines: list[str]) -> list[str]:
        """Articles reliés aux graines par RENVOIE_A, triés par nombre de liens."""
        if not graines:
            return []
        lignes = self.executer(
            "UNWIND $g AS num MATCH (a:Article {numero: num})-[:RENVOIE_A]-(b:Article) "
            "RETURN b.numero AS n, count(*) AS liens ORDER BY liens DESC, n",
            g=graines)
        valides, exclus = self.articles_valides(), set(graines)
        return [str(r["n"]) for r in lignes if str(r["n"]) in valides
                and str(r["n"]) not in exclus]

    def voie_section(self, graines: list[str], max_voisins: int) -> list[str]:
        """Articles sous le même parent que les graines, les plus proches d'abord."""
        if not graines:
            return []
        lignes = self.executer(
            "UNWIND range(0, size($g) - 1) AS i "
            "MATCH (p)-[c1:CONTIENT]->(a:Article {numero: $g[i]}) "
            "MATCH (p)-[c2:CONTIENT]->(b:Article) WHERE b <> a "
            "WITH b, min(i) AS rang_graine, min(abs(c2.ordre - c1.ordre)) AS distance "
            "RETURN b.numero AS n ORDER BY rang_graine, distance, n",
            g=graines)
        valides, exclus = self.articles_valides(), set(graines)
        voisins = [str(r["n"]) for r in lignes if str(r["n"]) in valides
                   and str(r["n"]) not in exclus]
        return voisins[:max_voisins * len(graines)]

    def rechercher(self, faits: str, k: int = 10, config: Config | None = None) -> list[Resultat]:
        """Recherche hybride complète ; renvoie les k premiers résultats."""
        config = config or Config()
        requetes = decouper_requetes(faits) if config.multi_requetes else [faits]
        listes: list[tuple[str, list[str], float]] = []
        for i, requete in enumerate(requetes):
            suffixe = "" if i == 0 else f"#{i}"
            if config.vecteur:
                listes.append((f"vecteur{suffixe}", self.voie_vecteur(requete, config.profondeur), 1.0))
            if config.plein_texte:
                listes.append((f"plein_texte{suffixe}",
                               self.voie_plein_texte(requete, config.profondeur), 1.0))
        base = fusion_rrf(listes, config.k_rrf)
        graines = [r.numero for r in base[:config.graines]]
        if config.renvois:
            listes.append(("renvoi", self.voie_renvois(graines), config.poids_graphe))
        if config.section:
            listes.append(("section", self.voie_section(graines, config.max_voisins),
                           config.poids_graphe))
        resultats = fusion_rrf(listes, config.k_rrf)[:k]
        for r in resultats:
            r.titre = self._titres.get(r.numero, "")
        return resultats


# --------------------------------------------------------------- construction réelle

def construire(cache: bool = True):
    """Crée le moteur relié à Neo4j et au modèle d'embedding de .env ; renvoie (moteur, driver)."""
    from dotenv import load_dotenv
    from neo4j import GraphDatabase

    from embeddings import create_embedder

    load_dotenv(RACINE / ".env")
    mdp = os.environ.get("NEO4J_PASSWORD")
    if not mdp:
        raise SystemExit("NEO4J_PASSWORD absent : renseignez .env")
    driver = GraphDatabase.driver(os.environ.get("NEO4J_URI", "bolt://localhost:7687"),
                                  auth=(os.environ.get("NEO4J_USER", "neo4j"), mdp),
                                  notifications_min_severity="OFF")
    base = os.environ.get("NEO4J_DATABASE", "neo4j")

    def executer(requete: str, **params) -> list:
        return driver.execute_query(requete, params, database_=base).records

    embedder = create_embedder()
    cache_req = CacheRequetes(CACHE_REQUETES if cache else None, embedder.signature)
    return RechercheHybride(executer, embedder.embed_query, cache_req), driver


def main() -> int:
    """Point d'entrée en ligne de commande."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("faits", help="description des faits en texte libre")
    parser.add_argument("--k", type=int, default=10)
    parser.add_argument("--sans-vecteur", action="store_true")
    parser.add_argument("--sans-plein-texte", action="store_true")
    parser.add_argument("--sans-renvois", action="store_true")
    parser.add_argument("--sans-section", action="store_true")
    parser.add_argument("--multi-requetes", action="store_true")
    parser.add_argument("--dry-run", action="store_true",
                        help="affiche les requêtes construites, sans connexion")
    args = parser.parse_args()
    config = Config(vecteur=not args.sans_vecteur, plein_texte=not args.sans_plein_texte,
                    renvois=not args.sans_renvois, section=not args.sans_section,
                    multi_requetes=args.multi_requetes)

    if args.dry_run:
        print(f"Configuration : {config.nom()}")
        for requete in (decouper_requetes(args.faits) if config.multi_requetes else [args.faits]):
            print(f"- requête : {requete}\n  Lucene : {requete_lucene(requete)}")
        return 0

    moteur, driver = construire()
    try:
        debut = time.perf_counter()
        resultats = moteur.rechercher(args.faits, args.k, config)
        duree = (time.perf_counter() - debut) * 1000
    finally:
        driver.close()
    print(f"Configuration {config.nom()} — {duree:.0f} ms")
    for r in resultats:
        print(f"{r.rang:2d}. Article {r.numero:7s} {r.titre[:50]:50s} "
              f"{r.score:.4f}  [{', '.join(r.sources)}]")
    print("\nAide à la recherche : à vérifier dans le texte officiel de chaque article.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
