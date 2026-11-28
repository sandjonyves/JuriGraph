"""Tests hors ligne de search_hybrid.py (faux Neo4j, faux embeddings)."""
import json
import tempfile
import unittest
from pathlib import Path

from search_hybrid import (
    CacheRequetes,
    Config,
    RechercheHybride,
    decouper_requetes,
    echapper_lucene,
    fusion_rrf,
    mots_pleins,
    requete_lucene,
)


class FauxNeo4j:
    """Répond aux requêtes du moteur selon des données fixes."""

    def __init__(self):
        self.valides = ["1", "2", "3", "4", "5", "6"]
        self.vecteur = ["2", "1", "159", "3"]          # 159 : abrogé, doit être filtré
        self.plein_texte = ["1", "4"]
        self.renvois = {"1": ["5"], "2": ["5", "6"]}
        self.voisins = {"1": ["3"], "2": ["4"]}
        self.requetes: list[str] = []

    def __call__(self, requete: str, **params):
        self.requetes.append(requete)
        if "VECTOR" in requete or "vector.queryNodes" in requete:
            return [{"n": n, "titre": "", "score": 1.0} for n in self.vecteur]
        if "RETURN a.numero AS n, a.titre AS titre" in requete:
            return [{"n": n, "titre": f"Titre {n}"} for n in self.valides]
        if "fulltext" in requete:
            return [{"n": n, "score": 1.0} for n in self.plein_texte]
        if "RENVOIE_A" in requete:
            liens: dict[str, int] = {}
            for g in params["g"]:
                for n in self.renvois.get(g, []):
                    liens[n] = liens.get(n, 0) + 1
            return [{"n": n, "liens": c} for n, c in sorted(liens.items(), key=lambda x: -x[1])]
        if "CONTIENT" in requete:
            return [{"n": n} for g in params["g"] for n in self.voisins.get(g, [])]
        if "dbms.components" in requete:
            return [{"v": "2026.10.1"}]
        raise AssertionError(f"requête inattendue : {requete}")


class TestFonctionsPures(unittest.TestCase):
    """Fusion, requêtes Lucene, découpage."""

    def test_fusion_rrf_score_et_provenance(self):
        """Un article présent dans deux listes passe devant et garde ses deux sources."""
        res = fusion_rrf([("a", ["x", "y"], 1.0), ("b", ["y", "z"], 1.0)], k=60)
        self.assertEqual(res[0].numero, "y")
        self.assertEqual(res[0].sources, ["a", "b"])
        self.assertAlmostEqual(res[0].score, 1 / 62 + 1 / 61)
        self.assertEqual([r.rang for r in res], [1, 2, 3])

    def test_fusion_rrf_poids(self):
        """Un poids nul n'apporte aucun score."""
        res = fusion_rrf([("a", ["x"], 1.0), ("b", ["z"], 0.0)], k=1)
        self.assertEqual(res[0].numero, "x")
        self.assertEqual(res[1].score, 0.0)

    def test_fusion_rrf_vide(self):
        """Aucune liste : aucun résultat."""
        self.assertEqual(fusion_rrf([]), [])

    def test_echapper_lucene(self):
        """Les caractères spéciaux sont échappés."""
        self.assertEqual(echapper_lucene('a:b(c)"d'), 'a\\:b\\(c\\)\\"d')

    def test_mots_pleins(self):
        """Mots vides, nombres et doublons retirés ; accents conservés."""
        self.assertEqual(mots_pleins("Il a volé la moto, la moto de 2020 !"), ["volé", "moto"])

    def test_requete_lucene(self):
        """Le titre est pondéré, le texte complet interrogé."""
        q = requete_lucene("vol de moto")
        self.assertEqual(q, "titre:(vol moto)^2 OR texte_complet:(vol moto)")
        self.assertEqual(requete_lucene("de la et"), "")

    def test_decouper_requetes(self):
        """Faits complets en premier, puis les phrases significatives."""
        req = decouper_requetes("Il a frappé son voisin avec un bâton. Le voisin est mort ensuite.")
        self.assertEqual(req[0], "Il a frappé son voisin avec un bâton. Le voisin est mort ensuite.")
        self.assertEqual(len(req), 3)

    def test_config_nom(self):
        """Le nom de configuration reflète les voies actives."""
        self.assertEqual(Config().nom(), "V+PT+R+S")
        self.assertEqual(Config(renvois=False, section=False, multi_requetes=True).nom(), "V+PT+MQ")


class TestMoteur(unittest.TestCase):
    """Moteur complet sur un faux graphe."""

    def setUp(self):
        self.neo = FauxNeo4j()
        self.moteur = RechercheHybride(self.neo, lambda t: [0.1, 0.2])

    def test_filtre_articles_invalides(self):
        """Un article absent des articles valides n'est jamais renvoyé."""
        res = self.moteur.rechercher("faits", k=10, config=Config(renvois=False, section=False))
        self.assertNotIn("159", [r.numero for r in res])

    def test_vecteur_seul(self):
        """Ablation : seule la voie vectorielle est utilisée."""
        cfg = Config(plein_texte=False, renvois=False, section=False)
        res = self.moteur.rechercher("faits", k=10, config=cfg)
        self.assertEqual([r.numero for r in res], ["2", "1", "3"])
        self.assertTrue(all(r.sources == ["vecteur"] for r in res))

    def test_expansion_graphe_provenance(self):
        """Les renvois et voisins ajoutent des articles avec leur source."""
        res = self.moteur.rechercher("faits", k=10, config=Config(graines=2))
        par_num = {r.numero: r for r in res}
        self.assertIn("renvoi", par_num["5"].sources)
        self.assertIn("section", par_num["4"].sources)
        self.assertEqual(par_num["1"].titre, "Titre 1")

    def test_graines_exclues_de_leur_propre_expansion(self):
        """Une graine n'est pas ajoutée comme renvoi d'elle-même."""
        self.neo.renvois = {"1": ["2"], "2": ["1"]}
        res = self.moteur.rechercher("faits", k=10, config=Config(graines=2, section=False))
        self.assertTrue(all("renvoi" not in r.sources for r in res if r.numero in ("1", "2")))

    def test_sans_embedding(self):
        """Sans modèle d'embedding, la voie vectorielle échoue clairement."""
        moteur = RechercheHybride(self.neo, None)
        with self.assertRaises(RuntimeError):
            moteur.voie_vecteur("faits", 5)


class TestCache(unittest.TestCase):
    """Cache disque des vecteurs de requêtes."""

    def test_cache_evite_second_appel(self):
        """Le second appel identique ne recalcule pas le vecteur."""
        appels = []

        def calculer(texte):
            appels.append(texte)
            return [1.0]

        with tempfile.TemporaryDirectory() as d:
            chemin = Path(d) / "c.json"
            cache = CacheRequetes(chemin, "modele")
            cache.obtenir("a", calculer)
            cache.obtenir("a", calculer)
            self.assertEqual(appels, ["a"])
            relu = CacheRequetes(chemin, "modele")
            self.assertEqual(len(json.loads(chemin.read_text())), 1)
            relu.obtenir("a", calculer)
            self.assertEqual(appels, ["a"])

    def test_cache_depend_du_modele(self):
        """Changer de modèle change la clé."""
        self.assertNotEqual(CacheRequetes(None, "m1").cle("a"), CacheRequetes(None, "m2").cle("a"))


if __name__ == "__main__":
    unittest.main()
