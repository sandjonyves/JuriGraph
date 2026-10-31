"""Tests de la couche d'embeddings (bibliothèque standard uniquement).

    python -m unittest discover -s tests
"""
import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import embed_articles
from embeddings import PROVIDERS, create_embedder
from embeddings.base import BaseEmbedder, EmbeddingError, normalize
from embeddings.openrouter import OpenRouterEmbedder


class FakeEmbedder(BaseEmbedder):
    name = "fake"
    default_model = "fake-model"
    default_dim = 3
    default_pause = 0

    def __init__(self, failures=0, **kwargs):
        super().__init__(**kwargs)
        self.failures = failures
        self.calls = 0

    def _embed_batch(self, texts, kind):
        self.calls += 1
        if self.failures:
            self.failures -= 1
            raise EmbeddingError("quota", transient=True)
        return [[1.0, 2.0, 2.0] for _ in texts]


class TestBaseEmbedder(unittest.TestCase):
    def setUp(self):
        self._delay = BaseEmbedder.base_delay
        BaseEmbedder.base_delay = 0.001

    def tearDown(self):
        BaseEmbedder.base_delay = self._delay

    def test_normalize(self):
        self.assertEqual(normalize([3.0, 4.0]), [0.6, 0.8])
        self.assertEqual(normalize([0.0, 0.0]), [0.0, 0.0])

    def test_lots_et_callback(self):
        embedder = FakeEmbedder(batch_size=2)
        compteurs = []
        vecteurs = embedder.embed_documents(
            ["a", "b", "c", "d", "e"], on_batch=lambda done, v: compteurs.append(done))
        self.assertEqual(compteurs, [2, 4, 5])
        self.assertEqual(len(vecteurs), 5)
        self.assertEqual(embedder.calls, 3)

    def test_retry_transitoire(self):
        embedder = FakeEmbedder(failures=2, batch_size=2)
        vecteurs = embedder.embed_documents(["a", "b", "c"])
        self.assertEqual(embedder.calls, 4)          # 2 échecs + 2 lots
        self.assertEqual(len(vecteurs), 3)

    def test_erreur_definitive_non_retentee(self):
        class Definitive(FakeEmbedder):
            def _embed_batch(self, texts, kind):
                raise EmbeddingError("clé invalide", transient=False)

        embedder = Definitive()
        with self.assertRaises(EmbeddingError):
            embedder.embed_documents(["a"])
        self.assertEqual(embedder.calls, 0)

    def test_nombre_de_vecteurs_incoherent(self):
        class Partiel(FakeEmbedder):
            def _embed_batch(self, texts, kind):
                return [[1.0, 1.0, 1.0]]

        with self.assertRaises(EmbeddingError):
            Partiel().embed_documents(["a", "b"])

    def test_mauvaise_dimension(self):
        embedder = FakeEmbedder(dim=4)
        with self.assertRaises(EmbeddingError):
            embedder.embed_documents(["a"])


class TestRegistre(unittest.TestCase):
    def test_fournisseurs_disponibles(self):
        self.assertIn("gemini", PROVIDERS)
        self.assertIn("openai", PROVIDERS)
        self.assertIn("openrouter", PROVIDERS)

    def test_openrouter_par_defaut(self):
        embedder = OpenRouterEmbedder()          # ignore volontairement le .env du projet
        self.assertEqual(embedder.signature, "openrouter:openai/text-embedding-3-small:1536")
        self.assertEqual(embedder.base_url, "https://openrouter.ai/api/v1")

    def test_signature_versionne_le_cache(self):
        embedder = create_embedder("openai", model="m", dim=1024)
        self.assertEqual(embedder.signature, "openai:m:1024")
        self.assertEqual(create_embedder("openai", model="m", dim=768).signature,
                         "openai:m:768")

    def test_fournisseur_inconnu(self):
        with self.assertRaises(SystemExit):
            create_embedder("inexistant")


class TestCache(unittest.TestCase):
    def test_cle_invalidee_par_modele_ou_texte(self):
        cle = embed_articles.cache_key("gemini:m:768", "texte")
        self.assertNotEqual(cle, embed_articles.cache_key("gemini:m:768", "autre"))
        self.assertNotEqual(cle, embed_articles.cache_key("openai:m:768", "texte"))
        self.assertNotEqual(cle, embed_articles.cache_key("gemini:m:1024", "texte"))

    def test_aller_retour_et_cache_corrompu(self):
        with tempfile.TemporaryDirectory() as tmp:
            original, embed_articles.CACHE = embed_articles.CACHE, Path(tmp) / "cache.json"
            try:
                signature = "fake:fake-model:3"
                embed_articles.sauver_cache(signature, {"abc": [0.1, 0.2, 0.3]})
                self.assertEqual(embed_articles.charger_cache(signature),
                                 {"abc": [0.1, 0.2, 0.3]})
                self.assertEqual(embed_articles.charger_cache("autre:modele:3"), {})
                embed_articles.CACHE.write_text("{pas du json", encoding="utf-8")
                self.assertEqual(embed_articles.charger_cache(signature), {})
            finally:
                embed_articles.CACHE = original


class TestVectorSearch(unittest.TestCase):
    """Choisit SEARCH (2026.01+) ou la procédure (5.x) selon la version serveur."""

    def _faux_run(self, version):
        appels = []

        def run(query, **params):
            appels.append((query, params))
            if "dbms.components" in query:
                return ([{"v": version}], None, None)
            return ([{"n": "1", "titre": "T", "score": 0.9}], None, None)

        return run, appels

    def test_search_sur_neo4j_2026(self):
        run, appels = self._faux_run("2026.10.1")
        resultat = embed_articles.vector_search(run, "idx", 5, [1.0])
        self.assertIn("SEARCH a IN (VECTOR INDEX idx", appels[-1][0])
        self.assertEqual(resultat[0]["n"], "1")

    def test_procedure_sur_neo4j_5x(self):
        run, appels = self._faux_run("5.26.0")
        embed_articles.vector_search(run, "idx", 5, [1.0])
        self.assertIn("db.index.vector.queryNodes", appels[-1][0])

    def test_nom_index_invalide(self):
        run, _ = self._faux_run("2026.10.1")
        with self.assertRaises(SystemExit):
            embed_articles.vector_search(run, "idx; DROP", 5, [1.0])


class TestOpenRouter(unittest.TestCase):
    """Vérifie le contrat HTTP OpenRouter sans appel réseau réel."""

    def _serveur(self):
        appels = []

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                appels.append({"path": self.path,
                               "headers": {k.lower(): v for k, v in self.headers.items()},
                               "body": body})
                data = [{"index": i, "embedding": [3.0, 4.0, 0.0]}
                        for i in range(len(body["input"]))]
                payload = json.dumps({"data": data}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

        serveur = HTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=serveur.serve_forever, daemon=True).start()
        self.addCleanup(serveur.shutdown)
        return f"http://127.0.0.1:{serveur.server_port}/api/v1", appels

    def test_entetes_et_payload_complets(self):
        url, appels = self._serveur()
        embedder = OpenRouterEmbedder(
            model="openai/text-embedding-3-small", dim=3, base_url=url,
            api_key="sk-or-test", site_url="https://example.org", app_name="JuriGraph",
            send_dimensions=True, input_type=True, batch_size=2)
        embedder.pause = 0
        vecteurs = embedder.embed_documents(["a", "b"])

        self.assertEqual(vecteurs, [[0.6, 0.8, 0.0], [0.6, 0.8, 0.0]])
        appel = appels[0]
        self.assertEqual(appel["path"], "/api/v1/embeddings")
        self.assertEqual(appel["headers"]["authorization"], "Bearer sk-or-test")
        self.assertEqual(appel["headers"]["x-title"], "JuriGraph")
        self.assertEqual(appel["headers"]["http-referer"], "https://example.org")
        self.assertEqual(appel["body"], {
            "model": "openai/text-embedding-3-small", "input": ["a", "b"],
            "dimensions": 3, "input_type": "search_document"})

    def test_payload_minimal_par_defaut(self):
        url, appels = self._serveur()
        embedder = OpenRouterEmbedder(model="m", dim=3, base_url=url, api_key="k",
                                      send_dimensions=False, input_type=False)
        embedder.embed_documents(["a"])
        self.assertEqual(appels[0]["body"], {"model": "m", "input": ["a"]})

    def test_requete_envoie_search_query(self):
        url, appels = self._serveur()
        embedder = OpenRouterEmbedder(model="m", dim=3, base_url=url, api_key="k",
                                      input_type=True)
        self.assertEqual(len(embedder.embed_query("q")), 3)
        self.assertEqual(appels[0]["body"]["input_type"], "search_query")

    def test_cle_manquante(self):
        embedder = OpenRouterEmbedder(model="m", dim=3, base_url="http://127.0.0.1:1/v1")
        embedder.api_key = ""            # force, même si OPENROUTER_API_KEY est défini
        with self.assertRaises(EmbeddingError):
            embedder.embed_documents(["a"])


if __name__ == "__main__":
    unittest.main()
