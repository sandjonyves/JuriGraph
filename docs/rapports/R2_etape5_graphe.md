# Rapport R2 — Étape 5 : graphe prêt pour la recherche

**Date :** 28 novembre 2026
**Branche :** `etape-5-graphe` (créée depuis `etape-3-prompt-v5`, voir § 5)
**Nature :** audit en lecture seule. **Aucune écriture dans Neo4j.**

## 1. Objectif

Avant de construire la recherche hybride (étape 8), vérifier que le graphe
contient bien :

1. les 271 relations `RENVOIE_A` de `renvois.json` ;
2. un index plein texte `article_texte` avec l'analyseur français ;
3. une hiérarchie complète (aucun article isolé).

## 2. Constat principal : l'état réel diffère de la documentation

`docs/PLAN.md` et `docs/BRIEF_IA.md` indiquaient « 0 relation `RENVOIE_A` » et
un analyseur `standard-no-stop-words`. Le relevé du 28/11/2026 montre que ces
deux points **avaient déjà été corrigés** dans la base (probablement lors de
la correction `862562a fix(etape-2): index plein texte avec analyseur
français` et d'un chargement des renvois non tracé dans le journal).

**Conséquence :** les tâches prévues « charger les renvois » et « reconstruire
l'index » sont devenues inutiles. Elles n'ont pas été exécutées, ce qui évite
une suppression d'index sans nécessité. L'étape se réduit à un audit.

**Leçon méthodologique :** l'état du graphe doit être mesuré, pas supposé à
partir de la documentation. Le script d'audit ajouté rend ce contrôle
reproductible en une commande.

## 3. Méthode

| Fichier | Rôle |
|---|---|
| `scripts/audit_graphe.py` | Audit en lecture seule, avec `--dry-run` |
| `tests/test_audit_graphe.py` | 4 tests hors ligne (comparaison des renvois, Jaccard) |
| `data/reports/audit_graphe_etape5.txt` | Sortie brute de l'audit |

Commandes exécutées :

```text
$ env/bin/python check_db.py
$ env/bin/python scripts/audit_graphe.py
```

## 4. Résultats

### 4.1 Base

Neo4j **2026.10.1**.

| Label | Nœuds |
|---|---:|
| Code | 1 |
| Livre | 2 |
| Titre | 9 |
| Chapitre | 37 |
| Section | 54 |
| Article | 427 (425 avec embedding) |
| Alinea | 627 |

- Articles sans parent : **0**.
- Les articles sont répartis sous **78 parents directs** (section, chapitre ou
  titre selon la profondeur) : minimum 1, **médiane 4**, maximum 31 articles.
  La médiane de 4 rend raisonnable l'expansion « voisins de même parent »
  prévue à l'étape 8 ; le parent de 31 articles devra être plafonné.

### 4.2 Renvois

| Mesure | Valeur |
|---|---:|
| Paires dans `renvois.json` | 271 |
| Paires en base | 271 |
| Absentes en base | 0 |
| En trop en base | 0 |

Contrôle hors ligne complémentaire : 271 paires distinctes, 0 auto-renvoi,
toutes les sources et cibles existent dans le corpus. 126 articles distincts
sont la cible d'au moins un renvoi.

### 4.3 Index plein texte

`article_texte` : `ONLINE`, analyseur `french`. Test sur les 10 premiers
résultats :

| Requête A | Requête B | Rés. A | Rés. B | Jaccard |
|---|---|---:|---:|---:|
| delit | délit | 10 | 10 | 1,00 |
| meurtre | meurtres | 4 | 4 | 1,00 |
| evasion | évasion | 3 | 3 | 1,00 |
| vol | vols | 4 | 4 | 1,00 |

L'analyseur neutralise les accents et le pluriel : **aucune normalisation
côté requête n'est nécessaire**.

### 4.4 Tests

```text
$ env/bin/python -m unittest discover -s tests
Ran 196 tests — OK (expected failures=10)
$ env/bin/ruff check --select E9,F .
All checks passed!
```

## 5. Difficultés et décisions

- **`main` n'a pas reçu les étapes 0 à 3.** Créer la branche depuis `main`,
  comme le prévoit `AGENTS.md`, aurait fait perdre `check_db.py`, `llm/`, le
  `.gitignore` complet et la CI. La branche a été créée depuis
  `etape-3-prompt-v5`. **Les branches doivent être fusionnées dans l'ordre :**
  `etape-0-base` → `etape-1-extraction` → `etape-2-schema-v5` →
  `etape-3-prompt-v5` → `etape-5-graphe` → `etape-8-recherche`.
- **Dépréciation Neo4j 2026.10 :** `db.index.fulltext.queryNodes` est signalé
  comme remplacé par la syntaxe `SEARCH`. La procédure fonctionne toujours ;
  les avertissements sont masqués dans l'audit. À surveiller pour une future
  migration.

## 6. Observations utiles pour l'article

- Le graphe est petit (427 articles, 271 renvois, 126 cibles) : l'expansion par
  renvois touche environ 30 % des articles, ce qui laisse espérer un apport
  mesurable sans noyer les résultats.
- La structure par parent direct (médiane de 4 articles) est une source de
  voisinage juridique distincte des renvois explicites ; son apport sera mesuré
  à l'étape 8.

✅ **Étape 5 terminée.** Le graphe est conforme ; aucune écriture n'a été nécessaire.
