"""Schéma Pydantic de la fiche d'extraction juridique V5."""
from __future__ import annotations

import re
from collections.abc import Iterator, Mapping
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationInfo,
    field_validator,
    model_validator,
)

SchemaVersion = Literal["5.0"]
TypeArticle = Literal[
    "definit_infraction",
    "regle_generale",
    "regime_peines",
    "mixte",
    "sans_objet",
    "indetermine",
]
Statut = Literal["explicite", "a_verifier", "indetermine"]
StatutRenvoi = Literal[
    "resolue", "textuelle", "non_resolue", "externe", "indetermine"
]
PorteeCondition = Literal["commune", "propre", "generale", "interpretative"]
CategorieCondition = Literal[
    "fait", "qualite", "procedure", "circonstance", "resultat", "renvoi", "autre"
]
NaturePeine = Literal[
    "emprisonnement",
    "amende",
    "mort",
    "travail_interet_general",
    "sanction_reparation",
    "confiscation",
    "retrait_permis",
    "suspension_permis",
    "interdiction",
    "decheance",
    "publication",
    "fermeture_etablissement",
    "dissolution",
    "placement_surveillance",
    "reparation",
    "autre",
    "indeterminee",
]
CategoriePeine = Literal[
    "principale", "accessoire", "complementaire", "alternative", "indeterminee"
]
ModaliteApplication = Literal["obligatoire", "facultative", "indeterminee"]
OriginePeine = Literal["texte", "renvoi", "regle_generale", "indetermine"]
ModeQuantum = Literal[
    "fixe",
    "fourchette",
    "minimum",
    "maximum",
    "perpetuite",
    "formule",
    "non_determine",
]
TypeFormule = Literal[
    "multiple_profit",
    "pourcentage",
    "reference_article",
    "reference_peine",
    "plafond",
    "plancher",
    "autre",
]
TypeInformation = Literal[
    "infraction",
    "libelle",
    "element",
    "condition",
    "quantum",
    "nature_peine",
    "categorie_peine",
    "formule",
    "renvoi",
    "regle",
    "effet",
    "disposition",
    "categorie_infraction",
    "autre",
]
TypeRenvoi = Literal[
    "article",
    "peine",
    "infraction",
    "regle",
    "condition",
    "procedure",
    "externe",
    "autre",
]
PorteeRenvoi = Literal[
    "peine",
    "quantum",
    "duree",
    "condition",
    "application",
    "doublement",
    "assimilation",
    "procedure",
    "autre",
]
TypeCible = Literal[
    "article",
    "infraction",
    "peine",
    "regle",
    "condition",
    "categorie",
    "libelle",
    "externe",
    "indetermine",
]
TypeRegle = Literal[
    "doublement",
    "assimilation",
    "majoration",
    "conversion",
    "application_peine",
    "peine_accessoire",
    "plafonnement",
    "autre",
]
TypeEffet = Literal[
    "multiplication",
    "assimilation",
    "fixation_peine",
    "ajout_peine",
    "substitution",
    "conversion",
    "plafonnement",
    "plancher",
    "formule",
    "autre",
]
TypeDisposition = Literal[
    "principe", "catalogue_peines", "classification", "definition", "autre"
]
PublicDisposition = Literal[
    "personne_physique", "personne_morale", "toutes", "indetermine"
]
ObjetIncertitude = Literal[
    "condition",
    "peine",
    "quantum",
    "formule",
    "renvoi",
    "regle",
    "libelle",
    "type_article",
    "autre",
]
MotifIncertitude = Literal[
    "texte_ambigu",
    "renvoi_non_resolu",
    "formule_non_chiffree",
    "information_absente",
    "desaccord_interpretation",
    "autre",
]
NiveauIncertitude = Literal["a_verifier", "non_determine"]
RelationGroupePeines = Literal[
    "alternative", "cumulative", "cumul_ou_alternative", "echelle_conditionnelle"
]

PREFIXES_ID = {
    "infraction": "INF",
    "element": "ELT",
    "peine": "PEI",
    "condition": "COND",
    "groupe_conditions": "GC",
    "groupe_peines": "GP",
    "regle": "REG",
    "effet": "EFF",
    "renvoi": "REN",
    "disposition": "DIS",
    "incertitude": "INC",
}

TYPES_CIBLES_INTERNES = {
    "infraction": "infraction",
    "peine": "peine",
    "regle": "regle",
    "condition": "condition",
}

_TYPES_ARTICLE_SANS_INFRACTION = {"regle_generale", "regime_peines"}

_ESPACES = re.compile(r"\s+")


def normaliser_citation(texte: str) -> str:
    """Normalise la typographie et les espaces avant comparaison d'une citation."""
    texte = texte.replace("\u00a0", " ").replace("\u202f", " ")
    texte = (
        texte.replace("’", "'")
        .replace("‘", "'")
        .replace("“", '"')
        .replace("”", '"')
        .replace("–", "-")
        .replace("—", "-")
    )
    return _ESPACES.sub(" ", texte).strip()


def _texte_non_vide(valeur: str, champ: str) -> str:
    """Vérifie qu'une chaîne obligatoire n'est pas vide."""
    if not valeur or not valeur.strip():
        raise ValueError(f"{champ} ne peut pas être vide")
    return valeur


class ModeleStrictV5(BaseModel):
    """Interdit les champs non prévus et les flottants non finis."""

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        allow_inf_nan=False,
    )


class Source(ModeleStrictV5):
    """Citation exacte et provenance d'une information extraite."""

    article: str
    alinea: str | None = None
    citation: str
    type_information: TypeInformation
    offset_debut: int | None = Field(default=None, ge=0)
    offset_fin: int | None = Field(default=None, ge=0)
    commentaire: str | None = None

    @field_validator("article", "citation")
    @classmethod
    def _champs_non_vides(cls, valeur: str, info: Any) -> str:
        return _texte_non_vide(valeur, info.field_name or "champ")

    @field_validator("alinea")
    @classmethod
    def _alinea_non_vide(cls, valeur: str | None) -> str | None:
        if valeur is not None:
            _texte_non_vide(valeur, "alinea")
        return valeur

    @model_validator(mode="after")
    def _offsets_coherents(self) -> Source:
        if (
            self.offset_debut is not None
            and self.offset_fin is not None
            and self.offset_fin < self.offset_debut
        ):
            raise ValueError(
                "offset_fin doit être supérieur ou égal à offset_debut"
            )
        return self


class Mesure(ModeleStrictV5):
    """Valeur numérique d'une durée ou d'un montant."""

    type: Literal["duree", "montant"]
    valeur: float = Field(ge=0)
    unite: Literal["jours", "mois", "ans", "francs"]
    unite_source: str | None = None

    @model_validator(mode="after")
    def _unite_coherente(self) -> Mesure:
        if self.type == "duree" and self.unite == "francs":
            raise ValueError("une durée ne peut pas utiliser l'unité francs")
        if self.type == "montant" and self.unite != "francs":
            raise ValueError("un montant doit utiliser l'unité francs")
        return self


class FormulePeine(ModeleStrictV5):
    """Formule de calcul d'une peine, sans montant inventé."""

    type: TypeFormule
    description: str
    facteur: float | None = Field(default=None, gt=0)
    base: str | None = None
    plancher: str | None = None
    reference_ids: list[str] = Field(default_factory=list)
    statut: Statut

    @field_validator("description")
    @classmethod
    def _description_non_vide(cls, valeur: str) -> str:
        return _texte_non_vide(valeur, "description")

    @field_validator("reference_ids")
    @classmethod
    def _references_uniques(cls, valeurs: list[str]) -> list[str]:
        _verifier_liste_unique(valeurs, "reference_ids")
        return valeurs


class QuantumPeine(ModeleStrictV5):
    """Quantum d'une peine : fixe, fourchette, maximum, perpétuité ou formule."""

    mode: ModeQuantum
    valeur: Mesure | None = None
    minimum: Mesure | None = None
    maximum: Mesure | None = None
    formule: FormulePeine | None = None

    @model_validator(mode="after")
    def _forme_coherente(self) -> QuantumPeine:
        if self.mode == "fixe":
            if self.valeur is None:
                raise ValueError("un quantum fixe exige une valeur")
            if any(
                champ is not None
                for champ in (self.minimum, self.maximum, self.formule)
            ):
                raise ValueError(
                    "un quantum fixe n'accepte ni minimum, ni maximum, ni formule"
                )
        elif self.mode == "fourchette":
            if self.minimum is None or self.maximum is None:
                raise ValueError(
                    "une fourchette exige un minimum et un maximum"
                )
            if self.valeur is not None or self.formule is not None:
                raise ValueError(
                    "une fourchette n'accepte ni valeur fixe ni formule"
                )
            _verifier_ordre_mesures(self.minimum, self.maximum)
        elif self.mode == "minimum":
            if self.minimum is None:
                raise ValueError("un quantum minimum exige une valeur minimale")
            if any(
                champ is not None for champ in (self.valeur, self.maximum, self.formule)
            ):
                raise ValueError(
                    "un quantum minimum n'accepte ni valeur, ni maximum, ni formule"
                )
        elif self.mode == "maximum":
            if self.maximum is None:
                raise ValueError("un quantum maximum exige une valeur maximale")
            if any(
                champ is not None for champ in (self.valeur, self.minimum, self.formule)
            ):
                raise ValueError(
                    "un quantum maximum n'accepte ni valeur, ni minimum, ni formule"
                )
        elif self.mode == "perpetuite":
            if any(
                champ is not None
                for champ in (self.valeur, self.minimum, self.maximum, self.formule)
            ):
                raise ValueError("une perpétuité n'accepte aucun quantum numérique")
        elif self.mode == "formule":
            if self.formule is None:
                raise ValueError("un quantum formule exige une formule")
            if any(
                champ is not None
                for champ in (self.valeur, self.minimum, self.maximum)
            ):
                raise ValueError(
                    "un quantum formule n'accepte ni valeur, ni minimum, ni maximum"
                )
        elif self.mode == "non_determine":
            if any(
                champ is not None
                for champ in (self.valeur, self.minimum, self.maximum, self.formule)
            ):
                raise ValueError(
                    "un quantum non déterminé n'accepte aucun quantum numérique"
                )
        return self


class Peine(ModeleStrictV5):
    """Peine principale, accessoire, complémentaire ou alternative."""

    id: str
    categorie: CategoriePeine
    nature: NaturePeine
    sous_type: str | None = None
    objet: str | None = None
    modalites: list[str] = Field(default_factory=list)
    modalite_application: ModaliteApplication
    quantum: QuantumPeine | None = None
    origine: OriginePeine
    renvoi_ids: list[str] = Field(default_factory=list)
    condition_groupe_ids: list[str] = Field(default_factory=list)
    sources: list[Source] = Field(min_length=1)
    statut: Statut
    commentaire: str | None = None

    @field_validator("id", "sous_type", "objet", "commentaire")
    @classmethod
    def _chaines_utiles(
        cls, valeur: str | None, info: Any
    ) -> str | None:
        if valeur is not None:
            _texte_non_vide(valeur, info.field_name or "champ")
        return valeur

    @field_validator("modalites", "renvoi_ids", "condition_groupe_ids")
    @classmethod
    def _listes_uniques(cls, valeurs: list[str], info: Any) -> list[str]:
        for valeur in valeurs:
            _texte_non_vide(valeur, info.field_name or "liste")
        _verifier_liste_unique(valeurs, info.field_name or "liste")
        return valeurs

    @model_validator(mode="after")
    def _coherence(self) -> Peine:
        if self.origine == "renvoi" and not self.renvoi_ids:
            raise ValueError("une peine par renvoi exige au moins un renvoi_id")
        if self.nature == "mort" and self.quantum is not None:
            raise ValueError("une peine de mort ne porte pas de quantum")
        if self.quantum is not None and self.quantum.mode != "formule":
            mesures = [
                mesure
                for mesure in (
                    self.quantum.valeur,
                    self.quantum.minimum,
                    self.quantum.maximum,
                )
                if mesure is not None
            ]
            if self.nature == "amende" and any(
                mesure.type != "montant" for mesure in mesures
            ):
                raise ValueError("une amende doit avoir un quantum en francs")
            if self.nature in {"emprisonnement", "travail_interet_general"} and any(
                mesure.type != "duree" for mesure in mesures
            ):
                raise ValueError(
                    "une peine d'emprisonnement ou de travail d'intérêt général "
                    "doit avoir un quantum en durée"
                )
        if self.nature in {
            "confiscation",
            "retrait_permis",
            "suspension_permis",
            "decheance",
        } and not self.objet:
            raise ValueError(
                f"une peine {self.nature} doit préciser son objet"
            )
        if self.nature == "autre" and not self.sous_type:
            raise ValueError(
                "une peine de nature autre doit préciser son sous_type"
            )
        return self


class ElementConstitutif(ModeleStrictV5):
    """Élément légal, matériel ou moral d'une infraction."""

    id: str
    type: Literal["legal", "materiel", "moral"]
    texte: str
    groupe_alternatif: str | None = None
    sources: list[Source] = Field(min_length=1)
    statut: Statut

    @field_validator("id", "texte", "groupe_alternatif")
    @classmethod
    def _chaines_non_vides(
        cls, valeur: str | None, info: Any
    ) -> str | None:
        if valeur is not None:
            _texte_non_vide(valeur, info.field_name or "champ")
        return valeur


class Infraction(ModeleStrictV5):
    """Fait punissable défini par le texte ou incorporé par un renvoi explicite."""

    id: str
    libelle: str
    libelle_source: Literal["texte", "reformulation", "indetermine"]
    origine: Literal["texte", "renvoi", "indetermine"]
    elements_constitutifs: list[ElementConstitutif] = Field(min_length=1)
    peines: list[Peine] = Field(default_factory=list)
    renvoi_ids: list[str] = Field(default_factory=list)
    sources: list[Source] = Field(min_length=1)
    statut: Statut
    commentaire: str | None = None

    @field_validator("id", "libelle", "commentaire")
    @classmethod
    def _chaines_non_vides(
        cls, valeur: str | None, info: Any
    ) -> str | None:
        if valeur is not None:
            _texte_non_vide(valeur, info.field_name or "champ")
        return valeur

    @field_validator("renvoi_ids")
    @classmethod
    def _renvois_uniques(cls, valeurs: list[str]) -> list[str]:
        for valeur in valeurs:
            _texte_non_vide(valeur, "renvoi_ids")
        _verifier_liste_unique(valeurs, "renvoi_ids")
        return valeurs

    @model_validator(mode="after")
    def _coherence(self) -> Infraction:
        if self.origine == "renvoi" and not self.renvoi_ids:
            raise ValueError(
                "une infraction par renvoi exige au moins un renvoi_id"
            )
        if not self.peines and not self.renvoi_ids:
            raise ValueError(
                "une infraction doit avoir une peine ou un renvoi de peine"
            )
        groupes: dict[str, list[str]] = {}
        for element in self.elements_constitutifs:
            if element.groupe_alternatif is not None:
                groupes.setdefault(element.groupe_alternatif, []).append(element.id)
        for groupe, membres in groupes.items():
            if len(membres) < 2:
                raise ValueError(
                    f"le groupe alternatif {groupe} doit contenir au moins "
                    "deux éléments"
                )
        return self


class Condition(ModeleStrictV5):
    """Condition juridique réutilisable, avec sa provenance."""

    id: str
    libelle: str
    portee: PorteeCondition
    categorie: CategorieCondition
    renvoi_ids: list[str] = Field(default_factory=list)
    sources: list[Source] = Field(min_length=1)
    statut: Statut
    commentaire: str | None = None

    @field_validator("id", "libelle", "commentaire")
    @classmethod
    def _chaines_non_vides(
        cls, valeur: str | None, info: Any
    ) -> str | None:
        if valeur is not None:
            _texte_non_vide(valeur, info.field_name or "champ")
        return valeur

    @field_validator("renvoi_ids")
    @classmethod
    def _renvois_uniques(cls, valeurs: list[str]) -> list[str]:
        for valeur in valeurs:
            _texte_non_vide(valeur, "renvoi_ids")
        _verifier_liste_unique(valeurs, "renvoi_ids")
        return valeurs


class GroupeConditions(ModeleStrictV5):
    """Combinaison ET/OU de conditions et de sous-groupes."""

    id: str
    operateur: Literal["et", "ou"]
    condition_ids: list[str] = Field(default_factory=list)
    sous_groupe_ids: list[str] = Field(default_factory=list)
    commentaire: str | None = None

    @field_validator("id", "commentaire")
    @classmethod
    def _chaines_non_vides(
        cls, valeur: str | None, info: Any
    ) -> str | None:
        if valeur is not None:
            _texte_non_vide(valeur, info.field_name or "champ")
        return valeur

    @field_validator("condition_ids", "sous_groupe_ids")
    @classmethod
    def _listes_uniques(cls, valeurs: list[str], info: Any) -> list[str]:
        for valeur in valeurs:
            _texte_non_vide(valeur, info.field_name or "liste")
        _verifier_liste_unique(valeurs, info.field_name or "liste")
        return valeurs

    @model_validator(mode="after")
    def _membres_coherents(self) -> GroupeConditions:
        total = len(self.condition_ids) + len(self.sous_groupe_ids)
        if total == 0:
            raise ValueError("un groupe de conditions doit avoir au moins un membre")
        if set(self.condition_ids) & set(self.sous_groupe_ids):
            raise ValueError(
                "un même identifiant ne peut être à la fois condition et sous-groupe"
            )
        if self.operateur == "ou" and total < 2:
            raise ValueError("un groupe OU doit avoir au moins deux membres")
        return self


class GroupePeines(ModeleStrictV5):
    """Groupe de peines alternatives, cumulatives ou conditionnelles."""

    id: str
    sujet_type: Literal["infraction", "regle_generale"]
    sujet_id: str
    relation: RelationGroupePeines
    peine_ids: list[str] = Field(min_length=1)
    sources: list[Source] = Field(default_factory=list)
    commentaire: str | None = None

    @field_validator("id", "sujet_id", "commentaire")
    @classmethod
    def _chaines_non_vides(
        cls, valeur: str | None, info: Any
    ) -> str | None:
        if valeur is not None:
            _texte_non_vide(valeur, info.field_name or "champ")
        return valeur

    @field_validator("peine_ids")
    @classmethod
    def _peines_uniques(cls, valeurs: list[str]) -> list[str]:
        for valeur in valeurs:
            _texte_non_vide(valeur, "peine_ids")
        _verifier_liste_unique(valeurs, "peine_ids")
        return valeurs

    @model_validator(mode="after")
    def _choix_coherent(self) -> GroupePeines:
        if len(self.peine_ids) < 2 and not (
            self.commentaire and self.commentaire.strip()
        ):
            raise ValueError(
                "un groupe de peines doit contenir au moins deux peines, "
                "sauf justification explicite dans commentaire"
            )
        return self


class EffetRegle(ModeleStrictV5):
    """Effet juridique produit par une règle générale."""

    id: str
    type: TypeEffet
    description: str
    facteur: float | None = Field(default=None, gt=0)
    formule: FormulePeine | None = None
    portee_effet: str | None = None
    peines_cible_ids: list[str] = Field(default_factory=list)
    peines_ajoutees_ids: list[str] = Field(default_factory=list)
    statut: Statut

    @field_validator("id", "description", "portee_effet")
    @classmethod
    def _chaines_non_vides(
        cls, valeur: str | None, info: Any
    ) -> str | None:
        if valeur is not None:
            _texte_non_vide(valeur, info.field_name or "champ")
        return valeur

    @field_validator("peines_cible_ids", "peines_ajoutees_ids")
    @classmethod
    def _listes_uniques(cls, valeurs: list[str], info: Any) -> list[str]:
        for valeur in valeurs:
            _texte_non_vide(valeur, info.field_name or "liste")
        _verifier_liste_unique(valeurs, info.field_name or "liste")
        return valeurs

    @model_validator(mode="after")
    def _effet_coherent(self) -> EffetRegle:
        if self.type == "multiplication" and self.facteur is None:
            raise ValueError("un effet de multiplication exige un facteur")
        if self.type == "formule" and self.formule is None:
            raise ValueError("un effet de formule exige une formule")
        if set(self.peines_cible_ids) & set(self.peines_ajoutees_ids):
            raise ValueError(
                "une peine ne peut pas être à la fois cible et ajoutée"
            )
        return self


class RegleGenerale(ModeleStrictV5):
    """Règle qui double, fixe, assimile, convertit ou ajoute une peine."""

    id: str
    type: TypeRegle
    libelle: str
    description: str
    condition_groupe_ids: list[str] = Field(default_factory=list)
    renvoi_ids: list[str] = Field(default_factory=list)
    effets: list[EffetRegle] = Field(min_length=1)
    peines: list[Peine] = Field(default_factory=list)
    sources: list[Source] = Field(min_length=1)
    statut: Statut
    commentaire: str | None = None

    @field_validator("id", "libelle", "description", "commentaire")
    @classmethod
    def _chaines_non_vides(
        cls, valeur: str | None, info: Any
    ) -> str | None:
        if valeur is not None:
            _texte_non_vide(valeur, info.field_name or "champ")
        return valeur

    @field_validator("condition_groupe_ids", "renvoi_ids")
    @classmethod
    def _listes_uniques(cls, valeurs: list[str], info: Any) -> list[str]:
        for valeur in valeurs:
            _texte_non_vide(valeur, info.field_name or "liste")
        _verifier_liste_unique(valeurs, info.field_name or "liste")
        return valeurs


class Cible(ModeleStrictV5):
    """Cible d'un renvoi juridique."""

    type: TypeCible
    article: str | None = None
    alinea: str | None = None
    id_interne: str | None = None
    libelle: str | None = None
    categorie: str | None = None
    statut: StatutRenvoi

    @field_validator("article", "alinea", "id_interne", "libelle", "categorie")
    @classmethod
    def _chaines_utiles(
        cls, valeur: str | None, info: Any
    ) -> str | None:
        if valeur is not None:
            _texte_non_vide(valeur, info.field_name or "champ")
        return valeur

    @model_validator(mode="after")
    def _cible_identifiable(self) -> Cible:
        if self.type == "article" and not self.article:
            raise ValueError("une cible de type article exige un numéro d'article")
        if self.type == "libelle" and not self.libelle:
            raise ValueError("une cible de type libelle exige un libellé")
        if self.statut == "textuelle" and not self.libelle:
            raise ValueError("une cible textuelle exige un libellé")
        if self.alinea is not None and not self.article:
            raise ValueError("un alinéa cible exige un article cible")
        if self.type in TYPES_CIBLES_INTERNES and not (
            self.id_interne or self.libelle or self.article
        ):
            raise ValueError(
                "une cible interne exige id_interne, libelle ou article"
            )
        if self.type == "externe" and not (self.libelle or self.article):
            raise ValueError("une cible externe exige un libellé ou un article")
        return self


class Renvoi(ModeleStrictV5):
    """Renvoi juridique typé et localisé."""

    id: str
    type: TypeRenvoi
    portee: PorteeRenvoi
    cibles: list[Cible] = Field(min_length=1)
    sources: list[Source] = Field(min_length=1)
    statut: StatutRenvoi
    commentaire: str | None = None

    @field_validator("id", "commentaire")
    @classmethod
    def _chaines_non_vides(
        cls, valeur: str | None, info: Any
    ) -> str | None:
        if valeur is not None:
            _texte_non_vide(valeur, info.field_name or "champ")
        return valeur


class DispositionRegime(ModeleStrictV5):
    """Principe, catalogue ou classification relatif au régime des peines."""

    id: str
    type: TypeDisposition
    libelle: str
    description: str
    public: PublicDisposition | None = None
    natures_citees: list[NaturePeine] = Field(default_factory=list)
    categories_infraction: list[str] = Field(default_factory=list)
    renvoi_ids: list[str] = Field(default_factory=list)
    sources: list[Source] = Field(min_length=1)
    statut: Statut

    @field_validator("id", "libelle", "description")
    @classmethod
    def _chaines_non_vides(cls, valeur: str, info: Any) -> str:
        return _texte_non_vide(valeur, info.field_name or "champ")

    @field_validator(
        "natures_citees", "categories_infraction", "renvoi_ids"
    )
    @classmethod
    def _listes_uniques(cls, valeurs: list[str], info: Any) -> list[str]:
        for valeur in valeurs:
            _texte_non_vide(valeur, info.field_name or "liste")
        _verifier_liste_unique(valeurs, info.field_name or "liste")
        return valeurs


class Incertitude(ModeleStrictV5):
    """Information non déterminée ou à vérifier."""

    id: str
    objet: ObjetIncertitude
    description: str
    motif: MotifIncertitude
    niveau: NiveauIncertitude
    entites_affectees: list[str] = Field(default_factory=list)
    sources: list[Source] = Field(default_factory=list)
    commentaire: str | None = None

    @field_validator("id", "description", "commentaire")
    @classmethod
    def _chaines_non_vides(
        cls, valeur: str | None, info: Any
    ) -> str | None:
        if valeur is not None:
            _texte_non_vide(valeur, info.field_name or "champ")
        return valeur

    @field_validator("entites_affectees")
    @classmethod
    def _entites_uniques(cls, valeurs: list[str]) -> list[str]:
        for valeur in valeurs:
            _texte_non_vide(valeur, "entites_affectees")
        _verifier_liste_unique(valeurs, "entites_affectees")
        return valeurs


class FicheV5(ModeleStrictV5):
    """Fiche complète produite pour un article avec le schéma V5."""

    schema_version: SchemaVersion
    article: str
    type_article: TypeArticle
    infractions: list[Infraction]
    regles_generales: list[RegleGenerale]
    dispositions_regime: list[DispositionRegime] = Field(default_factory=list)
    conditions: list[Condition] = Field(default_factory=list)
    groupes_conditions: list[GroupeConditions] = Field(default_factory=list)
    groupes_peines: list[GroupePeines] = Field(default_factory=list)
    renvois: list[Renvoi] = Field(default_factory=list)
    incertitudes: list[Incertitude] = Field(default_factory=list)

    @field_validator("article")
    @classmethod
    def _article_non_vide(cls, valeur: str) -> str:
        return _texte_non_vide(valeur, "article")

    @model_validator(mode="after")
    def _valider_ensemble(self, info: ValidationInfo) -> FicheV5:
        erreurs: list[str] = []
        inventaire = _inventaire_ids(self)
        _verifier_ids(self, inventaire, erreurs)
        registre = {identifiant: type_objet for identifiant, type_objet, _ in inventaire}

        if (
            self.type_article in _TYPES_ARTICLE_SANS_INFRACTION
            and self.infractions
        ):
            erreurs.append(
                "INFRACTION_SUR_ARTICLE_REGIME: un article de règle ou de "
                "régime ne peut pas contenir d'infraction"
            )

        _verifier_references(self, registre, erreurs)
        _verifier_sources(self, erreurs)
        _verifier_groupes_conditions(self, registre, erreurs)
        _verifier_groupes_peines(self, registre, erreurs)
        _verifier_conditions(self, registre, erreurs)
        _verifier_citations(self, info, erreurs)

        if erreurs:
            raise ValueError(
                "Fiche V5 invalide :\n- " + "\n- ".join(erreurs)
            )
        return self


def _verifier_liste_unique(valeurs: list[str], champ: str) -> None:
    """Rejette les doublons d'une liste d'identifiants ou de valeurs."""
    if len(set(valeurs)) != len(valeurs):
        raise ValueError(f"{champ} contient des doublons")


def _verifier_ordre_mesures(minimum: Mesure, maximum: Mesure) -> None:
    """Rejette une fourchette inversée lorsque les unités sont identiques."""
    if (
        minimum.type == maximum.type
        and minimum.unite == maximum.unite
        and minimum.valeur > maximum.valeur
    ):
        raise ValueError("le minimum d'une fourchette dépasse son maximum")


def _inventaire_ids(
    fiche: FicheV5,
) -> list[tuple[str, str, str]]:
    """Retourne les identifiants de la fiche avec leur type et leur préfixe."""
    inventaire: list[tuple[str, str, str]] = []

    for infraction in fiche.infractions:
        inventaire.append((infraction.id, "infraction", "INF"))
        for element in infraction.elements_constitutifs:
            inventaire.append((element.id, "element", "ELT"))
        for peine in infraction.peines:
            inventaire.append((peine.id, "peine", "PEI"))
    for regle in fiche.regles_generales:
        inventaire.append((regle.id, "regle", "REG"))
        for effet in regle.effets:
            inventaire.append((effet.id, "effet", "EFF"))
        for peine in regle.peines:
            inventaire.append((peine.id, "peine", "PEI"))
    for condition in fiche.conditions:
        inventaire.append((condition.id, "condition", "COND"))
    for groupe in fiche.groupes_conditions:
        inventaire.append((groupe.id, "groupe_conditions", "GC"))
    for groupe in fiche.groupes_peines:
        inventaire.append((groupe.id, "groupe_peines", "GP"))
    for renvoi in fiche.renvois:
        inventaire.append((renvoi.id, "renvoi", "REN"))
    for disposition in fiche.dispositions_regime:
        inventaire.append((disposition.id, "disposition", "DIS"))
    for incertitude in fiche.incertitudes:
        inventaire.append((incertitude.id, "incertitude", "INC"))
    return inventaire


def _verifier_ids(
    fiche: FicheV5,
    inventaire: list[tuple[str, str, str]],
    erreurs: list[str],
) -> None:
    """Vérifie l'unicité, la forme et l'article de chaque identifiant."""
    vus: set[str] = set()
    for identifiant, type_objet, prefixe in inventaire:
        if identifiant in vus:
            erreurs.append(f"ID_DUPLIQUE: {identifiant}")
        vus.add(identifiant)
        prefixe_attendu = f"{prefixe}-{fiche.article}-"
        if not identifiant.startswith(prefixe_attendu):
            erreurs.append(
                f"ID_INVALIDE: {identifiant} devrait commencer par "
                f"{prefixe_attendu} pour un objet {type_objet}"
            )
        elif not identifiant[len(prefixe_attendu):]:
            erreurs.append(f"ID_INVALIDE: suffixe manquant dans {identifiant}")
        if any(caractere.isspace() for caractere in identifiant):
            erreurs.append(f"ID_INVALIDE: espace dans {identifiant}")


def _verifier_references(
    fiche: FicheV5,
    registre: dict[str, str],
    erreurs: list[str],
) -> None:
    """Vérifie que toutes les références internes résolvent vers le bon type."""
    for infraction in fiche.infractions:
        _resoudre(
            infraction.renvoi_ids, "renvoi", registre, erreurs,
            f"Infraction {infraction.id}.renvoi_ids",
        )
        for peine in infraction.peines:
            _verifier_references_peine(peine, registre, erreurs)
    for regle in fiche.regles_generales:
        _resoudre(
            regle.condition_groupe_ids, "groupe_conditions", registre, erreurs,
            f"RegleGenerale {regle.id}.condition_groupe_ids",
        )
        _resoudre(
            regle.renvoi_ids, "renvoi", registre, erreurs,
            f"RegleGenerale {regle.id}.renvoi_ids",
        )
        _verifier_effets(regle, registre, erreurs)
        for peine in regle.peines:
            _verifier_references_peine(peine, registre, erreurs)
    for condition in fiche.conditions:
        _resoudre(
            condition.renvoi_ids, "renvoi", registre, erreurs,
            f"Condition {condition.id}.renvoi_ids",
        )
    for groupe in fiche.groupes_conditions:
        _resoudre(
            groupe.condition_ids, "condition", registre, erreurs,
            f"GroupeConditions {groupe.id}.condition_ids",
        )
        _resoudre(
            groupe.sous_groupe_ids, "groupe_conditions", registre, erreurs,
            f"GroupeConditions {groupe.id}.sous_groupe_ids",
        )
    for groupe in fiche.groupes_peines:
        _resoudre(
            groupe.peine_ids, "peine", registre, erreurs,
            f"GroupePeines {groupe.id}.peine_ids",
        )
        type_sujet = (
            "infraction"
            if groupe.sujet_type == "infraction"
            else "regle"
        )
        _resoudre(
            [groupe.sujet_id], type_sujet, registre, erreurs,
            f"GroupePeines {groupe.id}.sujet_id",
        )
    for renvoi in fiche.renvois:
        for cible in renvoi.cibles:
            if cible.id_interne is None:
                continue
            type_attendu = TYPES_CIBLES_INTERNES.get(cible.type)
            if cible.id_interne not in registre:
                erreurs.append(
                    f"CIBLE_INTERNE_INCONNUE: {cible.id_interne} "
                    f"dans Renvoi {renvoi.id}"
                )
            elif (
                type_attendu is not None
                and registre[cible.id_interne] != type_attendu
            ):
                erreurs.append(
                    f"CIBLE_INTERNE_INCOMPATIBLE: {cible.id_interne} "
                    f"n'est pas un objet {type_attendu}"
                )
    for disposition in fiche.dispositions_regime:
        _resoudre(
            disposition.renvoi_ids, "renvoi", registre, erreurs,
            f"DispositionRegime {disposition.id}.renvoi_ids",
        )
    for incertitude in fiche.incertitudes:
        for entite in incertitude.entites_affectees:
            if entite not in registre:
                erreurs.append(
                    f"REF_INCONNUE: entite {entite} dans Incertitude "
                    f"{incertitude.id}"
                )


def _verifier_references_peine(
    peine: Peine,
    registre: dict[str, str],
    erreurs: list[str],
) -> None:
    """Vérifie les références portées par une peine."""
    _resoudre(
        peine.renvoi_ids, "renvoi", registre, erreurs,
        f"Peine {peine.id}.renvoi_ids",
    )
    _resoudre(
        peine.condition_groupe_ids, "groupe_conditions", registre, erreurs,
        f"Peine {peine.id}.condition_groupe_ids",
    )
    if peine.quantum is not None:
        formule = peine.quantum.formule
        if formule is not None:
            _resoudre(
                formule.reference_ids, "renvoi", registre, erreurs,
                f"FormulePeine de {peine.id}.reference_ids",
            )


def _verifier_effets(
    regle: RegleGenerale,
    registre: dict[str, str],
    erreurs: list[str],
) -> None:
    """Vérifie les cibles et ajouts de peines des effets d'une règle."""
    for effet in regle.effets:
        _resoudre(
            effet.peines_cible_ids, "peine", registre, erreurs,
            f"EffetRegle {effet.id}.peines_cible_ids",
        )
        _resoudre(
            effet.peines_ajoutees_ids, "peine", registre, erreurs,
            f"EffetRegle {effet.id}.peines_ajoutees_ids",
        )
        if effet.formule is not None:
            _resoudre(
                effet.formule.reference_ids, "renvoi", registre, erreurs,
                f"FormulePeine de {effet.id}.reference_ids",
            )


def _resoudre(
    identifiants: list[str],
    type_attendu: str,
    registre: dict[str, str],
    erreurs: list[str],
    champ: str,
) -> None:
    """Vérifie qu'une liste d'identifiants existe avec le type attendu."""
    for identifiant in identifiants:
        if identifiant not in registre:
            erreurs.append(f"REF_INCONNUE: {identifiant} dans {champ}")
        elif registre[identifiant] != type_attendu:
            erreurs.append(
                f"REF_INCOMPATIBLE: {identifiant} dans {champ} "
                f"devrait être de type {type_attendu}"
            )


def _sources_fiche(
    fiche: FicheV5,
) -> Iterator[tuple[str, Source]]:
    """Parcourt toutes les sources de la fiche avec leur propriétaire."""
    for infraction in fiche.infractions:
        for source in infraction.sources:
            yield f"Infraction {infraction.id}", source
        for element in infraction.elements_constitutifs:
            for source in element.sources:
                yield f"ElementConstitutif {element.id}", source
        for peine in infraction.peines:
            for source in peine.sources:
                yield f"Peine {peine.id}", source
    for regle in fiche.regles_generales:
        for source in regle.sources:
            yield f"RegleGenerale {regle.id}", source
        for peine in regle.peines:
            for source in peine.sources:
                yield f"Peine {peine.id}", source
    for condition in fiche.conditions:
        for source in condition.sources:
            yield f"Condition {condition.id}", source
    for groupe in fiche.groupes_peines:
        for source in groupe.sources:
            yield f"GroupePeines {groupe.id}", source
    for renvoi in fiche.renvois:
        for source in renvoi.sources:
            yield f"Renvoi {renvoi.id}", source
    for disposition in fiche.dispositions_regime:
        for source in disposition.sources:
            yield f"DispositionRegime {disposition.id}", source
    for incertitude in fiche.incertitudes:
        for source in incertitude.sources:
            yield f"Incertitude {incertitude.id}", source


def _verifier_sources(fiche: FicheV5, erreurs: list[str]) -> None:
    """Vérifie que chaque source appartient bien à l'article de la fiche."""
    for proprietaire, source in _sources_fiche(fiche):
        if source.article != fiche.article:
            erreurs.append(
                f"ARTICLE_SOURCE_DIFFERENT: {proprietaire} cite "
                f"l'article {source.article} au lieu de {fiche.article}"
            )


def _verifier_groupes_conditions(
    fiche: FicheV5,
    registre: dict[str, str],
    erreurs: list[str],
) -> None:
    """Vérifie l'absence de cycles entre groupes de conditions."""
    groupes = {groupe.id: groupe for groupe in fiche.groupes_conditions}
    etats: dict[str, int] = {}

    def visiter(groupe_id: str) -> None:
        if groupe_id not in registre or registre[groupe_id] != "groupe_conditions":
            return
        if etats.get(groupe_id) == 1:
            erreurs.append(f"GROUPE_CONDITION_CYCLE: {groupe_id}")
            return
        if etats.get(groupe_id) == 2:
            return
        etats[groupe_id] = 1
        for sous_groupe in groupes[groupe_id].sous_groupe_ids:
            visiter(sous_groupe)
        etats[groupe_id] = 2

    for groupe_id in groupes:
        visiter(groupe_id)


def _verifier_groupes_peines(
    fiche: FicheV5,
    registre: dict[str, str],
    erreurs: list[str],
) -> None:
    """Vérifie le rattachement des peines aux groupes et à leur sujet."""
    peines_par_infraction = {
        infraction.id: {peine.id for peine in infraction.peines}
        for infraction in fiche.infractions
    }
    peines_par_regle = {
        regle.id: {peine.id for peine in regle.peines}
        for regle in fiche.regles_generales
    }
    groupes_par_peine: dict[str, str] = {}

    for groupe in fiche.groupes_peines:
        if groupe.sujet_type == "infraction":
            peines_du_sujet = peines_par_infraction.get(groupe.sujet_id)
        else:
            peines_du_sujet = peines_par_regle.get(groupe.sujet_id)
        if peines_du_sujet is None:
            continue
        for peine_id in groupe.peine_ids:
            if peine_id not in peines_du_sujet:
                erreurs.append(
                    f"PEINE_HORS_SUJET: {peine_id} n'appartient pas au sujet "
                    f"{groupe.sujet_id} du groupe {groupe.id}"
                )
            if peine_id in groupes_par_peine:
                erreurs.append(
                    f"PEINE_DANS_PLUSIEURS_GROUPES: {peine_id} est dans "
                    f"{groupes_par_peine[peine_id]} et {groupe.id}"
                )
            else:
                groupes_par_peine[peine_id] = groupe.id


def _verifier_conditions(
    fiche: FicheV5,
    registre: dict[str, str],
    erreurs: list[str],
) -> None:
    """Vérifie l'usage réel des conditions et leur portée déclarée."""
    groupes = {groupe.id: groupe for groupe in fiche.groupes_conditions}
    memo: dict[str, set[str]] = {}

    def conditions_du_groupe(groupe_id: str, vus: set[str]) -> set[str]:
        if groupe_id in vus:
            return set()
        if groupe_id in memo:
            return memo[groupe_id]
        groupe = groupes.get(groupe_id)
        if groupe is None:
            return set()
        vus_ici = vus | {groupe_id}
        resultat = set(groupe.condition_ids)
        for sous_groupe in groupe.sous_groupe_ids:
            resultat |= conditions_du_groupe(sous_groupe, vus_ici)
        memo[groupe_id] = resultat
        return resultat

    usages: dict[str, set[tuple[str, str]]] = {
        condition.id: set() for condition in fiche.conditions
    }

    def enregistrer(
        groupe_ids: list[str], type_sujet: str, sujet_id: str
    ) -> None:
        for groupe_id in groupe_ids:
            for condition_id in conditions_du_groupe(groupe_id, set()):
                if condition_id in usages:
                    usages[condition_id].add((type_sujet, sujet_id))

    for infraction in fiche.infractions:
        for peine in infraction.peines:
            enregistrer(peine.condition_groupe_ids, "peine", peine.id)
    for regle in fiche.regles_generales:
        enregistrer(regle.condition_groupe_ids, "regle", regle.id)
        for peine in regle.peines:
            enregistrer(peine.condition_groupe_ids, "peine", peine.id)

    for condition in fiche.conditions:
        usages_condition = usages[condition.id]
        if condition.portee == "commune" and len(usages_condition) < 2:
            erreurs.append(
                f"CONDITION_COMMUNE_UNIQUE: {condition.id} est déclarée "
                "commune mais n'est utilisée que par "
                f"{len(usages_condition)} sujet(s)"
            )
        elif condition.portee == "propre" and len(usages_condition) != 1:
            erreurs.append(
                f"CONDITION_PORTEE_INCOHERENTE: {condition.id} est déclarée "
                f"propre mais a {len(usages_condition)} usage(s)"
            )
        elif condition.portee == "generale":
            if any(type_sujet == "peine" for type_sujet, _ in usages_condition):
                erreurs.append(
                    f"CONDITION_PORTEE_INCOHERENTE: {condition.id} est "
                    "générale mais est attachée à une peine"
                )
            if not any(type_sujet == "regle" for type_sujet, _ in usages_condition):
                erreurs.append(
                    f"CONDITION_ORPHELINE: {condition.id} est générale mais "
                    "n'est rattachée à aucune règle"
                )
        elif condition.portee == "interpretative":
            if any(type_sujet == "peine" for type_sujet, _ in usages_condition):
                erreurs.append(
                    f"CONDITION_INTERPRETATIVE_SUR_PEINE: {condition.id} est "
                    "interprétative mais est attachée à une peine"
                )


def _verifier_citations(
    fiche: FicheV5,
    info: ValidationInfo,
    erreurs: list[str],
) -> None:
    """Vérifie les citations lorsque le corpus est fourni dans le contexte."""
    contexte = info.context
    if not isinstance(contexte, Mapping):
        return
    textes = contexte.get("textes")
    if textes is None:
        return
    if not isinstance(textes, Mapping):
        erreurs.append("CONTEXTE_CITATIONS_INVALIDE: textes doit être un mapping")
        return
    texte_article = textes.get(fiche.article)
    if texte_article is None:
        erreurs.append(f"ARTICLE_INCONNU: {fiche.article}")
        return

    for proprietaire, source in _sources_fiche(fiche):
        cibles = _textes_cibles_citation(
            texte_article, source, fiche.article, erreurs, proprietaire
        )
        if not cibles:
            continue
        citation = normaliser_citation(source.citation)
        if not any(citation in cible for cible in cibles):
            erreurs.append(
                f"CITATION_ABSENTE: {proprietaire} cite "
                f"« {source.citation} » absente de la source"
            )


def _textes_cibles_citation(
    texte_article: Any,
    source: Source,
    article: str,
    erreurs: list[str],
    proprietaire: str,
) -> list[str]:
    """Retourne les textes normalisés où vérifier une citation."""
    if isinstance(texte_article, str):
        return [normaliser_citation(texte_article)]
    if not isinstance(texte_article, Mapping):
        erreurs.append(
            f"CONTEXTE_CITATIONS_INVALIDE: texte de l'article {article} invalide"
        )
        return []

    if source.alinea is not None:
        texte_alinea = texte_article.get(source.alinea)
        if texte_alinea is None:
            erreurs.append(
                f"ALINEA_INCONNU: {source.alinea} absent pour {proprietaire}"
            )
            return []
        if not isinstance(texte_alinea, str):
            erreurs.append(
                f"CONTEXTE_CITATIONS_INVALIDE: alinéa {source.alinea} invalide"
            )
            return []
        return [normaliser_citation(texte_alinea)]

    texte_global = texte_article.get(None)
    if texte_global is None:
        texte_global = texte_article.get("")
    if texte_global is not None:
        if not isinstance(texte_global, str):
            erreurs.append(
                f"CONTEXTE_CITATIONS_INVALIDE: texte global de {article} invalide"
            )
            return []
        return [normaliser_citation(texte_global)]

    citations = [
        normaliser_citation(texte)
        for texte in texte_article.values()
        if isinstance(texte, str)
    ]
    if not citations:
        erreurs.append(
            f"CONTEXTE_CITATIONS_INVALIDE: aucun texte pour {article}"
        )
    return citations


def valider_fiche_v5(
    donnees: Mapping[str, Any],
    textes: Mapping[str, Any],
) -> FicheV5:
    """Valide une fiche V5 et ses citations contre les textes fournis."""
    return FicheV5.model_validate(donnees, context={"textes": textes})


__all__ = [
    "Cible",
    "Condition",
    "DispositionRegime",
    "EffetRegle",
    "ElementConstitutif",
    "FicheV5",
    "FormulePeine",
    "GroupeConditions",
    "GroupePeines",
    "Incertitude",
    "Infraction",
    "Mesure",
    "ModeleStrictV5",
    "Peine",
    "QuantumPeine",
    "RegleGenerale",
    "Renvoi",
    "Source",
    "normaliser_citation",
    "valider_fiche_v5",
]
