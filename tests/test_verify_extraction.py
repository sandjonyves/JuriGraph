"""Tests du vérificateur automatique d'extraction."""
import copy
import unittest

from schemas.extraction import Fiche
from verify_extraction import A_REVOIR, AUTO_OK, REJETE, _nombres, verifier

TEXTE = (
    "Sera puni d'un emprisonnement de cinq (05) à dix (10) ans et d'une amende "
    "de 25 000 francs celui qui commet un vol. Les peines sont celles de "
    "l'article 318."
)
EXISTANTS = {"164", "275", "318"}


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
                    "unite_min": "ans",
                    "unite_max": "ans",
                    "citation": "un emprisonnement de cinq (05) à dix (10) ans",
                },
                {
                    "type": "principale",
                    "nature": "amende",
                    "quantum_min": 25000,
                    "quantum_max": 25000,
                    "unite_min": "francs",
                    "unite_max": "francs",
                    "citation": "une amende de 25 000 francs",
                },
            ],
            "peines_renvoi": ["318"],
            "peines_au_choix": False,
        }],
        "conditions": [],
        "renvois": ["318"],
    }


class TestNombres(unittest.TestCase):
    def test_point_separateur_milliers(self):
        self.assertEqual(_nombres("5.000"), [5000.0])
        self.assertEqual(_nombres("5.000.000"), [5000000.0])

    def test_point_decimal_non_milliers(self):
        self.assertEqual(_nombres("5.5"), [5.5])


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

    def test_fourchette_deux_unites(self):
        texte = ("Est puni d'un emprisonnement de trois (03) mois à trois (03) ans "
                 "celui qui commet le fait.")
        fiche = {
            "article": "275",
            "infractions": [{
                "libelle": "Test",
                "elements_constitutifs": [{
                    "type": "materiel",
                    "texte": "fait",
                    "citation": "commet le fait",
                }],
                "peines": [{
                    "type": "principale",
                    "nature": "emprisonnement",
                    "quantum_min": 3,
                    "quantum_max": 3,
                    "unite_min": "mois",
                    "unite_max": "ans",
                    "citation": "un emprisonnement de trois (03) mois à trois (03) ans",
                }],
                "peines_renvoi": [],
                "peines_au_choix": False,
            }],
            "conditions": [],
            "renvois": [],
        }
        resultat = verifier(fiche, article(texte=texte), EXISTANTS)
        self.assertEqual(resultat["statut"], AUTO_OK)
        self.assertEqual(resultat["erreurs"], [])

    def test_fourchette_deux_unites_inversee(self):
        texte = ("Est puni d'un emprisonnement de trois (03) ans à trois (03) mois "
                 "celui qui commet le fait.")
        fiche = {
            "article": "275",
            "infractions": [{
                "libelle": "Test",
                "elements_constitutifs": [{
                    "type": "materiel",
                    "texte": "fait",
                    "citation": "commet le fait",
                }],
                "peines": [{
                    "type": "principale",
                    "nature": "emprisonnement",
                    "quantum_min": 3,
                    "quantum_max": 3,
                    "unite_min": "ans",
                    "unite_max": "mois",
                    "citation": "un emprisonnement de trois (03) ans à trois (03) mois",
                }],
                "peines_renvoi": [],
                "peines_au_choix": False,
            }],
            "conditions": [],
            "renvois": [],
        }
        resultat = verifier(fiche, article(texte=texte), EXISTANTS)
        self.assertEqual(resultat["statut"], A_REVOIR)
        self.assertTrue(any("fourchette" in e for e in resultat["erreurs"]))

    def test_unite_absente_de_la_citation(self):
        texte = ("Est puni d'un emprisonnement de cinq (05) à dix (10) "
                 "celui qui commet le fait.")
        fiche = {
            "article": "275",
            "infractions": [{
                "libelle": "Test",
                "elements_constitutifs": [{
                    "type": "materiel",
                    "texte": "fait",
                    "citation": "commet le fait",
                }],
                "peines": [{
                    "type": "principale",
                    "nature": "emprisonnement",
                    "quantum_min": 5,
                    "quantum_max": 10,
                    "unite_min": "ans",
                    "unite_max": "ans",
                    "citation": "un emprisonnement de cinq (05) à dix (10)",
                }],
                "peines_renvoi": [],
                "peines_au_choix": False,
            }],
            "conditions": [],
            "renvois": [],
        }
        resultat = verifier(fiche, article(texte=texte), EXISTANTS)
        self.assertEqual(resultat["statut"], REJETE)
        self.assertTrue(any("unité" in e for e in resultat["erreurs"]))

    def test_alternative_mal_employee(self):
        fiche = fiche_valide()
        fiche["infractions"][0]["peines"][0]["type"] = "alternative"
        resultat = verifier(fiche, article(), EXISTANTS)
        self.assertEqual(resultat["statut"], A_REVOIR)
        self.assertTrue(any("alternative" in e for e in resultat["erreurs"]))

    def test_peines_au_choix_vrai(self):
        fiche = fiche_valide()
        fiche["infractions"][0]["peines_au_choix"] = True
        texte = TEXTE.replace(
            "l'article 318.",
            "l'article 318, ou de l'une de ces deux peines seulement.")
        resultat = verifier(fiche, article(texte=texte), EXISTANTS)
        self.assertEqual(resultat["statut"], AUTO_OK)

    def test_peines_au_choix_invente(self):
        fiche = fiche_valide()
        fiche["infractions"][0]["peines_au_choix"] = True
        resultat = verifier(fiche, article(), EXISTANTS)
        self.assertEqual(resultat["statut"], REJETE)
        self.assertTrue(any("peines_au_choix" in e for e in resultat["erreurs"]))

    def test_infraction_sans_peine_a_revoir(self):
        fiche = {
            "article": "275",
            "infractions": [{
                "libelle": "Test",
                "elements_constitutifs": [{
                    "type": "materiel",
                    "texte": "fait",
                    "citation": "commet un vol",
                }],
                "peines": [],
                "peines_renvoi": [],
                "peines_au_choix": False,
            }],
            "conditions": [],
            "renvois": [],
        }
        resultat = verifier(fiche, article(), EXISTANTS)
        self.assertEqual(resultat["statut"], A_REVOIR)
        self.assertTrue(any("aucune peine" in e
                            for e in resultat["erreurs"]))

    def test_condition_formule_sans_numero_a_revoir(self):
        for phrase in ("puni comme faux témoin", "même peine", "mêmes peines"):
            with self.subTest(phrase=phrase):
                fiche = fiche_valide()
                fiche["conditions"] = [phrase]
                resultat = verifier(
                    fiche, article(texte=TEXTE + " " + phrase), EXISTANTS)
                self.assertEqual(resultat["statut"], A_REVOIR)
                self.assertTrue(any("condition à vérifier" in e
                                    for e in resultat["erreurs"]))

    def test_choix_isole_a_revoir(self):
        fiche = fiche_valide()
        fiche["infractions"][0]["elements_constitutifs"][0]["choix"] = 1
        resultat = verifier(fiche, article(), EXISTANTS)
        self.assertEqual(resultat["statut"], A_REVOIR)
        self.assertTrue(any("choix 1 utilisé par un seul élément" in e
                            for e in resultat["erreurs"]))

    def test_deux_elements_meme_choix_ok(self):
        fiche = fiche_valide()
        fiche["infractions"][0]["elements_constitutifs"][0]["choix"] = 1
        fiche["infractions"][0]["elements_constitutifs"].append({
            "type": "materiel",
            "texte": "vol",
            "citation": "un vol",
            "choix": 1,
        })
        resultat = verifier(fiche, article(), EXISTANTS)
        self.assertEqual(resultat["statut"], AUTO_OK)

    def test_condition_avec_renvoi_a_revoir(self):
        for condition in ("l'article 227", "les articles 227 et 228"):
            with self.subTest(condition=condition):
                texte = TEXTE + " " + condition + " provoque la mort."
                fiche = fiche_valide()
                fiche["infractions"][0]["peines"][0]["condition"] = condition
                resultat = verifier(fiche, article(texte=texte), EXISTANTS)
                self.assertEqual(resultat["statut"], A_REVOIR)
                self.assertIn(
                    "condition renvoyant à d'autres articles : "
                    "possible infraction distincte",
                    resultat["erreurs"],
                )

    def test_condition_sans_renvoi_inchangee(self):
        texte = TEXTE + " en cas de récidive."
        fiche = fiche_valide()
        fiche["infractions"][0]["peines"][0]["condition"] = "en cas de récidive"
        resultat = verifier(fiche, article(texte=texte), EXISTANTS)
        self.assertEqual(resultat["statut"], AUTO_OK)

    def test_reference_infraction_base_dans_condition_peine_ok(self):
        texte = (
            "Au cas où l'infraction prévue à l'article 157 ci-dessus est commise "
            "par au moins cinq (05) personnes, la peine est de un (01) à trois (03) "
            "ans d'emprisonnement."
        )
        fiche = {
            "article": "158",
            "infractions": [{
                "libelle": "Rébellion en groupe",
                "elements_constitutifs": [{
                    "type": "legal",
                    "texte": "Infraction prévue à l'article 157",
                    "citation": "l'infraction prévue à l'article 157 ci-dessus",
                }],
                "peines": [{
                    "type": "principale",
                    "nature": "emprisonnement",
                    "quantum_min": 1,
                    "quantum_max": 3,
                    "unite_min": "ans",
                    "unite_max": "ans",
                    "perpetuite": False,
                    "condition": (
                        "Au cas où l'infraction prévue à l'article 157 ci-dessus "
                        "est commise par au moins cinq (05) personnes, la peine "
                        "est de un (01) à trois (03) ans d'emprisonnement"
                    ),
                    "citation": (
                        "la peine est de un (01) à trois (03) ans d'emprisonnement"
                    ),
                }],
                "peines_renvoi": [],
                "peines_au_choix": False,
            }],
            "conditions": [],
            "renvois": ["157"],
        }
        resultat = verifier(
            fiche, article(texte=texte), EXISTANTS | {"157"})
        self.assertEqual(resultat["statut"], AUTO_OK)
        self.assertNotIn(
            "condition renvoyant à d'autres articles : "
            "possible infraction distincte",
            resultat["erreurs"],
        )

    def test_condition_generale_renvoi_peines_a_revoir(self):
        condition = (
            "Au cas où les infractions visées aux articles 295, 296 et 347-1 "
            "ont été commises sur la personne d'un mineur de seize (16) à "
            "vingt et un (21) ans, les peines prévues auxdits articles sont "
            "doublées."
        )
        fiche = {
            "article": "347",
            "infractions": [{
                "libelle": "Outrage sur mineur",
                "elements_constitutifs": [{
                    "type": "legal",
                    "texte": "Infractions visées aux articles 295, 296 et 347-1",
                    "citation": "infractions visées aux articles 295, 296 et 347-1",
                }],
                "peines": [],
                "peines_renvoi": ["295", "296", "347-1"],
                "peines_au_choix": False,
            }],
            "conditions": [condition],
            "renvois": ["295", "296", "347-1"],
        }
        resultat = verifier(
            fiche,
            article(texte=condition),
            EXISTANTS | {"295", "296", "347-1"},
        )
        self.assertEqual(resultat["statut"], A_REVOIR)
        self.assertIn(
            "condition renvoyant aux peines d'autres articles : "
            "possible renvoi de peine",
            resultat["erreurs"],
        )

    def test_condition_generale_renvoi_alinea_meme_article_ok(self):
        condition = "Les peines prévues à l'alinéa 1 ci-dessus sont doublées."
        texte = TEXTE + " " + condition
        fiche = fiche_valide()
        fiche["conditions"] = [condition]
        resultat = verifier(fiche, article(texte=texte), EXISTANTS)
        self.assertEqual(resultat["statut"], AUTO_OK)
        self.assertEqual(resultat["erreurs"], [])

    def test_condition_peine_renvoi_peines_autre_article_a_revoir(self):
        condition = "la peine est celle de l'article 164 (2)"
        texte = TEXTE + " " + condition + "."
        fiche = fiche_valide()
        fiche["infractions"][0]["peines"][0]["condition"] = condition
        resultat = verifier(
            fiche, article(texte=texte), EXISTANTS | {"164"})
        self.assertEqual(resultat["statut"], A_REVOIR)
        self.assertIn(
            "condition renvoyant aux peines d'autres articles : "
            "possible renvoi de peine",
            resultat["erreurs"],
        )

    def test_condition_infraction_autre_avec_resultat_a_revoir(self):
        condition = (
            "au cas où l'une des infractions prévues aux articles 227, 228 "
            "provoque la mort"
        )
        texte = TEXTE + " " + condition + "."
        fiche = fiche_valide()
        fiche["infractions"][0]["peines"][0]["condition"] = condition
        resultat = verifier(
            fiche, article(texte=texte), EXISTANTS | {"227", "228"})
        self.assertEqual(resultat["statut"], A_REVOIR)
        self.assertIn(
            "condition renvoyant à d'autres articles : "
            "possible infraction distincte",
            resultat["erreurs"],
        )

    def test_peines_accessoires_conditionnelles_ok(self):
        texte = (
            "Est puni d'un emprisonnement de trois (03) mois à cinq (05) ans "
            "celui qui cause la mort. Si l'homicide ou les blessures ont été "
            "causés par le conducteur d'un véhicule dont la conduite nécessite "
            "un permis, la juridiction peut ordonner le retrait du permis de "
            "conduire ou l'interdiction de l'obtenir pour une durée maximum de "
            "trois (03) ans et, en cas de récidive, pour une durée maximum de "
            "dix (10) ans."
        )
        fiche = {
            "article": "289",
            "infractions": [{
                "libelle": "Homicide involontaire",
                "elements_constitutifs": [{
                    "type": "materiel",
                    "texte": "Causer la mort",
                    "citation": "cause la mort",
                }],
                "peines": [
                    {
                        "type": "principale",
                        "nature": "emprisonnement",
                        "quantum_min": 3,
                        "quantum_max": 5,
                        "unite_min": "mois",
                        "unite_max": "ans",
                        "perpetuite": False,
                        "condition": None,
                        "citation": (
                            "un emprisonnement de trois (03) mois à cinq (05) ans"
                        ),
                    },
                    {
                        "type": "accessoire",
                        "nature": "autre",
                        "quantum_min": None,
                        "quantum_max": 3,
                        "unite_min": None,
                        "unite_max": "ans",
                        "perpetuite": False,
                        "condition": (
                            "Si l'homicide ou les blessures ont été causés par "
                            "le conducteur d'un véhicule dont la conduite "
                            "nécessite un permis"
                        ),
                        "citation": (
                            "le retrait du permis de conduire ou l'interdiction "
                            "de l'obtenir pour une durée maximum de trois (03) ans"
                        ),
                    },
                    {
                        "type": "accessoire",
                        "nature": "autre",
                        "quantum_min": None,
                        "quantum_max": 10,
                        "unite_min": None,
                        "unite_max": "ans",
                        "perpetuite": False,
                        "condition": (
                            "Si l'homicide ou les blessures ont été causés par "
                            "le conducteur d'un véhicule dont la conduite "
                            "nécessite un permis, la juridiction peut ordonner "
                            "le retrait du permis de conduire ou l'interdiction "
                            "de l'obtenir pour une durée maximum de trois (03) "
                            "ans et, en cas de récidive, pour une durée maximum "
                            "de dix (10) ans"
                        ),
                        "citation": (
                            "en cas de récidive, pour une durée maximum de "
                            "dix (10) ans"
                        ),
                    },
                ],
                "peines_renvoi": [],
                "peines_au_choix": False,
            }],
            "conditions": [],
            "renvois": [],
        }
        resultat = verifier(fiche, article(texte=texte), EXISTANTS)
        self.assertEqual(resultat["statut"], AUTO_OK)
        self.assertEqual(resultat["erreurs"], [])

    def test_peine_avec_une_seule_condition_ok(self):
        texte = TEXTE + " en cas de récidive."
        fiche = fiche_valide()
        fiche["infractions"][0]["peines"][0]["condition"] = "en cas de récidive"
        resultat = verifier(fiche, article(texte=texte), EXISTANTS)
        self.assertEqual(resultat["statut"], AUTO_OK)

    def test_peines_alternatives_conditions_differentes_ok(self):
        texte = (
            "Est puni d'un emprisonnement de cinq (05) à dix (10) ans "
            "celui qui commet le fait. "
            "Si l'auteur est armé, la peine est de dix (10) à vingt (20) ans. "
            "Si l'infraction est commise de nuit, la peine est de cinq (05) à "
            "quinze (15) ans."
        )
        fiche = {
            "article": "275",
            "infractions": [{
                "libelle": "Infraction conditionnelle",
                "elements_constitutifs": [{
                    "type": "materiel",
                    "texte": "Commet le fait",
                    "citation": "commet le fait",
                }],
                "peines": [
                    {
                        "type": "principale",
                        "nature": "emprisonnement",
                        "quantum_min": 5,
                        "quantum_max": 10,
                        "unite_min": "ans",
                        "unite_max": "ans",
                        "perpetuite": False,
                        "condition": None,
                        "citation": "un emprisonnement de cinq (05) à dix (10) ans",
                    },
                    {
                        "type": "principale",
                        "nature": "emprisonnement",
                        "quantum_min": 10,
                        "quantum_max": 20,
                        "unite_min": "ans",
                        "unite_max": "ans",
                        "perpetuite": False,
                        "condition": "Si l'auteur est armé",
                        "citation": "la peine est de dix (10) à vingt (20) ans",
                    },
                    {
                        "type": "principale",
                        "nature": "emprisonnement",
                        "quantum_min": 5,
                        "quantum_max": 15,
                        "unite_min": "ans",
                        "unite_max": "ans",
                        "perpetuite": False,
                        "condition": "Si l'infraction est commise de nuit",
                        "citation": "la peine est de cinq (05) à quinze (15) ans",
                    },
                ],
                "peines_renvoi": [],
                "peines_au_choix": False,
            }],
            "conditions": [],
            "renvois": [],
        }
        resultat = verifier(fiche, article(texte=texte), EXISTANTS)
        self.assertEqual(resultat["statut"], AUTO_OK)
        self.assertEqual(resultat["erreurs"], [])

    def test_article_289_condition_accessoire_incomplete_a_revoir(self):
        texte = (
            "Est puni d'un emprisonnement de trois (03) mois à cinq (05) ans "
            "celui qui cause la mort. Si le conducteur d'un véhicule dont la "
            "conduite nécessite un permis cause la mort, le retrait du permis "
            "peut être ordonné pour une durée maximum de trois (03) ans et, "
            "en cas de récidive, pour une durée maximum de dix (10) ans."
        )
        fiche = {
            "article": "289",
            "infractions": [{
                "libelle": "Homicide involontaire",
                "elements_constitutifs": [{
                    "type": "materiel",
                    "texte": "Causer la mort",
                    "citation": "cause la mort",
                }],
                "peines": [
                    {
                        "type": "principale",
                        "nature": "emprisonnement",
                        "quantum_min": 3,
                        "quantum_max": 5,
                        "unite_min": "mois",
                        "unite_max": "ans",
                        "perpetuite": False,
                        "condition": None,
                        "citation": (
                            "un emprisonnement de trois (03) mois à cinq (05) ans"
                        ),
                    },
                    {
                        "type": "accessoire",
                        "nature": "autre",
                        "quantum_min": None,
                        "quantum_max": 3,
                        "unite_min": None,
                        "unite_max": "ans",
                        "perpetuite": False,
                        "condition": (
                            "Si le conducteur d'un véhicule dont la conduite "
                            "nécessite un permis cause la mort"
                        ),
                        "citation": (
                            "le retrait du permis peut être ordonné pour une "
                            "durée maximum de trois (03) ans"
                        ),
                    },
                    {
                        "type": "accessoire",
                        "nature": "autre",
                        "quantum_min": None,
                        "quantum_max": 10,
                        "unite_min": None,
                        "unite_max": "ans",
                        "perpetuite": False,
                        "condition": "en cas de récidive",
                        "citation": (
                            "en cas de récidive, pour une durée maximum de "
                            "dix (10) ans"
                        ),
                    },
                ],
                "peines_renvoi": [],
                "peines_au_choix": False,
            }],
            "conditions": [],
            "renvois": [],
        }
        resultat = verifier(fiche, article(texte=texte), EXISTANTS)
        self.assertEqual(resultat["statut"], A_REVOIR)
        self.assertTrue(any(
            "condition de peine possiblement incomplète" in erreur
            for erreur in resultat["erreurs"]
        ))

    def test_condition_depend_paragraphe_precedent_a_revoir(self):
        texte = (
            "Est puni d'un emprisonnement de trois (03) mois à cinq (05) ans "
            "celui qui cause la mort. "
            "Si le conducteur d'un véhicule dont la conduite nécessite un permis "
            "cause la mort, le retrait du permis peut être ordonné pour une "
            "durée maximum de trois (03) ans. "
            "En cas de récidive, la durée maximum est de dix (10) ans."
        )
        fiche = {
            "article": "289",
            "infractions": [{
                "libelle": "Homicide involontaire",
                "elements_constitutifs": [{
                    "type": "materiel",
                    "texte": "Causer la mort",
                    "citation": "cause la mort",
                }],
                "peines": [
                    {
                        "type": "principale",
                        "nature": "emprisonnement",
                        "quantum_min": 3,
                        "quantum_max": 5,
                        "unite_min": "mois",
                        "unite_max": "ans",
                        "perpetuite": False,
                        "condition": None,
                        "citation": (
                            "un emprisonnement de trois (03) mois à cinq (05) ans"
                        ),
                    },
                    {
                        "type": "accessoire",
                        "nature": "autre",
                        "quantum_min": None,
                        "quantum_max": 3,
                        "unite_min": None,
                        "unite_max": "ans",
                        "perpetuite": False,
                        "condition": (
                            "Si le conducteur d'un véhicule dont la conduite "
                            "nécessite un permis cause la mort"
                        ),
                        "citation": (
                            "le retrait du permis peut être ordonné pour une "
                            "durée maximum de trois (03) ans"
                        ),
                    },
                    {
                        "type": "accessoire",
                        "nature": "autre",
                        "quantum_min": None,
                        "quantum_max": 10,
                        "unite_min": None,
                        "unite_max": "ans",
                        "perpetuite": False,
                        "condition": "En cas de récidive",
                        "citation": "la durée maximum est de dix (10) ans",
                    },
                ],
                "peines_renvoi": [],
                "peines_au_choix": False,
            }],
            "conditions": [],
            "renvois": [],
        }
        resultat = verifier(fiche, article(texte=texte), EXISTANTS)
        self.assertEqual(resultat["statut"], A_REVOIR)
        self.assertTrue(any(
            "condition de peine possiblement incomplète" in erreur
            for erreur in resultat["erreurs"]
        ))

    def test_condition_infraction_renvoi_peines_a_revoir(self):
        condition = "les peines prévues à l'article 164 sont doublées"
        texte = (
            "Est puni des peines de l'article 164, l'auteur qui commet le fait. "
            "Les peines prévues à l'article 164 sont doublées."
        )
        fiche = {
            "article": "165",
            "infractions": [{
                "libelle": "Fausse expertise",
                "elements_constitutifs": [{
                    "type": "legal",
                    "texte": "Auteur",
                    "citation": "l'auteur",
                }],
                "peines": [],
                "peines_renvoi": ["164"],
                "peines_au_choix": False,
                "conditions": [condition],
            }],
            "conditions": [],
            "renvois": ["164"],
        }
        resultat = verifier(
            fiche, article(texte=texte), EXISTANTS | {"164"})
        self.assertEqual(resultat["statut"], A_REVOIR)
        self.assertIn(
            "condition renvoyant aux peines d'autres articles : "
            "possible renvoi de peine",
            resultat["erreurs"],
        )

    def test_infraction_sans_peine_ni_renvoi_explicite_a_revoir(self):
        fiche = fiche_valide()
        fiche["infractions"][0]["peines"] = []
        fiche["infractions"][0]["peines_renvoi"] = []
        resultat = verifier(fiche, article(), EXISTANTS)
        self.assertEqual(resultat["statut"], A_REVOIR)
        self.assertIn(
            "Vol : aucune peine ni renvoi de peine",
            resultat["erreurs"],
        )

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

    def test_peines_renvoi_alinea_valide(self):
        texte = ("Est puni des peines de l'article 164 (2) ci-dessus, "
                 "l'expert judiciaire qui dépose un faux rapport.")
        fiche = {
            "article": "165",
            "infractions": [{
                "libelle": "Fausse expertise",
                "elements_constitutifs": [{
                    "type": "legal",
                    "texte": "Expert judiciaire",
                    "citation": "l'expert judiciaire",
                }],
                "peines": [],
                "peines_renvoi": ["164 (2)"],
            }],
            "conditions": [],
            "renvois": ["164"],
        }
        resultat = verifier(fiche, article(texte=texte), EXISTANTS)
        self.assertEqual(resultat["statut"], AUTO_OK)

    def test_peines_renvoi_alinea_invente(self):
        texte = ("Est puni des peines de l'article 164 (2) ci-dessus, "
                 "l'expert judiciaire qui dépose un faux rapport.")
        fiche = {
            "article": "165",
            "infractions": [{
                "libelle": "Fausse expertise",
                "elements_constitutifs": [{
                    "type": "legal",
                    "texte": "Expert judiciaire",
                    "citation": "l'expert judiciaire",
                }],
                "peines": [],
                "peines_renvoi": ["164 (3)"],
            }],
            "conditions": [],
            "renvois": ["164"],
        }
        resultat = verifier(fiche, article(texte=texte), EXISTANTS)
        self.assertEqual(resultat["statut"], REJETE)
        self.assertTrue(any("164 (3)" in e and "absent" in e
                            for e in resultat["erreurs"]))

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

    def test_quantum_point_milliers_accepte(self):
        texte = ("Est puni d'une amende de 5.000 francs "
                 "celui qui commet le fait.")
        fiche = {
            "article": "275",
            "infractions": [{
                "libelle": "Test",
                "elements_constitutifs": [{
                    "type": "materiel",
                    "texte": "fait",
                    "citation": "commet le fait",
                }],
                "peines": [{
                    "type": "principale",
                    "nature": "amende",
                    "quantum_min": 5000,
                    "quantum_max": 5000,
                    "unite_min": "francs",
                    "unite_max": "francs",
                    "perpetuite": False,
                    "condition": None,
                    "citation": "une amende de 5.000 francs",
                }],
                "peines_renvoi": [],
                "peines_au_choix": False,
            }],
            "conditions": [],
            "renvois": [],
        }
        resultat = verifier(fiche, article(texte=texte), EXISTANTS)
        self.assertEqual(resultat["statut"], AUTO_OK)
        self.assertEqual(resultat["erreurs"], [])

    def test_quantum_point_decimal_non_assimile_a_5500(self):
        texte = ("Est puni d'une amende de 5.5 francs "
                 "celui qui commet le fait.")
        fiche = {
            "article": "275",
            "infractions": [{
                "libelle": "Test",
                "elements_constitutifs": [{
                    "type": "materiel",
                    "texte": "fait",
                    "citation": "commet le fait",
                }],
                "peines": [{
                    "type": "principale",
                    "nature": "amende",
                    "quantum_min": 5500,
                    "quantum_max": 5500,
                    "unite_min": "francs",
                    "unite_max": "francs",
                    "perpetuite": False,
                    "condition": None,
                    "citation": "une amende de 5.5 francs",
                }],
                "peines_renvoi": [],
                "peines_au_choix": False,
            }],
            "conditions": [],
            "renvois": [],
        }
        resultat = verifier(fiche, article(texte=texte), EXISTANTS)
        self.assertEqual(resultat["statut"], REJETE)
        self.assertTrue(any("quantum_min=5500" in e
                            for e in resultat["erreurs"]))

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
