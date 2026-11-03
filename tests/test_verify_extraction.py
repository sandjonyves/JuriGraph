"""Tests du vérificateur automatique d'extraction."""
import copy
import unittest

from schemas.extraction import Fiche
from verify_extraction import A_REVOIR, AUTO_OK, REJETE, verifier

TEXTE = (
    "Sera puni d'un emprisonnement de cinq (05) à dix (10) ans et d'une amende "
    "de 25 000 francs celui qui commet un vol. Les peines sont celles de "
    "l'article 318."
)
EXISTANTS = {"275", "318"}


def article(livre=None, texte=TEXTE):
    resultat = {"numero": "275", "texte_complet": texte}
    if livre is not None:
        resultat["livre"] = livre
    return resultat


def fiche_valide():
    return {
        "article": "275",
        "infractions": [{
            "libelle": "Vol",
            "elements_constitutifs": [{
                "type": "materiel",
                "texte": "soustraction",
                "citation": "commet un vol",
            }],
            "peines": [
                {
                    "type": "principale",
                    "nature": "emprisonnement",
                    "quantum_min": 5,
                    "quantum_max": 10,
                    "unite": "ans",
                    "citation": "un emprisonnement de cinq (05) à dix (10) ans",
                },
                {
                    "type": "principale",
                    "nature": "amende",
                    "quantum_min": 25000,
                    "quantum_max": 25000,
                    "unite": "francs",
                    "citation": "une amende de 25 000 francs",
                },
            ],
            "peines_renvoi": ["318"],
        }],
        "conditions": [],
        "renvois": ["318"],
    }


class TestVerifier(unittest.TestCase):
    def test_bonne_fiche(self):
        resultat = verifier(fiche_valide(), article(), EXISTANTS)
        self.assertEqual(resultat["statut"], AUTO_OK)
        self.assertEqual(resultat["erreurs"], [])

    def test_citation_modifiee(self):
        fiche = fiche_valide()
        fiche["infractions"][0]["elements_constitutifs"][0]["citation"] = "commet le vol"
        resultat = verifier(fiche, article(), EXISTANTS)
        self.assertEqual(resultat["statut"], REJETE)
        self.assertTrue(any("citation" in e for e in resultat["erreurs"]))

    def test_chiffre_invente(self):
        fiche = fiche_valide()
        fiche["infractions"][0]["peines"][0]["quantum_min"] = 7
        resultat = verifier(fiche, article(), EXISTANTS)
        self.assertEqual(resultat["statut"], REJETE)
        self.assertTrue(any("quantum_min" in e for e in resultat["erreurs"]))

    def test_fourchette_inversee(self):
        fiche = fiche_valide()
        fiche["infractions"][0]["peines"][0]["quantum_min"] = 10
        fiche["infractions"][0]["peines"][0]["quantum_max"] = 5
        resultat = verifier(fiche, article(), EXISTANTS)
        self.assertEqual(resultat["statut"], A_REVOIR)
        self.assertTrue(any("fourchette" in e for e in resultat["erreurs"]))

    def test_unite_fausse(self):
        fiche = fiche_valide()
        fiche["infractions"][0]["peines"][1]["citation"] = "une amende de 25 000 FCFA"
        resultat = verifier(fiche, article(), EXISTANTS)
        self.assertEqual(resultat["statut"], REJETE)
        self.assertTrue(any("FCFA" in e for e in resultat["erreurs"]))

    def test_article_inexistant(self):
        fiche = fiche_valide()
        fiche["renvois"] = ["999"]
        resultat = verifier(fiche, article(), EXISTANTS)
        self.assertEqual(resultat["statut"], REJETE)
        self.assertTrue(any("999" in e and "inexistant" in e
                            for e in resultat["erreurs"]))

    def test_renvoi_existant_mais_absent_du_texte(self):
        fiche = fiche_valide()
        fiche["renvois"] = ["275"]
        resultat = verifier(fiche, article(), EXISTANTS)
        self.assertEqual(resultat["statut"], REJETE)
        self.assertTrue(any("275" in e and "absent du texte" in e
                            for e in resultat["erreurs"]))

    def test_peines_renvoi_absent_du_texte(self):
        fiche = fiche_valide()
        fiche["infractions"][0]["peines_renvoi"] = ["275"]
        resultat = verifier(fiche, article(), EXISTANTS)
        self.assertEqual(resultat["statut"], REJETE)
        self.assertTrue(any("peines_renvoi" in e for e in resultat["erreurs"]))

    def test_doublon_infraction(self):
        fiche = fiche_valide()
        fiche["infractions"].append(copy.deepcopy(fiche["infractions"][0]))
        resultat = verifier(fiche, article(), EXISTANTS)
        self.assertEqual(resultat["statut"], A_REVOIR)
        self.assertTrue(any("double" in e for e in resultat["erreurs"]))

    def test_fiche_vide_livre_i_legitime(self):
        texte = "Le tribunal prononce un emprisonnement selon les règles du Livre I."
        fiche = {"article": "10", "infractions": []}
        resultat = verifier(fiche, article(livre="I", texte=texte), EXISTANTS)
        self.assertEqual(resultat["statut"], AUTO_OK)

    def test_fiche_vide_livre_ii_suspecte(self):
        fiche = {"article": "275", "infractions": []}
        resultat = verifier(fiche, article(livre="II"), EXISTANTS)
        self.assertEqual(resultat["statut"], A_REVOIR)
        self.assertTrue(any("fiche vide" in e for e in resultat["erreurs"]))

    def test_espaces_insecables(self):
        fiche = fiche_valide()
        texte = TEXTE.replace("25 000", "25\u00a0000")
        fiche["infractions"][0]["peines"][1]["citation"] = "une amende de 25\u00a0000 francs"
        resultat = verifier(fiche, article(texte=texte), EXISTANTS)
        self.assertEqual(resultat["statut"], AUTO_OK)

    def test_condition_peine_valide(self):
        fiche = fiche_valide()
        texte = TEXTE + " En temps de guerre, la peine est celle de mort."
        fiche["infractions"][0]["peines"][0]["condition"] = "En temps de guerre"
        resultat = verifier(fiche, article(texte=texte), EXISTANTS)
        self.assertEqual(resultat["statut"], AUTO_OK)

    def test_condition_peine_inventee(self):
        fiche = fiche_valide()
        fiche["infractions"][0]["peines"][0]["condition"] = "En temps de paix"
        resultat = verifier(fiche, article(), EXISTANTS)
        self.assertEqual(resultat["statut"], REJETE)
        self.assertTrue(any("condition de peine" in e for e in resultat["erreurs"]))

    def test_fiche_pydantic(self):
        resultat = verifier(Fiche.model_validate(fiche_valide()), article(), EXISTANTS)
        self.assertEqual(resultat["statut"], AUTO_OK)


if __name__ == "__main__":
    unittest.main()
