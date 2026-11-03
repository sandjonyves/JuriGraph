"""Tests de la validation JSON, du cache et du journal LLM."""
import json
import tempfile
import unittest
from pathlib import Path

from pydantic import BaseModel

from llm.base import BaseChat, ChatResult
from llm.cache import CacheDisque
from llm.validation import LLMValidationError, generate_validated, nettoyer_json


class FicheTest(BaseModel):
    article: str
    valeur: int


class FauxChat(BaseChat):
    name = "fake"

    def __init__(self, reponses, **kwargs):
        super().__init__(model="fake-model", api_key="cle-secrete", **kwargs)
        self.reponses = list(reponses)
        self.demandes = []

    def _generate(self, system, user, schema=None):
        self.demandes.append(user)
        if not self.reponses:
            raise AssertionError("appel inattendu au faux fournisseur")
        return ChatResult(text=self.reponses.pop(0), tokens_in=5, tokens_out=2)


class TestGenerateValidated(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.cache = CacheDisque(Path(self.tmp.name) / "cache.json")
        self.log = Path(self.tmp.name) / "logs" / "runs.jsonl"

    def _appel(self, chat, **kwargs):
        return generate_validated(
            chat, "systeme", "utilisateur", FicheTest,
            cache=self.cache, log_path=self.log, **kwargs)

    def _lignes_journal(self):
        return [json.loads(l) for l in self.log.read_text(encoding="utf-8").splitlines()]

    def test_json_valide(self):
        chat = FauxChat(['{"article": "275", "valeur": 3}'])
        resultat = self._appel(chat)

        self.assertEqual(resultat.data.article, "275")
        self.assertEqual(resultat.data.valeur, 3)
        self.assertFalse(resultat.cached)
        self.assertEqual(len(chat.demandes), 1)
        lignes = self._lignes_journal()
        self.assertEqual(len(lignes), 1)
        self.assertEqual(lignes[0]["tokens_in"], 5)
        self.assertFalse(lignes[0]["cache_hit"])
        self.assertNotIn("cle-secrete", self.log.read_text(encoding="utf-8"))

    def test_json_avec_balises_markdown(self):
        chat = FauxChat(["```json\n{\"article\": \"275\", \"valeur\": 3}\n```"])
        resultat = self._appel(chat)
        self.assertEqual(resultat.data.valeur, 3)

    def test_json_invalide_puis_repare(self):
        chat = FauxChat([
            '{"article": "275"}',
            '{"article": "275", "valeur": 4}',
        ])
        resultat = self._appel(chat)

        self.assertEqual(resultat.data.valeur, 4)
        self.assertEqual(len(chat.demandes), 2)
        self.assertIn("Erreur de validation", chat.demandes[1])

    def test_invalide_deux_fois_leve_erreur(self):
        chat = FauxChat(["pas du json", "toujours pas"])
        with self.assertRaises(LLMValidationError):
            self._appel(chat)

        self.assertEqual(len(chat.demandes), 2)
        lignes = self._lignes_journal()
        self.assertEqual(lignes[-1]["tentatives"], 2)

    def test_cache_hit_n_appelle_pas_le_modele(self):
        premier = FauxChat(['{"article": "275", "valeur": 3}'])
        self._appel(premier)

        second = FauxChat([])
        resultat = self._appel(second)

        self.assertTrue(resultat.cached)
        self.assertEqual(resultat.data.valeur, 3)
        self.assertEqual(len(second.demandes), 0)
        lignes = self._lignes_journal()
        self.assertTrue(lignes[-1]["cache_hit"])

    def test_ecriture_atomique_sans_tmp(self):
        chat = FauxChat(['{"article": "275", "valeur": 3}'])
        self._appel(chat)
        self.assertTrue(self.cache.chemin.exists())
        self.assertFalse((self.cache.chemin.parent
                          / (self.cache.chemin.name + ".tmp")).exists())

    def test_nettoyer_json(self):
        self.assertEqual(nettoyer_json('```json\n{"a": 1}\n```'), '{"a": 1}')
        self.assertEqual(nettoyer_json('  {"a": 1}  '), '{"a": 1}')


if __name__ == "__main__":
    unittest.main()
