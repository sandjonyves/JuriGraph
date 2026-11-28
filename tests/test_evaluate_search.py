"""Tests hors ligne des métriques de evaluate_search.py (valeurs calculées à la main)."""
import math
import unittest

from evaluate_search import (
    ABLATIONS,
    agreger,
    bootstrap,
    choisir_meilleur,
    grille_utile,
    ndcg,
    permutation_appariee,
    rang_reciproque,
    rappel,
)


class TestMetriques(unittest.TestCase):
    """Métriques de recherche."""

    def test_rappel(self):
        """Un attendu sur deux dans le top 2."""
        self.assertEqual(rappel(["a", "b"], ["a", "x", "b"], 2), 0.5)
        self.assertEqual(rappel(["a", "b"], ["a", "x", "b"], 3), 1.0)

    def test_rang_reciproque(self):
        """1/rang du premier attendu, 0 s'il manque."""
        self.assertEqual(rang_reciproque(["b"], ["a", "b"]), 0.5)
        self.assertEqual(rang_reciproque(["z"], ["a", "b"]), 0.0)

    def test_ndcg_parfait(self):
        """Classement idéal : nDCG = 1."""
        self.assertAlmostEqual(ndcg(["a"], ["b"], ["a", "b", "c"]), 1.0)

    def test_ndcg_calcule_main(self):
        """Attendu au rang 2, rien d'autre : (1/log2 3) / 1."""
        self.assertAlmostEqual(ndcg(["a"], [], ["x", "a"]), 1 / math.log2(3))

    def test_ndcg_acceptable_seul(self):
        """Seul un acceptable au rang 1 : 0,5 / IDCG."""
        idcg = 1.0 + 0.5 / math.log2(3)
        self.assertAlmostEqual(ndcg(["a"], ["b"], ["b"]), 0.5 / idcg)

    def test_agreger(self):
        """Moyenne par métrique."""
        lignes = [{"R@5": 1, "R@10": 1, "MRR": 1, "nDCG@10": 1},
                  {"R@5": 0, "R@10": 1, "MRR": 0.5, "nDCG@10": 0}]
        self.assertEqual(agreger(lignes), {"R@5": 0.5, "R@10": 1.0, "MRR": 0.75, "nDCG@10": 0.5})


class TestStatistiques(unittest.TestCase):
    """Bootstrap, permutation, sélection."""

    def test_bootstrap_constante(self):
        """Valeurs constantes : intervalle réduit à un point."""
        self.assertEqual(bootstrap([1.0] * 10), (1.0, 1.0))

    def test_bootstrap_encadre_moyenne(self):
        """L'intervalle contient la moyenne observée."""
        bas, haut = bootstrap([0, 1] * 10)
        self.assertLessEqual(bas, 0.5)
        self.assertGreaterEqual(haut, 0.5)

    def test_permutation_identique(self):
        """Aucune différence : p = 1."""
        self.assertEqual(permutation_appariee([1, 0, 1], [1, 0, 1]), 1.0)

    def test_permutation_difference_nette(self):
        """Gain systématique sur 20 scénarios : p très faible."""
        self.assertLess(permutation_appariee([1.0] * 20, [0.0] * 20), 0.01)

    def test_permutation_reproductible(self):
        """Même graine, même p-valeur."""
        a, b = [1, 0, 1, 1, 0], [0, 0, 1, 0, 1]
        self.assertEqual(permutation_appariee(a, b), permutation_appariee(a, b))

    def test_choisir_meilleur(self):
        """R@10 d'abord, puis MRR."""
        res = {"A": {"R@10": 0.8, "MRR": 0.5}, "B": {"R@10": 0.8, "MRR": 0.6},
               "C": {"R@10": 0.7, "MRR": 0.9}}
        self.assertEqual(choisir_meilleur(res), "B")

    def test_grille_utile_vecteur_seul(self):
        """Sans plein texte ni graphe, seuls k_rrf et la profondeur varient."""
        grille = grille_utile(ABLATIONS["V"])
        self.assertEqual(len(grille["poids_plein_texte"]), 1)
        self.assertEqual(len(grille["poids_graphe"]), 1)

    def test_grille_utile_hybride(self):
        """Configuration complète : tous les poids varient."""
        grille = grille_utile(ABLATIONS["V+PT+R+S"])
        self.assertGreater(len(grille["poids_plein_texte"]), 1)
        self.assertGreater(len(grille["poids_graphe"]), 1)


if __name__ == "__main__":
    unittest.main()
