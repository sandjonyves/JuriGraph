"""Schéma d'une fiche d'extraction Infraction / Peine."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ModeleStrict(BaseModel):
    """Interdit les champs non prévus par le schéma."""

    model_config = ConfigDict(extra="forbid")


class Element(ModeleStrict):
    """Élément constitutif d'une infraction."""

    type: Literal["legal", "materiel", "moral"]
    texte: str
    citation: str


class Peine(ModeleStrict):
    """Peine principale, alternative ou accessoire."""

    type: Literal["principale", "alternative", "accessoire"]
    nature: Literal[
        "emprisonnement", "amende", "mort", "travail_interet_general", "autre"
    ]
    quantum_min: float | None = None
    quantum_max: float | None = None
    unite: Literal["ans", "mois", "jours", "francs"] | None = None
    perpetuite: bool = False
    condition: str | None = None
    citation: str


class Infraction(ModeleStrict):
    """Infraction définie par un article."""

    libelle: str
    elements_constitutifs: list[Element] = Field(default_factory=list)
    peines: list[Peine] = Field(default_factory=list)
    peines_renvoi: list[str] = Field(default_factory=list)


class Fiche(ModeleStrict):
    """Fiche complète produite pour un article."""

    article: str
    infractions: list[Infraction] = Field(default_factory=list)
    conditions: list[str] = Field(default_factory=list)
    renvois: list[str] = Field(default_factory=list)


__all__ = ["Element", "Fiche", "Infraction", "Peine"]
