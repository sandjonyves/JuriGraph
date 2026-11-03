"""Tests de la couche LLM (bibliothèque standard uniquement).

    python -m unittest discover -s tests
"""
import json
import os
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest.mock import patch

from llm import PROVIDERS, create_chat
from llm.base import ChatError
from llm.openai_compat import OpenAICompatibleChat, OpenRouterChat


class FauxServeur:
    """Serveur HTTP local qui rejoue une file de réponses."""

    def __init__(self, reponses):
        self.reponses = list(reponses)
        self.appels = []
        serveur = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                corps = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                serveur.appels.append({
                    "path": self.path,
                    "headers": {k.lower(): v for k, v in self.headers.items()},
                    "body": corps,
                })
                statut, contenu = (serveur.reponses.pop(0)
                                   if serveur.reponses else (500, {"error": "vide"}))
                charge = json.dumps(contenu).encode("utf-8")
                self.send_response(statut)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(charge)))
                self.end_headers()
                self.wfile.write(charge)

        self.httpd = HTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.httpd.server_port}/v1"

    def fermer(self):
        self.httpd.shutdown()
        self.httpd.server_close()


def reponse_ok(texte="bonjour"):
    return {
        "choices": [{"message": {"content": texte}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 3},
    }


class TestOpenAICompatibleChat(unittest.TestCase):
    def _serveur(self, reponses):
        serveur = FauxServeur(reponses)
        self.addCleanup(serveur.fermer)
        return serveur

    def test_succes_et_payload(self):
        serveur = self._serveur([(200, reponse_ok())])
        chat = OpenAICompatibleChat(
            model="mon-modele", api_key="cle-test", base_url=serveur.url,
            base_delay=0, jitter=0)
        resultat = chat.generate("systeme", "utilisateur")

        self.assertEqual(resultat.text, "bonjour")
        self.assertEqual((resultat.tokens_in, resultat.tokens_out), (10, 3))
        appel = serveur.appels[0]
        self.assertEqual(appel["path"], "/v1/chat/completions")
        self.assertEqual(appel["headers"]["authorization"], "Bearer cle-test")
        self.assertEqual(appel["body"]["model"], "mon-modele")
        self.assertEqual(appel["body"]["temperature"], 0.0)
        self.assertEqual(appel["body"]["messages"], [
            {"role": "system", "content": "systeme"},
            {"role": "user", "content": "utilisateur"},
        ])
        self.assertNotIn("response_format", appel["body"])

    def test_schema_demande_json(self):
        serveur = self._serveur([(200, reponse_ok("{}"))])
        chat = OpenAICompatibleChat(
            model="m", api_key="k", base_url=serveur.url, base_delay=0, jitter=0)
        chat.generate("s", "u", schema={"type": "object"})
        self.assertEqual(serveur.appels[0]["body"]["response_format"],
                         {"type": "json_object"})

    def test_429_puis_succes(self):
        serveur = self._serveur([
            (429, {"error": "quota"}),
            (200, reponse_ok("réparé")),
        ])
        chat = OpenAICompatibleChat(
            model="m", api_key="k", base_url=serveur.url,
            max_retries=3, base_delay=0, jitter=0)
        resultat = chat.generate("s", "u")

        self.assertEqual(resultat.text, "réparé")
        self.assertEqual(len(serveur.appels), 2)

    def test_401_definitif_non_retente(self):
        serveur = self._serveur([(401, {"error": "clé invalide"})])
        chat = OpenAICompatibleChat(
            model="m", api_key="k", base_url=serveur.url,
            max_retries=3, base_delay=0, jitter=0)
        with self.assertRaises(ChatError) as contexte:
            chat.generate("s", "u")

        self.assertFalse(contexte.exception.transient)
        self.assertEqual(len(serveur.appels), 1)

    def test_openrouter_entetes(self):
        serveur = self._serveur([(200, reponse_ok())])
        chat = OpenRouterChat(
            model="m", api_key="k", base_url=serveur.url,
            site_url="https://example.org", app_name="JuriGraph",
            base_delay=0, jitter=0)
        chat.generate("s", "u")

        entetes = serveur.appels[0]["headers"]
        self.assertEqual(entetes["authorization"], "Bearer k")
        self.assertEqual(entetes["x-title"], "JuriGraph")
        self.assertEqual(entetes["http-referer"], "https://example.org")


class TestCreateChat(unittest.TestCase):
    def test_model_manquant(self):
        with patch.dict(os.environ, {"LLM_PROVIDER": "openai", "LLM_MODEL": ""}):
            with self.assertRaises(SystemExit) as contexte:
                create_chat()
        self.assertIn("LLM_MODEL", str(contexte.exception))

    def test_provider_manquant(self):
        with patch.dict(os.environ, {"LLM_PROVIDER": "", "LLM_MODEL": "m"}):
            with self.assertRaises(SystemExit) as contexte:
                create_chat()
        self.assertIn("LLM_PROVIDER", str(contexte.exception))

    def test_valeurs_par_defaut(self):
        with patch.dict(os.environ, {"LLM_PROVIDER": "openai", "LLM_MODEL": "mon-modele"}):
            chat = create_chat()
        self.assertEqual(chat.name, "openai")
        self.assertEqual(chat.model, "mon-modele")

    def test_provider_inconnu(self):
        with self.assertRaises(SystemExit):
            create_chat("inexistant", model="m")

    def test_fournisseurs_disponibles(self):
        for nom in ("openai", "openrouter", "ollama", "gemini"):
            self.assertIn(nom, PROVIDERS)


if __name__ == "__main__":
    unittest.main()
