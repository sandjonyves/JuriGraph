"""Tests hors ligne de scripts/audit_graphe.py (aucun accès Neo4j)."""
import json
import tempfile
import unittest
from pathlib import Path

from scripts.audit_graphe import charger_renvois, comparer_paires, recouvrement


class TestAuditGraphe(unittest.TestCase):
    """Fonctions pures de l'audit."""

    def test_charger_renvois_dedoublonne(self):
        """Les paires identiques ne comptent qu'une fois."""
        donnees = [{"source": "104", "cible": "102", "contexte": "x"},
                   {"source": "104", "cible": "102", "contexte": "y"},
                   {"source": 5, "cible": 6, "contexte": ""}]
        with tempfile.TemporaryDirectory() as d:
            chemin = Path(d) / "r.json"
            chemin.write_text(json.dumps(donnees), encoding="utf-8")
            self.assertEqual(charger_renvois(chemin), {("104", "102"), ("5", "6")})

    def test_comparer_paires(self):
        """Les écarts sont listés dans les deux sens."""
        ecarts = comparer_paires({("1", "2"), ("3", "4")}, {("1", "2"), ("5", "6")})
        self.assertEqual(ecarts["absents_en_base"], [("3", "4")])
        self.assertEqual(ecarts["en_trop_en_base"], [("5", "6")])

    def test_comparer_paires_identiques(self):
        """Aucun écart quand les ensembles sont égaux."""
        ecarts = comparer_paires({("1", "2")}, {("1", "2")})
        self.assertFalse(any(ecarts.values()))

    def test_recouvrement(self):
        """Indice de Jaccard sur des listes de résultats."""
        self.assertEqual(recouvrement(["a", "b"], ["b", "c"]), 1 / 3)
        self.assertEqual(recouvrement([], []), 1.0)


if __name__ == "__main__":
    unittest.main()
