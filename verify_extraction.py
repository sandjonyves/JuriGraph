"""Vérificateur automatique d'une fiche d'extraction.

Le vérificateur ne juge pas le droit : il contrôle que la fiche est fidèle au
texte de l'article (citations exactes, nombres présents, renvois réels).
"""
from __future__ import annotations

import re
from typing import Any, Iterable

AUTO_OK = "auto_ok"
A_REVOIR = "a_revoir"
REJETE = "rejete"

MOTS_INFRACTION = ("emprisonnement", "amende", "puni")
UNITES_DUREE = {"ans", "mois", "jours"}


def normaliser(texte: str) -> str:
    """Normalise espaces, apostrophes et tirets avant comparaison."""
    texte = (texte or "").replace("\u00a0", " ").replace("\u202f", " ")
    texte = texte.replace("’", "'").replace("‘", "'")
    texte = texte.replace("“", '"').replace("”", '"')
    texte = texte.replace("–", "-").replace("—", "-").replace("‑", "-")
    texte = re.sub(r"\s+", " ", texte)
    return texte.strip().lower()


def _nombres(texte: str) -> list[float]:
    """Extrait les nombres, en supprimant les espaces entre chiffres."""
    texte = (texte or "").replace("\u00a0", " ").replace("\u202f", " ")
    texte = re.sub(r"(?<=\d)\s+(?=\d)", "", texte)
    resultat = []
    for valeur in re.findall(r"\d+(?:[.,]\d+)?", texte):
        try:
            resultat.append(float(valeur.replace(",", ".")))
        except ValueError:
            pass
    return resultat


def _nombre(valeur: Any) -> float | None:
    """Convertit une valeur en float, ou retourne None."""
    if valeur is None or valeur == "":
        return None
    try:
        return float(valeur)
    except (TypeError, ValueError):
        return None


def _en_jours(quantum: float, unite: str | None) -> float | None:
    """Convertit une durée en jours pour comparer des unités différentes."""
    if unite == "ans":
        return quantum * 365
    if unite == "mois":
        return quantum * 30
    if unite == "jours":
        return quantum
    return None


def _unite_presente(citation_normalisee: str, unite: str | None) -> bool:
    """Vrai si le mot de l'unité apparaît dans la citation normalisée."""
    if unite is None:
        return True
    motifs = {
        "ans": r"\bans?\b|\bannées?\b",
        "mois": r"\bmois\b",
        "jours": r"\bjours?\b",
        "francs": r"\bfrancs?\b",
    }
    motif = motifs.get(unite)
    if motif is None:
        return False
    return re.search(motif, citation_normalisee) is not None


def _contient_numero(texte_normalise: str, numero: str) -> bool:
    """Vrai si le numéro d'article apparaît comme mot isolé dans le texte."""
    motif = rf"(?<![\d-]){re.escape(str(numero))}(?![\d-])"
    return re.search(motif, texte_normalise) is not None


def _est_livre_i(article: dict) -> bool:
    """Vrai si l'article appartient au Livre I."""
    valeur = (article.get("livre") or article.get("livre_numero")
              or article.get("livre_id"))
    if valeur is None:
        return False
    return str(valeur).strip().upper() in {"I", "1", "L1", "LI"}


def _ajouter(liste: list[str], message: str) -> None:
    """Ajoute un message sans doublon."""
    if message not in liste:
        liste.append(message)


def verifier(fiche, article: dict, numeros_existants: Iterable[str]) -> dict:
    """Vérifie une fiche et retourne {statut, erreurs}."""
    if hasattr(fiche, "model_dump"):
        fiche = fiche.model_dump()
    texte = normaliser(article.get("texte_complet") or article.get("texte_brut") or "")
    existants = {str(n) for n in numeros_existants}
    rejets: list[str] = []
    avertissements: list[str] = []

    renvois = fiche.get("renvois") or []
    for numero in renvois:
        numero = str(numero)
        if numero not in existants:
            _ajouter(rejets, f"renvoi {numero} : article inexistant")
        elif not _contient_numero(texte, numero):
            _ajouter(rejets, f"renvoi {numero} : absent du texte de l'article")

    infractions = fiche.get("infractions") or []
    libelles: set[str] = set()

    for infraction in infractions:
        libelle = str(infraction.get("libelle") or "").strip()
        libelle_normalise = normaliser(libelle)
        if not libelle_normalise:
            _ajouter(rejets, "infraction sans libellé")
        elif libelle_normalise in libelles:
            _ajouter(avertissements, f"infraction en double : {libelle!r}")
        else:
            libelles.add(libelle_normalise)

        for element in infraction.get("elements_constitutifs") or []:
            citation = str(element.get("citation") or "")
            if not citation.strip():
                _ajouter(rejets, f"{libelle} : citation d'élément vide")
            elif normaliser(citation) not in texte:
                _ajouter(rejets, f"{libelle} : citation d'élément absente du texte")

        peines = infraction.get("peines") or []
        for peine in peines:
            citation = str(peine.get("citation") or "")
            citation_norm = normaliser(citation)
            if not citation.strip():
                _ajouter(rejets, f"{libelle} : citation de peine vide")
            elif citation_norm not in texte:
                _ajouter(rejets, f"{libelle} : citation de peine absente du texte")

            condition = peine.get("condition")
            if condition is not None:
                condition_texte = str(condition)
                if not condition_texte.strip():
                    _ajouter(rejets, f"{libelle} : condition de peine vide")
                elif normaliser(condition_texte) not in texte:
                    _ajouter(rejets,
                             f"{libelle} : condition de peine absente du texte")

            nombres = _nombres(citation)
            for champ, champ_unite in (("quantum_min", "unite_min"),
                                       ("quantum_max", "unite_max")):
                quantum = _nombre(peine.get(champ))
                if quantum is None:
                    continue
                if not any(abs(n - quantum) < 1e-9 for n in nombres):
                    _ajouter(rejets,
                             f"{libelle} : {champ}={peine.get(champ)} absent de la citation")
                unite = peine.get(champ_unite)
                if unite is not None and not _unite_presente(citation_norm, unite):
                    _ajouter(rejets,
                             f"{libelle} : {champ}={peine.get(champ)} avec unité "
                             f"{unite!r} absente de la citation")

            if "fcfa" in citation_norm and "fcfa" not in texte:
                _ajouter(rejets,
                         f"{libelle} : unité FCFA absente du texte (le texte parle de francs)")
            if any(peine.get(champ) == "francs"
                   for champ in ("unite_min", "unite_max")) and "fcfa" in citation_norm:
                _ajouter(rejets, f"{libelle} : unité convertie en FCFA")

            if peine.get("type") == "alternative" and peine.get("nature") not in {
                    "travail_interet_general", "autre"}:
                _ajouter(avertissements,
                         f"{libelle} : type 'alternative' réservé au travail d'intérêt "
                         f"général ou à la sanction-réparation (nature {peine.get('nature')!r})")

            quantum_min = _nombre(peine.get("quantum_min"))
            quantum_max = _nombre(peine.get("quantum_max"))
            if quantum_min is not None and quantum_max is not None:
                unite_min = peine.get("unite_min")
                unite_max = peine.get("unite_max")
                if unite_min in UNITES_DUREE and unite_max in UNITES_DUREE:
                    minimum = _en_jours(quantum_min, unite_min)
                    maximum = _en_jours(quantum_max, unite_max)
                else:
                    minimum = quantum_min
                    maximum = quantum_max
                if minimum > maximum:
                    _ajouter(avertissements,
                             f"{libelle} : fourchette inversée ({quantum_min} > {quantum_max})")

        if infraction.get("peines_au_choix"):
            expression = "l'une de ces deux peines"
            if expression not in texte:
                _ajouter(rejets,
                         f"{libelle} : peines_au_choix vrai mais l'expression "
                         f"« {expression} » est absente du texte")

        peines_renvoi = infraction.get("peines_renvoi") or []
        for numero in peines_renvoi:
            numero = str(numero)
            if numero not in existants:
                _ajouter(rejets, f"peines_renvoi {numero} : article inexistant")
            elif not _contient_numero(texte, numero):
                _ajouter(rejets,
                         f"peines_renvoi {numero} : absent du texte de l'article")

        if not peines and not peines_renvoi:
            _ajouter(avertissements,
                     f"{libelle} : aucune peine ni renvoi de peine")

    if not infractions:
        if not _est_livre_i(article):
            mots = [mot for mot in MOTS_INFRACTION if mot in texte]
            if mots:
                _ajouter(avertissements,
                         "fiche vide alors que le texte mentionne "
                         + ", ".join(mots))

    rejets = list(dict.fromkeys(rejets))
    avertissements = list(dict.fromkeys(avertissements))
    if rejets:
        statut = REJETE
    elif avertissements:
        statut = A_REVOIR
    else:
        statut = AUTO_OK
    return {"statut": statut, "erreurs": rejets + avertissements}


__all__ = ["AUTO_OK", "A_REVOIR", "REJETE", "normaliser", "verifier"]
