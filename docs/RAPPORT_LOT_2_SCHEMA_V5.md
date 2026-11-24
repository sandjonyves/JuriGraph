# Rapport — Lot 2 : schéma d’extraction V5

Date : 24 novembre 2026  
Branche : `etape-2-schema-v5`  
Périmètre : implémentation du schéma Pydantic V5 et de ses tests, sans extraction réelle.

## 1. Objectif

Implémenter le schéma d’extraction juridique V5 décrit dans
`docs/SCHEMA_EXTRACTION_V5_PROPOSITION.md`, en conservant V4 intact et sans
conversion automatique V4 → V5.

## 2. Fichiers livrés

| Fichier | Rôle |
|---|---|
| `schemas/extraction_v5.py` | Modèles Pydantic V5 et validateurs. |
| `tests/test_schema_v5.py` | 51 tests hors ligne V5. |
| `docs/RAPPORT_LOT_2_SCHEMA_V5.md` | Ce rapport. |

Aucun fichier existant n’a été modifié pour cette tâche. En particulier :

- `schemas/extraction.py` reste intact ;
- `verify_extraction.py` reste intact ;
- les prompts V1 à V4 restent intacts ;
- le corpus, le cache et l’échantillon de 40 articles ne sont pas modifiés ;
- `load_neo4j.py` n’est pas modifié.

## 3. Architecture

Le schéma V5 est isolé dans `schemas/extraction_v5.py`. La fiche racine est
`FicheV5`, avec :

- `schema_version = "5.0"` ;
- `article`, `type_article` ;
- `infractions`, `regles_generales` ;
- `dispositions_regime` ;
- `conditions`, `groupes_conditions`, `groupes_peines` ;
- `renvois`, `incertitudes`.

Entités implémentées :

`FicheV5`, `Infraction`, `ElementConstitutif`, `Peine`, `QuantumPeine`,
`Mesure`, `FormulePeine`, `Condition`, `GroupeConditions`, `GroupePeines`,
`RegleGenerale`, `EffetRegle`, `Renvoi`, `Cible`, `DispositionRegime`,
`Source`, `Incertitude`.

### Validation des citations

La validation structurelle est toujours active avec `FicheV5.model_validate`.
La validation textuelle des citations s’active lorsque le corpus est fourni :

```python
from schemas.extraction_v5 import valider_fiche_v5

fiche = valider_fiche_v5(donnees, textes)
```

Cela évite de coupler le schéma au corpus et permet de vérifier les citations
exactes lorsqu’un appelant dispose des textes.

## 4. Validateurs principaux

- `extra="forbid"` et rejet des flottants non finis.
- Unicité, forme et article des identifiants.
- Résolution de toutes les références internes.
- Contrôle du type des cibles internes.
- Article de chaque `Source` identique à l’article de la fiche.
- Vérification des citations et alinéas avec le corpus fourni.
- Quantums : fixe, fourchette, minimum, maximum, perpétuité, formule.
- Cohérence nature/quantum : amende en montant, emprisonnement en durée,
  peine de mort sans quantum.
- Objet obligatoire pour confiscation, retrait, suspension et déchéance.
- `sous_type` obligatoire lorsque `nature = "autre"`.
- Peine par renvoi exigeant au moins un `renvoi_id`.
- Groupes de conditions : membres non vides, `OU` à deux membres minimum,
  cycles interdits.
- Groupes de peines : deux peines minimum, sauf justification explicite,
  appartenance à un seul groupe, peines rattachées au bon sujet.
- Conditions communes utilisées au moins deux fois, conditions propres
  utilisées une seule fois.
- Règles sans effet refusées, multiplication sans facteur refusée, formule
  sans formulaire refusée.
- Renvoi sans cible refusé, cible textuelle sans libellé refusée.
- Articles `regle_generale` et `regime_peines` sans infraction.

## 5. Cas critiques

| Article | Résultat obtenu |
|---|---|
| `124` | Une infraction, trois peines. |
| `158` | `COND-158-A` commune aux deux premières peines. |
| `289` | `COND-289-1` commune aux deux peines de retrait. |
| `347` | Aucune infraction, deux règles. |
| `135-2` | Deux infractions ; formule au décuple du profit, non convertie en montant fixe. |
| `226` | Confiscation explicite, accessoire, objet `marchandises`. |
| `164` | Renvoi textuel accepté, statut `textuelle`, peine d’origine `renvoi`. |
| `17`, `18`, `18-1`, `19`, `21` | Aucune infraction, dispositions de régime. |

Les huit exemples JSON du document V5 sont validés contre le corpus local :
8/8.

## 6. Vérifications exécutées

### Tests V5

```text
$ env/bin/python -m unittest tests.test_schema_v5
Ran 51 tests in 0.045s
OK
```

### Tests V4 et audit hors ligne

```text
$ env/bin/python -m unittest tests.test_schema_v5 tests.test_audit_v4 \
    tests.test_extract_infractions tests.test_llm_validation \
    tests.test_schemas tests.test_verify_extraction
Ran 154 tests in 0.097s
OK (expected failures=10)
```

Détail :

- `tests.test_schemas` : 12/12 ;
- `tests.test_audit_v4` : 26 tests, 10 `expectedFailure` documentés ;
- total hors ligne : 154 tests, tous verts.

### Ruff

```text
$ env/bin/ruff check --select E9,F .
All checks passed!
```

### Absence d’appels réseau / Neo4j dans les fichiers V5

```text
$ grep -nE 'requests|httpx|urllib|socket|neo4j|Neo4j|HTTPServer|openrouter|OpenRouter|LLM_' \
    tests/test_schema_v5.py schemas/extraction_v5.py
(no output)
```

### Tests non exécutés

29 tests historiques n’ont pas été lancés :

- `tests/test_llm.py` : 10 tests ;
- `tests/test_embeddings.py` : 19 tests.

Ces tests démarrent un serveur HTTP local. Ils ne sont pas modifiés et ne font
pas partie du schéma V5.

## 7. Compatibilité et limites

- V4 reste utilisable : aucun champ ni validateur V4 n’a été modifié.
- Aucun convertisseur V4 → V5 n’a été créé.
- Le schéma V5 ne produit pas encore de statut global `auto_ok` / `a_revoir`.
  Le vérificateur V5 reste à écrire.
- Pour `164`, le schéma garantit un renvoi textuel structurellement valide ;
  il ne classe pas automatiquement la fiche en `a_revoir`.
- Le contrôle « aucune infraction pour `347` et `17`–`21` » repose sur
  `type_article` et sur les tests de non-régression. Une modification
  frauduleuse de `type_article` ne serait pas détectée par le seul schéma.
- Décisions juridiques encore à valider : lecture de `158`, portée de `289`
  alinéas 2 et 3, nature de la privation de `347`, portée de `135-2` alinéa 3,
  sens de `cumul_ou_alternative`, coexistence Neo4j V4/V5.

## 8. Git

- Aucun commit ni push n’a été effectué avant ce rapport.
- Les fichiers du Lot 2 sont committés sur `etape-2-schema-v5`.
- `main` n’est pas modifiée.
- Aucun `git add .` ni `git add -A`.

## 9. Verdict

L’implémentation V5 est fonctionnelle et couverte par 51 tests hors ligne.
Les tests V4 et d’audit restent verts, Ruff passe, et les huit cas critiques
sont couverts.

✅ **Lot 2 terminé — en attente de validation pour le Lot 3.**
