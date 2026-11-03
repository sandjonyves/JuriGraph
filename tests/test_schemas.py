"""Tests du schéma de fiche d'extraction."""
import unittest

from pydantic import ValidationError

from schemas.extraction import Element, Fiche, Infraction, Peine


def fiche_valide() -> dict:
    return {
        "article": "275",
        "infractions": [{
            "libelle": "Vol",
            "elements_constitutifs": [{
                "type": "materiel",
                "texte": "soustraction frauduleuse",
                "citation": "soustraction frauduleuse",
            }],
            "peines": [{
                "type": "principale",
                "nature": "emprisonnement",
                "quantum_min": 5,
                "quantum_max": 10,
                "unite": "ans",
                "citation": "de cinq (05) à dix (10) ans",
            }],
            "peines_renvoi": [],
        }],
        "conditions": [],
        "renvois": ["318"],
    }


class TestFiche(unittest.TestCase):
    def test_fiche_valide(self):
        fiche = Fiche.model_validate(fiche_valide())
        self.assertEqual(fiche.article, "275")
        self.assertEqual(fiche.infractions[0].peines[0].nature, "emprisonnement")

    def test_nature_inconnue(self):
        donnees = fiche_valide()
        donnees["infractions"][0]["peines"][0]["nature"] = "inconnue"
        with self.assertRaises(ValidationError):
            Fiche.model_validate(donnees)

    def test_fiche_vide_valide(self):
        fiche = Fiche.model_validate({"article": "1", "infractions": []})
        self.assertEqual(fiche.infractions, [])
        self.assertEqual(fiche.conditions, [])
        self.assertEqual(fiche.renvois, [])

    def test_pas_de_champ_confiance(self):
        self.assertNotIn("confiance", Fiche.model_fields)
        self.assertNotIn("confiance", Infraction.model_fields)

    def test_champ_inconnu_refuse(self):
        donnees = fiche_valide()
        donnees["confiance"] = 0.9
        with self.assertRaises(ValidationError):
            Fiche.model_validate(donnees)

    def test_peine_par_renvoi(self):
        infraction = Infraction.model_validate({
            "libelle": "Vol aggravé",
            "elements_constitutifs": [],
            "peines": [],
            "peines_renvoi": ["318"],
        })
        self.assertEqual(infraction.peines_renvoi, ["318"])

    def test_perpetuite(self):
        peine = Peine.model_validate({
            "type": "principale",
            "nature": "mort",
            "perpetuite": True,
            "citation": "peine de mort",
        })
        self.assertTrue(peine.perpetuite)
        self.assertIsNone(peine.quantum_min)

    def test_element_type_inconnu(self):
        with self.assertRaises(ValidationError):
            Element.model_validate({
                "type": "autre", "texte": "x", "citation": "x"})


if __name__ == "__main__":
    unittest.main()
