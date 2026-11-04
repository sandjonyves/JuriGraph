"""Tests de l'extracteur d'infractions, sans appel réseau."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from extract_infractions import (
    _livres_par_article,
    articles_extractibles,
    charger_articles,
    construire_message,
    extraire_article,
    selectionner_articles,
    verifier_configuration_llm,
)
from llm.base import BaseChat, ChatResult


TEXTE = "Est puni d'une amende de 25 000 francs celui qui commet un vol."
ARTICLE = {
    "numero": "275",
    "titre": "Vol",
    "livre": "II",
    "texte_complet": TEXTE,
}
FICHE = {
    "article": "275",
    "infractions": [{
        "libelle": "Vol",
        "elements_constitutifs": [{
            "type": "materiel",
            "texte": "commet un vol",
            "citation": "commet un vol",
        }],
        "peines": [{
            "type": "principale",
            "nature": "amende",
            "quantum_min": 25000,
            "quantum_max": 25000,
            "unite_min": "francs",
            "unite_max": "francs",
            "perpetuite": False,
            "condition": None,
            "citation": "une amende de 25 000 francs",
        }],
        "peines_renvoi": [],
        "peines_au_choix": False,
    }],
    "conditions": [],
    "renvois": [],
}


class FauxChat(BaseChat):
    """Fournisseur factice : aucune requête réseau."""

    name = "fake"

    def __init__(self, reponse: str | None = None):
        super().__init__(model="fake-model", api_key="cle-secrete")
        self.reponse = reponse
        self.appels = 0

    def _generate(self, system, user, schema=None):
        self.appels += 1
        if self.reponse is None:
            raise AssertionError("appel inattendu au faux fournisseur")
        return ChatResult(text=self.reponse)


class TestExtractInfractions(unittest.TestCase):
    def test_articles_extractibles(self):
        articles = [
            {"numero": "1", "texte_complet": "x"},
            {"numero": "2", "texte_complet": "abc"},
            {"numero": "3", "texte_complet": "abc", "abroge": True},
            {"numero": "4", "texte_complet": "abc", "est_plage": True},
            {"numero": "5", "texte_complet": "   "},
            {"numero": "6", "texte_brut": "abc"},
        ]
        self.assertEqual(
            [a["numero"] for a in articles_extractibles(articles)],
            ["2", "6"],
        )

    def test_livres_par_article(self):
        data = {"livres": [{
            "numero": "II",
            "titres": [{"chapitres": [{
                "articles": [{"numero": "275"}],
                "sections": [{"articles": [{"numero": "276"}]}],
            }]}],
        }]}
        self.assertEqual(
            _livres_par_article(data),
            {"275": "II", "276": "II"},
        )

    def test_selection_par_numero(self):
        articles = [{"numero": "275"}, {"numero": "276"}]
        self.assertEqual(
            selectionner_articles(articles, numero="276"),
            [{"numero": "276"}],
        )
        with self.assertRaises(ValueError):
            selectionner_articles(articles, numero="999")

    def test_selection_par_limit(self):
        articles = [{"numero": "1"}, {"numero": "2"}, {"numero": "3"}]
        self.assertEqual(len(selectionner_articles(articles, limit=2)), 2)
        with self.assertRaises(ValueError):
            selectionner_articles(articles, limit=0)

    def test_selection_run(self):
        articles = [{"numero": "1"}, {"numero": "2"}]
        self.assertEqual(selectionner_articles(articles, run=True), articles)

    def test_message_contient_le_texte(self):
        message = construire_message(ARTICLE)
        self.assertIn("Article 275 — Vol", message)
        self.assertIn(TEXTE, message)

    def test_extraire_article_et_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp) / "cache.json"
            log = Path(tmp) / "logs.jsonl"
            chat = FauxChat(json.dumps(FICHE, ensure_ascii=False))
            fiche, verification, cache_hit = extraire_article(
                ARTICLE, chat, "prompt de test", {"275"}, cache, log)
            self.assertEqual(fiche.article, "275")
            self.assertEqual(verification["statut"], "auto_ok")
            self.assertFalse(cache_hit)

            second = FauxChat()
            fiche2, verification2, cache_hit2 = extraire_article(
                ARTICLE, second, "prompt de test", {"275"}, cache, log)
            self.assertTrue(cache_hit2)
            self.assertEqual(second.appels, 0)
            self.assertEqual(fiche2.article, "275")
            self.assertEqual(verification2["statut"], "auto_ok")

    def test_configuration_llm_incomplete(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(SystemExit) as contexte:
                verifier_configuration_llm()
        self.assertIn("LLM_PROVIDER", str(contexte.exception))
        self.assertIn("LLM_MODEL", str(contexte.exception))

    def test_configuration_llm_complete(self):
        with patch.dict(os.environ, {
            "LLM_PROVIDER": "openrouter",
            "LLM_MODEL": "modele-test",
            "OPENROUTER_API_KEY": "cle-test",
        }, clear=True):
            verifier_configuration_llm()

    def test_charger_articles(self):
        articles, existants = charger_articles()
        self.assertEqual(len(articles), 427)
        self.assertEqual(len(existants), 427)
        self.assertIn("275", existants)
        article = next(a for a in articles if a["numero"] == "275")
        self.assertEqual(article["livre"], "II")


if __name__ == "__main__":
    unittest.main()
