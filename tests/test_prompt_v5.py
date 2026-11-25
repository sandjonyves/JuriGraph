"""Tests hors ligne de conformité du prompt d'extraction V5 au schéma V5."""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path
from typing import get_args

import schemas.extraction_v5 as schema
from schemas.extraction_v5 import FicheV5

RACINE = Path(__file__).resolve().parents[1]
PROMPT = RACINE / "prompts" / "extraction_v5.md"

CHAMPS_MODELES = [
    "FicheV5",
    "Source",
    "Mesure",
    "FormulePeine",
    "QuantumPeine",
    "Peine",
    "ElementConstitutif",
    "Infraction",
    "Condition",
    "GroupeConditions",
    "GroupePeines",
    "EffetRegle",
    "RegleGenerale",
    "Cible",
    "Renvoi",
    "DispositionRegime",
    "Incertitude",
]

ENUMS = [
    "TypeArticle",
    "Statut",
    "StatutRenvoi",
    "PorteeCondition",
    "CategorieCondition",
    "NaturePeine",
    "CategoriePeine",
    "ModaliteApplication",
    "OriginePeine",
    "ModeQuantum",
    "TypeFormule",
    "TypeInformation",
    "TypeRenvoi",
    "PorteeRenvoi",
    "TypeCible",
    "TypeRegle",
    "TypeEffet",
    "TypeDisposition",
    "PublicDisposition",
    "ObjetIncertitude",
    "MotifIncertitude",
    "NiveauIncertitude",
    "RelationGroupePeines",
]

ANCIENS_CHAMPS_V4 = [
    "peines_au_choix",
    "quantum_min",
    "quantum_max",
    "unite_min",
    "unite_max",
    "peines_renvoi",
]

CAS_CRITIQUES = [
    "124",
    "158",
    "289",
    "347",
    "135-2",
    "226",
    "164",
    "17",
    "18",
    "18-1",
    "19",
    "21",
]


class TestPromptV5(unittest.TestCase):
    """Le prompt V5 doit rester aligné sur le schéma et les cas d'audit."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.texte = PROMPT.read_text(encoding="utf-8")

    def test_fichier_existe_et_non_vide(self):
        self.assertTrue(PROMPT.exists())
        self.assertGreater(len(self.texte), 5000)
        self.assertIn("FicheV5", self.texte)

    def test_tous_les_champs_des_modeles_sont_documentes(self):
        for nom in CHAMPS_MODELES:
            modele = getattr(schema, nom)
            for champ in modele.model_fields:
                with self.subTest(modele=nom, champ=champ):
                    self.assertIn(champ, self.texte)

    def test_toutes_les_valeurs_autorisees_sont_documentees(self):
        for nom in ENUMS:
            alias = getattr(schema, nom)
            for valeur in get_args(alias):
                with self.subTest(enum=nom, valeur=valeur):
                    self.assertIn(valeur, self.texte)

    def test_champs_racine_et_gabarit_valide(self):
        self.assertIn('"schema_version": "5.0"', self.texte)
        blocs = re.findall(r"```json\n(.*?)\n```", self.texte, flags=re.DOTALL)
        self.assertGreaterEqual(len(blocs), 2)
        donnees = [json.loads(bloc) for bloc in blocs]
        gabarit = next(bloc for bloc in donnees if bloc["article"] == "<numéro>")
        self.assertEqual(set(gabarit), set(FicheV5.model_fields))
        FicheV5.model_validate(gabarit)
        for bloc in donnees:
            self.assertEqual(bloc["schema_version"], "5.0")

    def test_exemple_226_valide_structurellement(self):
        blocs = re.findall(r"```json\n(.*?)\n```", self.texte, flags=re.DOTALL)
        donnees = [json.loads(bloc) for bloc in blocs]
        exemple = next(bloc for bloc in donnees if bloc["article"] == "226")
        fiche = FicheV5.model_validate(exemple)
        self.assertEqual(len(fiche.infractions), 1)
        confiscation = next(
            peine for peine in fiche.infractions[0].peines
            if peine.nature == "confiscation"
        )
        self.assertEqual(confiscation.objet, "marchandises")
        self.assertEqual(fiche.groupes_peines[0].relation, "cumulative")

    def test_cas_critiques_presents(self):
        for article in CAS_CRITIQUES:
            with self.subTest(article=article):
                self.assertRegex(
                    self.texte,
                    rf"(?i)(article\s+{re.escape(article)}|\*\*{re.escape(article)}\*\*)",
                )

    def test_regles_metier_critiques_presentes(self):
        attendus = [
            "une seule `INF-124-1`",
            "echelle_conditionnelle",
            "COND-158-A",
            "GC-158-AB",
            "COND-289-1",
            "GC-289-AB",
            "REG-347-1",
            "aucune infraction",
            "REG-135-2-4",
            "multiple_profit",
            "cumul_ou_alternative",
            "cumulative",
            "REN-164-1",
            "textuelle",
            "ne classe pas ce renvoi en `non_resolue`",
            "PEI-226-1-2",
            "objet = \"marchandises\"",
            "DIS-18-1-1",
            "schema_version",
        ]
        for extrait in attendus:
            with self.subTest(extrait=extrait):
                self.assertIn(extrait, self.texte)

    def test_aucun_champ_v4_ne_subsiste(self):
        for champ in ANCIENS_CHAMPS_V4:
            with self.subTest(champ=champ):
                self.assertNotIn(champ, self.texte)

    def test_consigne_de_sortie_json_pur(self):
        self.assertIn("sans balise Markdown", self.texte)
        self.assertIn("sans texte avant ou après", self.texte)
        self.assertIn("un seul objet JSON", self.texte)


if __name__ == "__main__":
    unittest.main()
