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
MOTIFS_CONDITIONS_A_REVOIR = ("puni comme", "même peine", "mêmes peines")
MOTIF_CONDITION_RENVOI = re.compile(r"\barticles?\s+\d", re.IGNORECASE)
MOTIF_RENVOI_PEINE = re.compile(
    r"\bpeines?\b[^.]{0,80}\b(?:de|des|à|aux|auxdits)\s+"
    r"(?:l'article|articles?)\b"
    r"|\bpeines?\b[^.]{0,80}\b(?:est|sont)\s+celles?\b[^.]{0,80}\b"
    r"(?:de|à)\s+l'article\b",
    re.IGNORECASE,
)
MOTIF_INFRACTION_BASE = re.compile(
    r"\binfractions?\b.{0,120}\barticles?\s+\d",
    re.IGNORECASE,
)
MOTIF_RESULTAT_DIFFERENT = re.compile(
    r"\b(?:provoque(?:nt)?|provoqué(?:e|es|s)?|"
    r"cause(?:nt)?|causé(?:e|es|s)?|"
    r"entra[iî]ne(?:nt)?|entra[iî]né(?:e|es|s)?|"
    r"occasionne(?:nt)?|occasionné(?:e|es|s)?|"
    r"abouti(?:t|ssent)|résulte(?:nt)?|suivi(?:e|es|s)?)\b",
    re.IGNORECASE,
)
MESSAGE_INFRACTION_DISTINCTE = (
    "condition renvoyant à d'autres articles : possible infraction distincte"
)
MESSAGE_RENVOI_PEINE = (
    "condition renvoyant aux peines d'autres articles : possible renvoi de peine"
)
MESSAGE_CONDITION_INCOMPLETE = (
    "condition de peine possiblement incomplète : dépendance à une autre "
    "condition non reprise"
)
MOTIF_CONDITION_SUBORDONNEE = re.compile(r"^en cas d", re.IGNORECASE)
MOTIF_CONDITION_CONTEXTE = re.compile(
    r"\b(?:si|au cas où|lorsque|dans le cas où)\b",
    re.IGNORECASE,
)


def normaliser(texte: str) -> str:
    """Normalise espaces, apostrophes et tirets avant comparaison."""
    texte = (texte or "").replace("\u00a0", " ").replace("\u202f", " ")
    texte = texte.replace("’", "'").replace("‘", "'")
    texte = texte.replace("“", '"').replace("”", '"')
    texte = texte.replace("–", "-").replace("—", "-").replace("‑", "-")
    texte = re.sub(r"\s+", " ", texte)
    return texte.strip().lower()


def _nombres(texte: str) -> list[float]:
    """Extrait les nombres, en traitant espaces et points de milliers."""
    texte = (texte or "").replace("\u00a0", " ").replace("\u202f", " ")
    texte = re.sub(r"(?<=\d)\s+(?=\d)", "", texte)
    texte = re.sub(r"(?<=\d)\.(?=\d{3}(?!\d))", "", texte)
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


def _numero_article(valeur: str) -> str:
    """Extrait le numéro d'article au début d'un renvoi (ex. '164 (2)' -> '164')."""
    correspondance = re.match(r"\s*(\d+(?:-\d+)?)", str(valeur))
    return correspondance.group(1) if correspondance else ""


def _contient_renvoi(texte_normalise: str, renvoi_normalise: str,
                     numero_article: str) -> bool:
    """Vrai si le renvoi complet, ou son numéro seul, figure dans le texte."""
    if renvoi_normalise == numero_article:
        return _contient_numero(texte_normalise, numero_article)
    return renvoi_normalise in texte_normalise


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


def _est_reference_infraction_de_base(condition_normalisee: str) -> bool:
    """Vrai si la condition cite une infraction de base sans résultat distinct."""
    return (
        MOTIF_INFRACTION_BASE.search(condition_normalisee) is not None
        and MOTIF_RESULTAT_DIFFERENT.search(condition_normalisee) is None
    )


def _controler_condition(condition: str, avertissements: list[str]) -> None:
    """Classe une condition et ajoute les avertissements adaptés."""
    condition_normalisee = normaliser(str(condition))
    if any(motif in condition_normalisee for motif in MOTIFS_CONDITIONS_A_REVOIR):
        _ajouter(avertissements, f"condition à vérifier : {str(condition)!r}")

    renvoi_peine = MOTIF_RENVOI_PEINE.search(condition_normalisee) is not None
    if renvoi_peine:
        _ajouter(avertissements, MESSAGE_RENVOI_PEINE)

    if (
        not renvoi_peine
        and MOTIF_CONDITION_RENVOI.search(condition_normalisee) is not None
        and not _est_reference_infraction_de_base(condition_normalisee)
    ):
        _ajouter(avertissements, MESSAGE_INFRACTION_DISTINCTE)


def _phrases(texte_normalise: str) -> list[str]:
    """Découpe un texte normalisé en phrases simples."""
    return [
        phrase.strip()
        for phrase in re.split(r"(?<=[.!?])\s+", texte_normalise)
        if phrase.strip()
    ]


def _condition_dependante_incomplete(
    condition: str,
    autres_conditions: list[str],
    texte_normalise: str,
) -> bool:
    """Vrai si une sous-condition ne reprend pas une condition précédente."""
    condition_normalisee = normaliser(str(condition))
    if not MOTIF_CONDITION_SUBORDONNEE.search(condition_normalisee):
        return False

    phrases = _phrases(texte_normalise)
    index = next(
        (i for i, phrase in enumerate(phrases) if condition_normalisee in phrase),
        None,
    )
    if index is None:
        return False

    phrase = phrases[index]
    for autre in autres_conditions:
        autre_normalisee = normaliser(str(autre))
        if not autre_normalisee or autre_normalisee == condition_normalisee:
            continue

        if autre_normalisee in phrase:
            position_autre = phrase.find(autre_normalisee)
            position_condition = phrase.find(condition_normalisee)
            if position_autre >= position_condition:
                continue
            between = phrase[
                position_autre + len(autre_normalisee):position_condition
            ]
            connecteur = re.search(r"\b(et|ou)\b[^a-z0-9]*$", between)
            if connecteur and connecteur.group(1) == "et":
                return True
        elif index > 0 and autre_normalisee in phrases[index - 1]:
            if MOTIF_CONDITION_CONTEXTE.search(phrases[index - 1]):
                return True

    return False


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

    for condition in fiche.get("conditions") or []:
        _controler_condition(condition, avertissements)

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

        for condition in infraction.get("conditions") or []:
            _controler_condition(condition, avertissements)

        choix_utilises: dict[int, int] = {}
        for element in infraction.get("elements_constitutifs") or []:
            citation = str(element.get("citation") or "")
            if not citation.strip():
                _ajouter(rejets, f"{libelle} : citation d'élément vide")
            elif normaliser(citation) not in texte:
                _ajouter(rejets, f"{libelle} : citation d'élément absente du texte")
            choix = element.get("choix")
            if choix is not None:
                choix_utilises[int(choix)] = choix_utilises.get(int(choix), 0) + 1

        for choix, nombre in choix_utilises.items():
            if nombre == 1:
                _ajouter(
                    avertissements,
                    f"{libelle} : choix {choix} utilisé par un seul élément",
                )

        peines = infraction.get("peines") or []
        conditions_peines = [
            str(peine.get("condition"))
            for peine in peines
            if peine.get("condition")
        ]
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
                condition_normalisee = normaliser(condition_texte)
                if not condition_texte.strip():
                    _ajouter(rejets, f"{libelle} : condition de peine vide")
                elif condition_normalisee not in texte:
                    _ajouter(rejets,
                             f"{libelle} : condition de peine absente du texte")
                if condition_texte.strip():
                    _controler_condition(condition_texte, avertissements)
                    if _condition_dependante_incomplete(
                        condition_texte, conditions_peines, texte
                    ):
                        _ajouter(
                            avertissements,
                            f"{libelle} : {MESSAGE_CONDITION_INCOMPLETE}",
                        )

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
        for renvoi in peines_renvoi:
            renvoi_normalise = normaliser(str(renvoi))
            numero_article = _numero_article(renvoi_normalise)
            if not numero_article or numero_article not in existants:
                _ajouter(rejets,
                         f"peines_renvoi {renvoi} : article inexistant")
            elif not _contient_renvoi(texte, renvoi_normalise, numero_article):
                _ajouter(rejets,
                         f"peines_renvoi {renvoi} : absent du texte de l'article")

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
