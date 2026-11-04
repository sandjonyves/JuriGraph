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
                "unite_min": "ans",
                "unite_max": "ans",
                "citation": "de cinq (05) à dix (10) ans",
            }],
            "peines_renvoi": [],
            "peines_au_choix": False,
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
        self.assertIsNone(peine.condition)

    def test_condition_peine(self):
        peine = Peine.model_validate({
            "type": "principale",
            "nature": "mort",
            "condition": "En temps de guerre",
            "citation": "En temps de guerre, la peine est celle de mort.",
        })
        self.assertEqual(peine.condition, "En temps de guerre")

    def test_unites_separees(self):
        peine = Peine.model_validate({
            "type": "principale",
            "nature": "emprisonnement",
            "quantum_min": 3,
            "quantum_max": 3,
            "unite_min": "mois",
            "unite_max": "ans",
            "citation": "trois (03) mois à trois (03) ans",
        })
        self.assertEqual(peine.unite_min, "mois")
        self.assertEqual(peine.unite_max, "ans")

    def test_peines_au_choix(self):
        infraction = Infraction.model_validate({
            "libelle": "Test",
            "peines_au_choix": True,
        })
        self.assertTrue(infraction.peines_au_choix)
        self.assertFalse(Infraction.model_validate({"libelle": "Test"}).peines_au_choix)

    def test_element_choix(self):
        element = Element.model_validate({
            "type": "materiel",
            "texte": "Acte a",
            "citation": "acte a",
            "choix": 1,
        })
        self.assertEqual(element.choix, 1)
        obligatoire = Element.model_validate({
            "type": "materiel",
            "texte": "Acte obligatoire",
            "citation": "acte obligatoire",
        })
        self.assertIsNone(obligatoire.choix)

    def test_element_type_inconnu(self):
        with self.assertRaises(ValidationError):
            Element.model_validate({
                "type": "autre", "texte": "x", "citation": "x"})


if __name__ == "__main__":
    unittest.main()
