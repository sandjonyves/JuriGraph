"""Tests hors ligne du schéma d'extraction juridique V5."""
from __future__ import annotations

import copy
import json
import re
import unittest
from functools import lru_cache
from pathlib import Path

from pydantic import ValidationError

from schemas.extraction_v5 import (
    FicheV5,
    Incertitude,
    Peine,
    Source,
    valider_fiche_v5,
)

RACINE = Path(__file__).resolve().parents[1]
DOCUMENT_V5 = RACINE / "docs" / "SCHEMA_EXTRACTION_V5_PROPOSITION.md"
CORPUS = RACINE / "code_penal_structure_docx.json"


@lru_cache(maxsize=1)
def exemples_document() -> dict[str, dict]:
    """Charge les exemples JSON du document de proposition V5."""
    texte = DOCUMENT_V5.read_text(encoding="utf-8")
    blocs = [
        json.loads(bloc)
        for bloc in re.findall(r"```json\n(.*?)\n```", texte, flags=re.S)
    ]
    return {bloc["article"]: bloc for bloc in blocs}


@lru_cache(maxsize=1)
def textes_corpus() -> dict[str, dict]:
    """Construit les textes d'articles et d'alinéas depuis le corpus local."""
    data = json.loads(CORPUS.read_text(encoding="utf-8"))
    resultat = {}

    def ajouter(article: dict) -> None:
        alineas = {
            alinea["numero"]: alinea["texte"]
            for alinea in article.get("alineas", [])
        }
        parties = [article.get("texte_brut", "")]
        parties += [
            f"({alinea['numero']}) {alinea['texte']}"
            for alinea in article.get("alineas", [])
        ]
        alineas[None] = "\n".join(partie for partie in parties if partie)
        resultat[article["numero"]] = alineas

    for livre in data["livres"]:
        for titre in livre["titres"]:
            for chapitre in titre["chapitres"]:
                for article in chapitre.get("articles", []):
                    ajouter(article)
                for section in chapitre.get("sections", []):
                    for article in section.get("articles", []):
                        ajouter(article)
    return resultat


def exemple(article: str) -> dict:
    """Retourne une copie modifiable d'un exemple du document."""
    return copy.deepcopy(exemples_document()[article])


def source(
    article: str,
    citation: str,
    type_information: str = "infraction",
    alinea: str | None = None,
) -> dict:
    """Construit une source minimale."""
    return {
        "article": article,
        "alinea": alinea,
        "citation": citation,
        "type_information": type_information,
    }


def infraction_minimale(article: str) -> dict:
    """Construit une infraction minimale pour tester les garde-fous."""
    texte = textes_corpus()[article][None]
    return {
        "id": f"INF-{article}-1",
        "libelle": "Infraction de test",
        "libelle_source": "reformulation",
        "origine": "texte",
        "elements_constitutifs": [{
            "id": f"ELT-{article}-1-1",
            "type": "materiel",
            "texte": "Fait de test",
            "groupe_alternatif": None,
            "sources": [source(article, texte, "element")],
            "statut": "explicite",
        }],
        "peines": [{
            "id": f"PEI-{article}-1-1",
            "categorie": "principale",
            "nature": "amende",
            "sous_type": None,
            "objet": None,
            "modalites": [],
            "modalite_application": "obligatoire",
            "quantum": {
                "mode": "fixe",
                "valeur": {
                    "type": "montant",
                    "valeur": 1,
                    "unite": "francs",
                    "unite_source": "francs",
                },
            },
            "origine": "texte",
            "renvoi_ids": [],
            "condition_groupe_ids": [],
            "sources": [source(article, texte, "quantum")],
            "statut": "explicite",
        }],
        "renvoi_ids": [],
        "sources": [source(article, texte, "infraction")],
        "statut": "explicite",
    }


def fiche_regime(
    article: str,
    type_disposition: str,
    natures: list[str],
    categories: list[str] | None = None,
) -> dict:
    """Construit une fiche de disposition de régime minimale."""
    texte = textes_corpus()[article][None]
    return {
        "schema_version": "5.0",
        "article": article,
        "type_article": "regime_peines",
        "infractions": [],
        "regles_generales": [],
        "dispositions_regime": [{
            "id": f"DIS-{article}-1",
            "type": type_disposition,
            "libelle": "Disposition de test",
            "description": "Disposition de régime issue du corpus.",
            "public": "toutes",
            "natures_citees": natures,
            "categories_infraction": categories or [],
            "renvoi_ids": [],
            "sources": [source(article, texte, "disposition")],
            "statut": "explicite",
        }],
        "conditions": [],
        "groupes_conditions": [],
        "groupes_peines": [],
        "renvois": [],
        "incertitudes": [],
    }


def valider_exemple(article: str) -> FicheV5:
    """Valide un exemple du document contre le corpus local."""
    return valider_fiche_v5(exemple(article), textes_corpus())


class TestExemplesDocument(unittest.TestCase):
    """Les exemples de conception doivent être valides en V5."""

    def test_huit_exemples_charges_et_valides(self):
        self.assertEqual(
            set(exemples_document()),
            {"289", "347", "124", "158", "135-2", "226", "164", "18"},
        )
        for article in exemples_document():
            with self.subTest(article=article):
                fiche = valider_exemple(article)
                self.assertEqual(fiche.article, article)

    def test_124_une_infraction_trois_peines(self):
        fiche = valider_exemple("124")
        self.assertEqual(len(fiche.infractions), 1)
        self.assertEqual(len(fiche.infractions[0].peines), 3)

    def test_158_condition_commune_aux_deux_peines(self):
        fiche = valider_exemple("158")
        condition = next(
            condition for condition in fiche.conditions
            if condition.id == "COND-158-A"
        )
        self.assertEqual(condition.portee, "commune")
        peines = [
            peine.id for peine in fiche.regles_generales[0].peines
            if set(peine.condition_groupe_ids) & {"GC-158-A", "GC-158-AB"}
        ]
        self.assertEqual(peines, ["PEI-158-R1-1", "PEI-158-R1-2"])

    def test_289_condition_commune_aux_deux_durees(self):
        fiche = valider_exemple("289")
        penalties = {
            peine.id: peine for peine in fiche.infractions[0].peines
        }
        self.assertIn("GC-289-A", penalties["PEI-289-1-3"].condition_groupe_ids)
        self.assertIn("GC-289-AB", penalties["PEI-289-1-4"].condition_groupe_ids)
        self.assertIn("COND-289-1", {
            condition.id for condition in fiche.conditions
            if condition.portee == "commune"
        })

    def test_347_sans_infraction_et_deux_regles(self):
        fiche = valider_exemple("347")
        self.assertEqual(fiche.infractions, [])
        self.assertEqual(len(fiche.regles_generales), 2)
        self.assertFalse(any(
            "outrage" in infraction.libelle.lower()
            for infraction in fiche.infractions
        ))

    def test_135_2_formule_non_transformee_en_montant_fixe(self):
        fiche = valider_exemple("135-2")
        self.assertEqual(len(fiche.infractions), 2)
        regle = next(regle for regle in fiche.regles_generales
                     if regle.id == "REG-135-2-4")
        effet = regle.effets[0]
        self.assertEqual(effet.type, "formule")
        self.assertIsNotNone(effet.formule)
        self.assertEqual(effet.formule.facteur, 10.0)
        self.assertEqual(effet.formule.base, "profit_realise")
        self.assertEqual(effet.formule.plancher, "profit_realise")

    def test_226_confiscation_explicite(self):
        fiche = valider_exemple("226")
        confiscation = next(
            peine for peine in fiche.infractions[0].peines
            if peine.nature == "confiscation"
        )
        self.assertEqual(confiscation.categorie, "accessoire")
        self.assertEqual(confiscation.objet, "marchandises")
        self.assertEqual(fiche.groupes_peines[0].relation, "cumulative")

    def test_164_renvoi_textuel_accepte(self):
        fiche = valider_exemple("164")
        renvoi = next(renvoi for renvoi in fiche.renvois
                      if renvoi.id == "REN-164-1")
        peine = fiche.infractions[0].peines[0]
        self.assertEqual(renvoi.statut, "textuelle")
        self.assertEqual(renvoi.cibles[0].statut, "textuelle")
        self.assertEqual(peine.origine, "renvoi")
        self.assertEqual(peine.nature, "indeterminee")


class TestChampsObligatoiresEtStrictes(unittest.TestCase):
    """Les champs obligatoires, énumérations et champs inconnus sont contrôlés."""

    def test_schema_version_obligatoire(self):
        fiche = exemple("289")
        del fiche["schema_version"]
        with self.assertRaises(ValidationError):
            FicheV5.model_validate(fiche)

    def test_article_et_type_article_obligatoires(self):
        for champ in ("article", "type_article"):
            fiche = exemple("289")
            del fiche[champ]
            with self.subTest(champ=champ):
                with self.assertRaises(ValidationError):
                    FicheV5.model_validate(fiche)

    def test_listes_racines_obligatoires(self):
        for champ in ("infractions", "regles_generales"):
            fiche = exemple("289")
            del fiche[champ]
            with self.subTest(champ=champ):
                with self.assertRaises(ValidationError):
                    FicheV5.model_validate(fiche)

    def test_type_article_invalide(self):
        fiche = exemple("289")
        fiche["type_article"] = "autre"
        with self.assertRaises(ValidationError):
            FicheV5.model_validate(fiche)

    def test_nature_penale_inconnue(self):
        fiche = exemple("289")
        fiche["infractions"][0]["peines"][0]["nature"] = "inconnue"
        with self.assertRaises(ValidationError):
            FicheV5.model_validate(fiche)

    def test_champ_inconnu_refuse(self):
        fiche = exemple("289")
        fiche["confiance"] = 0.9
        with self.assertRaises(ValidationError):
            FicheV5.model_validate(fiche)

    def test_champ_inconnu_refuse_dans_objet_imbrique(self):
        fiche = exemple("289")
        fiche["conditions"][0]["sources"][0]["confiance"] = 1
        with self.assertRaises(ValidationError):
            FicheV5.model_validate(fiche)

    def test_quantum_incoherent_refuse(self):
        fiche = exemple("226")
        quantum = fiche["infractions"][0]["peines"][0]["quantum"]
        quantum["minimum"] = None
        with self.assertRaises(ValidationError):
            FicheV5.model_validate(fiche)

    def test_mesure_negative_refusee(self):
        fiche = exemple("226")
        fiche["infractions"][0]["peines"][0]["quantum"]["minimum"]["valeur"] = -1
        with self.assertRaises(ValidationError):
            FicheV5.model_validate(fiche)


class TestIdentifiantsEtReferences(unittest.TestCase):
    """Les identifiants et références internes sont contrôlés."""

    def test_id_duplique(self):
        fiche = exemple("289")
        fiche["incertitudes"].append(copy.deepcopy(fiche["incertitudes"][0]))
        with self.assertRaises(ValidationError) as contexte:
            FicheV5.model_validate(fiche)
        self.assertIn("ID_DUPLIQUE", str(contexte.exception))

    def test_id_mauvais_prefixe(self):
        fiche = exemple("289")
        fiche["conditions"][0]["id"] = "COND-999-1"
        with self.assertRaises(ValidationError) as contexte:
            FicheV5.model_validate(fiche)
        self.assertIn("ID_INVALIDE", str(contexte.exception))

    def test_id_suffixe_manquant(self):
        fiche = exemple("289")
        fiche["conditions"][0]["id"] = "COND-289-"
        with self.assertRaises(ValidationError) as contexte:
            FicheV5.model_validate(fiche)
        self.assertIn("ID_INVALIDE", str(contexte.exception))

    def test_reference_inconnue(self):
        fiche = exemple("289")
        fiche["infractions"][0]["peines"][2]["condition_groupe_ids"] = [
            "GC-289-Z"
        ]
        with self.assertRaises(ValidationError) as contexte:
            FicheV5.model_validate(fiche)
        self.assertIn("REF_INCONNUE", str(contexte.exception))

    def test_reference_mauvais_type(self):
        fiche = exemple("289")
        fiche["infractions"][0]["peines"][2]["condition_groupe_ids"] = [
            "COND-289-1"
        ]
        with self.assertRaises(ValidationError) as contexte:
            FicheV5.model_validate(fiche)
        self.assertIn("REF_INCOMPATIBLE", str(contexte.exception))

    def test_cible_interne_inconnue(self):
        fiche = exemple("124")
        cible = fiche["renvois"][0]["cibles"][0]
        cible.update({
            "type": "infraction",
            "article": None,
            "alinea": None,
            "id_interne": "INF-999-1",
        })
        with self.assertRaises(ValidationError) as contexte:
            FicheV5.model_validate(fiche)
        self.assertIn("CIBLE_INTERNE_INCONNUE", str(contexte.exception))


class TestConditionsEtGroupes(unittest.TestCase):
    """Les conditions communes, groupes et cycles sont contrôlés."""

    def test_condition_commune_utilisee_une_seule_fois(self):
        fiche = exemple("289")
        fiche["infractions"][0]["peines"][3]["condition_groupe_ids"] = []
        with self.assertRaises(ValidationError) as contexte:
            FicheV5.model_validate(fiche)
        self.assertIn("CONDITION_COMMUNE_UNIQUE", str(contexte.exception))

    def test_condition_propre_sans_usage(self):
        fiche = exemple("289")
        fiche["conditions"][1]["portee"] = "propre"
        fiche["infractions"][0]["peines"][3]["condition_groupe_ids"] = []
        with self.assertRaises(ValidationError) as contexte:
            FicheV5.model_validate(fiche)
        self.assertIn("CONDITION_PORTEE_INCOHERENTE", str(contexte.exception))

    def test_groupe_ou_sans_deux_membres(self):
        fiche = exemple("289")
        fiche["groupes_conditions"][0]["operateur"] = "ou"
        with self.assertRaises(ValidationError) as contexte:
            FicheV5.model_validate(fiche)
        self.assertIn("OU", str(contexte.exception))

    def test_cycle_de_groupes_conditions(self):
        fiche = exemple("289")
        fiche["groupes_conditions"][0]["sous_groupe_ids"] = ["GC-289-AB"]
        fiche["groupes_conditions"][1]["sous_groupe_ids"] = ["GC-289-A"]
        with self.assertRaises(ValidationError) as contexte:
            FicheV5.model_validate(fiche)
        self.assertIn("GROUPE_CONDITION_CYCLE", str(contexte.exception))


class TestPeinesEtGroupesDePeines(unittest.TestCase):
    """Les peines, groupes et accessoires sont contrôlés."""

    def test_groupe_de_peines_avec_une_seule_peine(self):
        fiche = exemple("226")
        fiche["groupes_peines"][0]["peine_ids"] = ["PEI-226-1-1"]
        with self.assertRaises(ValidationError) as contexte:
            FicheV5.model_validate(fiche)
        self.assertIn("au moins deux peines", str(contexte.exception))

    def test_peine_dans_plusieurs_groupes(self):
        fiche = exemple("226")
        fiche["groupes_peines"].append({
            "id": "GP-226-2",
            "sujet_type": "infraction",
            "sujet_id": "INF-226-1",
            "relation": "cumulative",
            "peine_ids": ["PEI-226-1-1", "PEI-226-1-2"],
            "sources": [],
        })
        with self.assertRaises(ValidationError) as contexte:
            FicheV5.model_validate(fiche)
        self.assertIn("PEINE_DANS_PLUSIEURS_GROUPES", str(contexte.exception))

    def test_confiscation_sans_objet_refusee(self):
        fiche = exemple("226")
        fiche["infractions"][0]["peines"][1]["objet"] = None
        with self.assertRaises(ValidationError) as contexte:
            FicheV5.model_validate(fiche)
        self.assertIn("objet", str(contexte.exception))

    def test_nature_autre_sans_sous_type_refusee(self):
        fiche = exemple("226")
        fiche["infractions"][0]["peines"][1].update({
            "nature": "autre",
            "sous_type": None,
        })
        with self.assertRaises(ValidationError) as contexte:
            FicheV5.model_validate(fiche)
        self.assertIn("sous_type", str(contexte.exception))

    def test_peine_par_renvoi_sans_renvoi_refusee(self):
        fiche = exemple("164")
        fiche["infractions"][0]["peines"][0]["renvoi_ids"] = []
        with self.assertRaises(ValidationError) as contexte:
            FicheV5.model_validate(fiche)
        self.assertIn("renvoi", str(contexte.exception))

    def test_effet_formule_sans_formule_refuse(self):
        fiche = exemple("135-2")
        regle = next(regle for regle in fiche["regles_generales"]
                     if regle["id"] == "REG-135-2-4")
        regle["effets"][0]["formule"] = None
        with self.assertRaises(ValidationError) as contexte:
            FicheV5.model_validate(fiche)
        self.assertIn("formule", str(contexte.exception))

    def test_groupe_alternatif_valide(self):
        fiche = exemple("226")
        fiche["groupes_peines"][0]["relation"] = "alternative"
        valide = FicheV5.model_validate(fiche)
        self.assertEqual(valide.groupes_peines[0].relation, "alternative")

    def test_quantum_sous_forme_de_formule(self):
        peine = Peine.model_validate({
            "id": "PEI-999-1-1",
            "categorie": "principale",
            "nature": "amende",
            "modalite_application": "obligatoire",
            "quantum": {
                "mode": "formule",
                "formule": {
                    "type": "multiple_profit",
                    "description": "Amende égale au décuple du profit.",
                    "facteur": 10.0,
                    "base": "profit_realise",
                    "reference_ids": [],
                    "statut": "explicite",
                },
            },
            "origine": "texte",
            "sources": [source("999", "une amende", "quantum")],
            "statut": "explicite",
        })
        self.assertEqual(peine.quantum.mode, "formule")
        self.assertIsNone(peine.quantum.valeur)


class TestSourcesEtCitations(unittest.TestCase):
    """Les sources, alinéas et citations exactes sont contrôlés."""

    def test_article_source_different(self):
        fiche = exemple("289")
        fiche["conditions"][0]["sources"][0]["article"] = "288"
        with self.assertRaises(ValidationError) as contexte:
            FicheV5.model_validate(fiche)
        self.assertIn("ARTICLE_SOURCE_DIFFERENT", str(contexte.exception))

    def test_citation_absente_du_corpus(self):
        fiche = exemple("289")
        fiche["conditions"][0]["sources"][0]["citation"] += " (ajout)"
        with self.assertRaises(ValidationError) as contexte:
            valider_fiche_v5(fiche, textes_corpus())
        self.assertIn("CITATION_ABSENTE", str(contexte.exception))

    def test_alinea_inconnu(self):
        fiche = exemple("289")
        fiche["conditions"][0]["sources"][0]["alinea"] = "99"
        with self.assertRaises(ValidationError) as contexte:
            valider_fiche_v5(fiche, textes_corpus())
        self.assertIn("ALINEA_INCONNU", str(contexte.exception))

    def test_citation_normalisee_typographiquement(self):
        fiche = exemple("289")
        source_condition = fiche["conditions"][0]["sources"][0]
        source_condition["citation"] = source_condition["citation"].replace(
            "'", "’"
        ).replace(" ", "\u00a0")
        valider_fiche_v5(fiche, textes_corpus())

    def test_citation_vide_refusee(self):
        with self.assertRaises(ValidationError):
            Source.model_validate({
                "article": "289",
                "alinea": None,
                "citation": "   ",
                "type_information": "condition",
            })

    def test_offsets_inverses_refuses(self):
        with self.assertRaises(ValidationError):
            Source.model_validate({
                "article": "289",
                "alinea": "4",
                "citation": "condition",
                "type_information": "condition",
                "offset_debut": 10,
                "offset_fin": 2,
            })


class TestReglesEtRenvois(unittest.TestCase):
    """Les règles générales et les renvois typés sont contrôlés."""

    def test_infraction_inventee_sur_347_refusee(self):
        fiche = exemple("347")
        fiche["infractions"].append(infraction_minimale("347"))
        with self.assertRaises(ValidationError) as contexte:
            FicheV5.model_validate(fiche)
        self.assertIn("INFRACTION_SUR_ARTICLE_REGIME", str(contexte.exception))

    def test_renvoi_sans_cible_refuse(self):
        fiche = exemple("164")
        fiche["renvois"][0]["cibles"] = []
        with self.assertRaises(ValidationError):
            FicheV5.model_validate(fiche)

    def test_cible_textuelle_sans_libelle_refusee(self):
        fiche = exemple("164")
        fiche["renvois"][0]["cibles"][0]["libelle"] = None
        with self.assertRaises(ValidationError):
            FicheV5.model_validate(fiche)

    def test_regle_sans_effet_refusee(self):
        fiche = exemple("347")
        fiche["regles_generales"][0]["effets"] = []
        with self.assertRaises(ValidationError):
            FicheV5.model_validate(fiche)

    def test_multiplication_sans_facteur_refusee(self):
        fiche = exemple("347")
        fiche["regles_generales"][0]["effets"][0]["facteur"] = None
        with self.assertRaises(ValidationError) as contexte:
            FicheV5.model_validate(fiche)
        self.assertIn("facteur", str(contexte.exception))


class TestDispositionsDeRegime(unittest.TestCase):
    """Les articles de régime ne doivent pas produire d'infraction."""

    def test_article_18_sans_infraction(self):
        fiche = valider_exemple("18")
        self.assertEqual(fiche.infractions, [])
        self.assertEqual(len(fiche.dispositions_regime), 2)

    def test_articles_17_18_1_19_21_sans_infraction(self):
        fixtures = {
            "17": fiche_regime("17", "principe", []),
            "18-1": fiche_regime(
                "18-1", "catalogue_peines",
                ["travail_interet_general", "sanction_reparation"],
            ),
            "19": fiche_regime(
                "19", "catalogue_peines",
                ["decheance", "publication", "fermeture_etablissement",
                 "confiscation", "interdiction", "placement_surveillance"],
            ),
            "21": fiche_regime(
                "21", "classification", [],
                ["crime", "delit", "contravention"],
            ),
        }
        textes = textes_corpus()
        for article, fiche in fixtures.items():
            with self.subTest(article=article):
                valide = valider_fiche_v5(fiche, textes)
                self.assertEqual(valide.infractions, [])
                self.assertTrue(valide.dispositions_regime)

    def test_infraction_inventee_sur_18_refusee(self):
        fiche = exemple("18")
        fiche["infractions"].append(infraction_minimale("18"))
        with self.assertRaises(ValidationError) as contexte:
            FicheV5.model_validate(fiche)
        self.assertIn("INFRACTION_SUR_ARTICLE_REGIME", str(contexte.exception))


class TestIncertitudes(unittest.TestCase):
    """Les informations indéterminées sont représentables et typées."""

    def test_incertitude_sans_source_acceptee(self):
        incertitude = Incertitude.model_validate({
            "id": "INC-289-9",
            "objet": "quantum",
            "description": "Quantum non chiffré.",
            "motif": "information_absente",
            "niveau": "non_determine",
            "entites_affectees": ["PEI-289-1-1"],
        })
        self.assertEqual(incertitude.niveau, "non_determine")

    def test_motif_incertitude_inconnu_refuse(self):
        with self.assertRaises(ValidationError):
            Incertitude.model_validate({
                "id": "INC-289-9",
                "objet": "quantum",
                "description": "Quantum non chiffré.",
                "motif": "inconnu",
                "niveau": "non_determine",
            })


if __name__ == "__main__":
    unittest.main()
