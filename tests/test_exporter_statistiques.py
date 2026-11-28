"""Tests hors ligne de scripts/exporter_statistiques.py (données fictives)."""
import json
import tempfile
import unittest
from pathlib import Path

from scripts.exporter_statistiques import (
    construire_classeur,
    lignes_ablations,
    lignes_renvois,
    lignes_scenarios,
)


def _mesures(r10: float) -> dict:
    """Bloc de métriques fictif."""
    return {"R@5": r10, "R@10": r10, "MRR": r10 / 2, "nDCG@10": r10, "latence": 10.0,
            "ic_R@10": [0.1, 0.9], "ic_MRR": [0.1, 0.9], "p_R@10": 1.0, "p_MRR": 1.0}


def _rapport() -> dict:
    """Rapport d'évaluation minimal."""
    ligne = {"id": "S01", "categorie": "biens", "classement": ["318", "320"],
             "sources": {}, "R@5": 1.0, "R@10": 1.0, "MRR": 1.0, "nDCG@10": 1.0}
    details = {nom: [ligne] for nom in ("V", "V+PT", "V+PT+R+S", "V+R+S")}
    return {"date": "2026-11-28", "statut": "provisoire", "n_dev": 1, "n_test": 1,
            "ablations": {"dev": {"V": _mesures(0.8), "PT": _mesures(0.2)},
                          "test": {"V": _mesures(0.9), "PT": _mesures(0.1)}},
            "details": {"dev": details, "test": {}},
            "reglage": {}, "final": {}}


ARTICLES = {"318": {"titre": "Vol", "texte": "celui qui soustrait la chose d'autrui",
                    "abroge": False, "est_plage": False}}
SCENARIOS = [{"id": "S01", "split": "dev", "categorie": "biens", "faits": "il a pris la moto",
              "attendus": ["318"], "acceptables": []},
             {"id": "S02", "split": "test", "categorie": "sans_infraction", "faits": "rien",
              "attendus": [], "acceptables": []}]


class TestExport(unittest.TestCase):
    """Préparation des lignes et assemblage du classeur."""

    def test_lignes_ablations(self):
        """Dev et test côte à côte, dans l'ordre des configurations."""
        lignes = lignes_ablations(_rapport())
        self.assertEqual([ligne[0] for ligne in lignes], ["V", "PT"])
        self.assertEqual(lignes[0][1:3], [0.8, 0.9])

    def test_lignes_scenarios_exclut_sans_infraction(self):
        """Un scénario sans attendu n'a pas de métrique."""
        lignes = lignes_scenarios(_rapport(), SCENARIOS, ARTICLES)
        self.assertEqual(lignes[0][7], 1.0)
        self.assertIsNone(lignes[1][7])
        self.assertIn("exclu", lignes[1][-1])

    def test_lignes_renvois(self):
        """Les cibles sont comptées et triées."""
        with tempfile.TemporaryDirectory() as d:
            chemin = Path(d) / "r.json"
            chemin.write_text(json.dumps([{"source": "320", "cible": "318"},
                                          {"source": "324", "cible": "318"},
                                          {"source": "1", "cible": "2"}]), encoding="utf-8")
            lignes = lignes_renvois(chemin, ARTICLES)
        self.assertEqual(lignes[0], ["Art. 318", "Vol", 2])

    def test_classeur_complet(self):
        """Le classeur contient les huit feuilles et s'enregistre."""
        wb = construire_classeur(_rapport(), SCENARIOS, ARTICLES,
                                 [["Livre I — Titre I", "x", 3]], [["Art. 318", "Vol", 2]])
        self.assertEqual(wb.sheetnames, ["Lisez-moi", "Ablations", "Réglage", "Scénarios",
                                         "Par catégorie", "Recouvrement", "Corpus",
                                         "Essais réglage"])
        self.assertTrue(wb["Ablations"]["M2"].value.startswith("="))
        with tempfile.TemporaryDirectory() as d:
            wb.save(Path(d) / "t.xlsx")


if __name__ == "__main__":
    unittest.main()
