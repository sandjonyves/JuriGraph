"""Tests hors ligne de scripts/verifier_gold_set.py et du jeu d'évaluation."""
import unittest
from pathlib import Path

from scripts.verifier_gold_set import (
    charger_articles,
    charger_scenarios,
    controler,
    est_plage,
    normaliser,
    recouvrement_lexical,
)

RACINE = Path(__file__).resolve().parent.parent


class TestFonctions(unittest.TestCase):
    """Fonctions pures du vérificateur."""

    def test_normaliser_accents(self):
        """Les accents et apostrophes disparaissent."""
        self.assertEqual(normaliser("L'Évasion d'un détenu").split(),
                         ["l", "evasion", "d", "un", "detenu"])

    def test_est_plage(self):
        """Une plage se distingue d'un article bis."""
        self.assertTrue(est_plage("362-370"))
        self.assertFalse(est_plage("18-1"))
        self.assertFalse(est_plage("275"))

    def test_recouvrement_identique(self):
        """Un texte recopié a un recouvrement de 1."""
        texte = "celui qui détruit le bien appartenant à autrui"
        self.assertEqual(recouvrement_lexical(texte, texte), 1.0)

    def test_recouvrement_nul(self):
        """Des textes sans mot commun ont un recouvrement de 0."""
        self.assertEqual(recouvrement_lexical("chien jaune", "maison rouge"), 0.0)

    def test_controler_signale_article_inexistant(self):
        """Un numéro absent du corpus est une erreur bloquante."""
        articles = {"1": {"titre": "", "texte": "x", "abroge": False, "est_plage": False}}
        scenarios = [{"id": "S1", "faits": "x", "attendus": ["999"], "acceptables": [],
                      "split": "dev"}]
        erreurs, _ = controler(scenarios, articles)
        self.assertTrue(any("999" in e for e in erreurs))

    def test_controler_signale_doublon_attendu_acceptable(self):
        """Un article ne peut pas être à la fois attendu et acceptable."""
        articles = {"1": {"titre": "", "texte": "x", "abroge": False, "est_plage": False}}
        scenarios = [{"id": "S1", "faits": "x", "attendus": ["1"], "acceptables": ["1"],
                      "split": "test"}]
        erreurs, _ = controler(scenarios, articles)
        self.assertTrue(erreurs)


class TestJeuReel(unittest.TestCase):
    """Le jeu data/eval/faits_articles.jsonl est valide (hors ligne)."""

    def test_jeu_sans_erreur(self):
        """Tous les articles cités existent et les splits sont valides."""
        articles = charger_articles(RACINE / "code_penal_structure_docx.json")
        scenarios = charger_scenarios(RACINE / "data/eval/faits_articles.jsonl")
        erreurs, _ = controler(scenarios, articles)
        self.assertEqual(erreurs, [])


if __name__ == "__main__":
    unittest.main()
