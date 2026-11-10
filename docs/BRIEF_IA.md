# Brief de reprise — JuriGraph

> Document destiné à une autre intelligence artificielle qui reprend le projet.
> Il décrit le but, l’architecture, l’état réel du dépôt, les règles à ne jamais
> enfreindre et les prochaines étapes.
>
> **À lire avant d’agir :**
> 1. `AGENTS.md` (règles de travail locales) ;
> 2. `docs/PLAN.md` (plan complet et critères d’acceptation) ;
> 3. ce document (instantané de l’état du projet).
>
> En cas de contradiction, le code et les règles de `AGENTS.md` priment sur ce
> brief. Ne jamais inventer une information juridique.

---

## 1. Mission du projet

**JuriGraph** est un pipeline **Graph-RAG juridique** appliqué au **Code pénal
camerounais (Loi n° 2016/007)**.

Le système doit :

1. recevoir un dossier décrit en langage libre (faits, personnes, dommages,
   circonstances) ;
2. retrouver les articles pertinents dans un graphe de connaissances Neo4j ;
3. proposer une **qualification juridique justifiée et vérifiable** ;
4. afficher les textes de loi **mot pour mot**, avec leur provenance ;
5. ne jamais décider à la place du juge.

Le projet ne produit pas un « avis juridique ». C’est une **aide à la décision**
qui doit rester vérifiable par un humain, idéalement un juriste.

### Phases du projet

| Phase | Contenu | État |
|---|---|---|
| Phase 1 | Extraction structurée `Infraction` / `Peine` depuis les articles | En cours |
| Phase 2 | Recherche hybride : vectoriel + plein texte + renvois de graphe | À venir |
| Phase 3 | Pipeline dossier → qualification vérifiée | À venir |

Le travail actuel porte sur la **Phase 1** : transformer chaque article du Code
pénal en une fiche JSON fiable, puis la charger dans Neo4j.

---

## 2. Règles absolues

Ces règles ne sont pas des préférences de style. Les enfreindre peut produire
une fausse information juridique.

1. **Ne jamais inventer** un numéro d’article, une peine, une durée, un montant,
   une unité ou une citation de loi.
2. **Toute citation présentée comme du droit** doit être une sous-chaîne exacte
   du texte fourni, accents et ponctuation compris.
3. **Ne jamais compléter** un article avec des connaissances extérieures.
   Si une information manque : `null` pour un quantum, `[]` pour une liste.
4. **Ne pas convertir les unités** : si le texte dit « francs », écrire
   `francs`, jamais `FCFA`.
5. **Les nombres doivent apparaître dans la citation** de la peine.
6. **Les renvois de peine** (`peines_renvoi`) ne contiennent que des numéros
   d’articles réellement écrits dans le texte. Une formule comme « puni comme
   faux témoin » ou « mêmes peines » n’est pas un numéro d’article.
7. **Tout est en français** : commentaires, docstrings, messages, README,
   commits, réponses.
8. **Aucun secret dans le dépôt** : pas de clé API, pas de mot de passe, pas de
   `.env`, pas de cache, pas de journal de run.
9. **Aucun test ne doit appeler une API réseau ni Neo4j.** Utiliser des faux
   objets. Les tests d’intégration Neo4j doivent être ignorés si
   `NEO4J_PASSWORD` est absent.
10. **Une seule tâche à la fois.** Ne pas refactoriser hors périmètre.
11. **Vérifier en exécutant** : tests + lint. Ne jamais écrire « ça marche »
    sans preuve.
12. **Le lancement complet du corpus (`--run`) n’est jamais implicite.** Il doit
    être demandé explicitement par l’utilisateur.

---

## 3. État du dépôt au moment de la rédaction

| Élément | Valeur |
|---|---|
| Dépôt | `sandjonyves/JuriGraph` |
| Branche de travail | `etape-1-extraction` |
| Dernier commit de code avant ce brief | `7ac3faf` — `feat(etape-1): prompt v3, granularité par contexte` |
| Prompt actif | `prompts/extraction_v3.md` |
| Modèle utilisé pour les rejeux | `nvidia/nemotron-3-ultra-550b-a55b:free` via OpenRouter |
| Tests | **89 tests OK** |
| Lint | `ruff check --select E9,F .` → OK |
| Articles dans le corpus | **427** |
| Articles extractibles | **424** |
| Embeddings connus | **425** articles vectorisés (2048 dimensions, cosinus) |
| Fiches d’extraction en cache | Un échantillon seulement, pas le corpus complet |
| `load_infractions.py` | **Inexistant** |
| Nœuds `Infraction` / `Peine` dans Neo4j | **0** au dernier contrôle connu |
| Neo4j pendant la rédaction | **Injoignable** (`bolt://localhost:7687`, connexion refusée) |

> Le compteur Neo4j n’a pas pu être revérifié pendant la rédaction du brief.
> Lancer `env/bin/python check_db.py` quand Neo4j est démarré.

### Ce qui est fait

- Couche LLM interchangeable : `llm/`.
- Schéma Pydantic strict : `schemas/extraction.py`.
- Prompts versionnés v1, v2, v3.
- Extracteur : `extract_infractions.py`.
- Vérificateur : `verify_extraction.py`.
- Cache disque et journal JSONL.
- Tests unitaires.
- Rejeu réel de huit articles : `164`, `186`, `252`, `289`, `124`, `105`,
  `108`, `275`.
- Rejeu v3 de `164` et `289` :
  - `164` → `a_revoir`, avec **quatre infractions** (non-lieu ; juridiction
    pénale avec conditions contravention / délit / crime ; autre juridiction ;
    interprète sans peine) ;
  - `289` → `auto_ok`, avec une peine accessoire de **3 ans** et une autre de
    **10 ans** avec `condition: "en cas de récidive"`.

### Ce qui n’est pas fait

- Échantillon de relecture humaine de 40 articles.
- Extraction complète des 424 articles (`--run`).
- `load_infractions.py` et chargement des `Infraction` / `Peine` dans Neo4j.
- Rapport de revue de la Phase 1.
- Phase 2 : chargement des renvois, index plein texte français, `search_hybrid.py`.
- Phase 3 : `predict.py`, structuration des faits, qualification.

---

## 4. Données et pipeline

### 4.1 Source

Le corpus source est le **Code pénal camerounais**, Loi n° 2016/007.

Le fichier de travail est :

```text
code_penal_structure_docx.json
```

Il contient la hiérarchie complète :

```text
Code
└── Livre
    └── Titre
        └── Chapitre
            └── Section
                └── Article
                    └── Alinéa
```

Le script `parse_code_penal_docx.py` produit ce JSON depuis le DOCX.

### 4.2 Pipeline actuel

```text
DOCX
  │  parse_code_penal_docx.py
  ▼
code_penal_structure_docx.json
  │
  ├── load_neo4j.py
  │     └── hiérarchie + Article + Alinea dans Neo4j
  │
  ├── extract_renvois.py
  │     └── renvois.json (271 relations RENVOIE_A)
  │
  ├── embed_articles.py
  │     └── embeddings + index vectoriel Neo4j
  │
  └── extract_infractions.py
        ├── prompts/extraction_v3.md
        ├── llm/ (chat interchangeable, cache, validation)
        ├── schemas/extraction.py
        └── verify_extraction.py
              └── fiche JSON + statut auto_ok / a_revoir / rejete
```

### 4.3 Rôle des fichiers

| Fichier | Rôle |
|---|---|
| `parse_code_penal_docx.py` | DOCX → `code_penal_structure_docx.json` |
| `load_neo4j.py` | Charge la hiérarchie dans Neo4j (idempotent, `MERGE`) |
| `extract_renvois.py` | Détecte les renvois entre articles |
| `renvois.json` | 271 renvois extraits |
| `embed_articles.py` | Calcule et indexe les embeddings |
| `embeddings/` | Fournisseurs d’embeddings interchangeables |
| `llm/` | Fournisseurs de chat interchangeables |
| `schemas/extraction.py` | Schéma Pydantic d’une fiche |
| `prompts/extraction_v3.md` | Prompt actif d’extraction |
| `extract_infractions.py` | Article → fiche JSON |
| `verify_extraction.py` | Contrôle la fidélité de la fiche au texte |
| `check_db.py` | Contrôle en lecture seule de l’état Neo4j |
| `tests/` | Tests `unittest` |
| `docs/PLAN.md` | Plan complet et critères d’acceptation |

---

## 5. Modèle Neo4j

### 5.1 Nœuds existants

Ne jamais renommer ces labels ni ces propriétés sans instruction explicite.

| Label | Identifiant | Propriétés principales |
|---|---|---|
| `Code` | `CODE` | `nom` |
| `Livre` | `L<numéro>` (ex. `LI`, `LII`) | `id`, `numero`, `titre_texte` |
| `Titre` | — | `id`, `numero`, `titre_texte` |
| `Chapitre` | — | `id`, `numero`, `titre_texte` |
| `Section` | — | `id`, `numero`, `titre_texte` |
| `Article` | `ART-<numero>` (ex. `ART-275`) | `id`, `numero`, `titre`, `texte_brut`, `texte_complet`, `abroge`, `est_plage`, `embedding` |
| `Alinea` | `ART-<numero>-AL<k>` | `id`, `numero`, `texte` |

Remarques :

- `numero` d’un article est du texte : `"275"`, `"18-1"`, etc.
- `texte_complet` = texte brut + alinéas.
- `abroge` et `est_plage` servent à filtrer les articles non exploitables.

### 5.2 Relations existantes

```cypher
(:Parent)-[:CONTIENT {ordre: n}]->(:Enfant)
(:Article)-[:RENVOIE_A {contexte}]->(:Article)
```

### 5.3 Index

| Index | Type | Détail |
|---|---|---|
| `article_embedding` | vectoriel | cosinus, 2048 dimensions |
| `article_texte` | plein texte | actuellement analyseur `standard-no-stop-words`, **pas français** |

La Phase 2 devra reconstruire `article_texte` avec l’analyseur `french`.

### 5.4 Modèle cible pour les infractions

Le modèle cible est prévu par `AGENTS.md` et `docs/PLAN.md` :

```cypher
(:Article)-[:DEFINIT]->(:Infraction)-[:PUNIE_PAR]->(:Peine)
```

Propriétés minimales prévues :

```text
Infraction {id, libelle, article_source, statut, extraction_id}
Peine      {id, type, nature, quantum_min, quantum_max, unite, quantum_texte,
            article_source, extraction_id}
ElementConstitutif {id, type, texte, citation}
```

Identifiants prévus :

```text
Infraction          INF-<article>-<k>
Peine               PEI-<article>-<k>-<j>
ElementConstitutif  ELT-<article>-<k>-<j>
```

`k` = numéro de l’infraction, `j` = numéro de l’élément ou de la peine.
Le suffixe `-j` évite les collisions quand une infraction a plusieurs peines.

> **Attention :** `AGENTS.md` fixe explicitement `DEFINIT` et `PUNIE_PAR`. La
> relation exacte pour rattacher un `ElementConstitutif` n’est pas fixée dans
> `AGENTS.md`. Ne pas inventer un nom de relation sans validation de
> l’utilisateur.

`extraction_id` doit permettre de retrouver la fiche et le run qui ont produit
chaque nœud. Le statut doit être conservé (`auto_ok`, `a_revoir`, `rejete`,
puis `valide` après relecture humaine).

---

## 6. Schéma d’extraction

Fichier : `schemas/extraction.py`.

Toutes les classes héritent de `ModeleStrict`, qui interdit les champs
supplémentaires (`extra="forbid"`).

```python
class Element(ModeleStrict):
    type: Literal["legal", "materiel", "moral"]
    texte: str
    citation: str
    choix: int | None = None


class Peine(ModeleStrict):
    type: Literal["principale", "alternative", "accessoire"]
    nature: Literal[
        "emprisonnement", "amende", "mort",
        "travail_interet_general", "autre"
    ]
    quantum_min: float | None = None
    quantum_max: float | None = None
    unite_min: Literal["ans", "mois", "jours", "francs"] | None = None
    unite_max: Literal["ans", "mois", "jours", "francs"] | None = None
    perpetuite: bool = False
    condition: str | None = None
    citation: str


class Infraction(ModeleStrict):
    libelle: str
    elements_constitutifs: list[Element] = []
    peines: list[Peine] = []
    peines_renvoi: list[str] = []
    peines_au_choix: bool = False


class Fiche(ModeleStrict):
    article: str
    infractions: list[Infraction] = []
    conditions: list[str] = []
    renvois: list[str] = []
```

### Signification des champs

| Champ | Signification |
|---|---|
| `elements_constitutifs` | Éléments légal, matériel, moral de l’infraction |
| `choix` | Même entier non nul = éléments alternatifs ; `null` = obligatoire |
| `peines` | Peines explicitement fixées par le texte |
| `peines_renvoi` | Numéros d’articles vers lesquels le texte renvoie pour la peine |
| `peines_au_choix` | Vrai si le texte permet « l’une ou l’autre » de plusieurs peines |
| `conditions` | Clauses qui ne fixent pas de peine explicite : doublement, conversion, assimilation, etc. |
| `renvois` | Tous les numéros d’articles cités, même hors peine |

Une fiche avec `infractions: []` est **normale** pour les articles du Livre I
qui définissent le système des peines, des notions ou des renvois. Le
vérificateur ne doit pas la rejeter pour ce seul motif.

---

## 7. Prompts d’extraction

Les prompts sont versionnés. Ne jamais modifier un prompt déjà utilisé sans
créer une nouvelle version :

```text
prompts/extraction_v1.md
prompts/extraction_v2.md
prompts/extraction_v3.md   ← actif
```

### 7.1 Évolution

| Version | Apport principal |
|---|---|
| v1 | Première extraction Infraction / Peine |
| v2 | Nombres à séparateur de milliers, `peines_renvoi` limité aux numéros écrits, clause explicite transformée en `Peine` avec `condition`, `conditions` vide si `infractions` vide |
| v3 | Granularité par contexte, phrase « puni comme… » conservée comme infraction distincte, une `Peine` par cas dans une même phrase |

### 7.2 Règles importantes du prompt v3

- Une infraction par **contexte principal**.
- Si des sous-clauses a), b), c) visent des contextes différents (autre
  procédure, autre juridiction, autre qualité de l’auteur), créer **une
  infraction par contexte**.
- Les sous-cas internes à un contexte (contravention / délit / crime) sont des
  `Peine.condition` de **cette** infraction.
- Un alinéa qui décrit un autre fait avec sa propre peine est une infraction
  distincte.
- Une phrase qui définit un acte punissable mais ne donne la peine que par une
  formule sans numéro d’article est une **infraction à part entière**, avec
  `peines: []` et `peines_renvoi: []`. Ne jamais la supprimer.
- Quand une même phrase donne deux durées ou montants selon des cas, créer
  **une `Peine` par cas**, chacune avec sa `condition` et sa citation.
- Une clause qui fixe explicitement une peine devient une `Peine` avec
  `condition` exacte, même si le cas est défini par renvoi.
- `conditions` est réservé aux clauses qui ne fixent **aucune peine explicite**.
- Si l’article ne définit aucune infraction : `infractions: []` et
  `conditions: []`.
- Réponse **JSON uniquement**, sans balises Markdown ni commentaire.

### 7.3 Pourquoi v3 existe

Sur `164`, le modèle v2 produisait une fiche `auto_ok` mais incomplète :
certaines branches de l’article étaient fusionnées. Sur `289`, il produisait une
seule peine accessoire de 3 ans, sans la seconde de 10 ans « en cas de
récidive ». v3 impose la granularité par contexte et une peine par cas.

---

## 8. Vérificateur

Fichier : `verify_extraction.py`.

Le vérificateur **ne juge pas le droit**. Il contrôle la fidélité de la fiche au
texte de l’article.

### 8.1 Contrôles effectués

- L’article de la fiche correspond à l’article demandé.
- Chaque citation est une sous-chaîne exacte du texte.
- Les nombres des peines apparaissent dans la citation.
- Les fourchettes ne sont pas inversées.
- Les unités sont cohérentes avec le texte.
- Les `peines_renvoi` sont des articles existants et écrits dans le texte.
- Les `renvois` sont des articles existants et écrits dans le texte.
- Une infraction sans peine ni `peines_renvoi` passe en `a_revoir`.
- Une `condition` contenant « puni comme », « même peine » ou « mêmes peines »
  passe la fiche en `a_revoir`.

### 8.2 Statuts

| Statut | Signification |
|---|---|
| `auto_ok` | Aucun rejet, aucun avertissement |
| `a_revoir` | Fiche exploitable mais un humain doit vérifier un point |
| `rejete` | Erreur dure : citation fausse, nombre inventé, renvoi inexistant, etc. |
| `valide` | Statut final après relecture humaine (pas produit par le vérificateur) |

### 8.3 Nombres à séparateur de milliers

Règle implémentée :

- un point suivi d’**exactement trois chiffres** est un séparateur de milliers :
  `5.000` = `5000` ;
- `5.5` reste `5.5` et ne devient pas `5500`.

Des tests couvrent ces deux cas.

---

## 9. Cache et journal LLM

### 9.1 Cache

Fichier : `llm/cache.py`.

La clé est un SHA-256 calculé sur :

```text
modèle + version de prompt + schéma + entrée utilisateur
```

Dans `llm/validation.py`, la « version » passée au cache vaut :

```text
prompt_version + "\n" + prompt système complet
```

Le **contenu complet du prompt** est donc inclus dans le hachage. Changer le
contenu de `extraction_v3.md` sans changer son nom invalide automatiquement le
cache. Un test vérifie qu’un même nom de version avec un contenu différent ne
produit pas de cache hit.

Chemins :

```text
data/cache/llm_cache.json
data/logs/llm_runs.jsonl
```

Ces fichiers sont **gitignorés** et ne doivent jamais être commités.

### 9.2 Journal

Chaque appel écrit une ligne JSONL avec :

- date ;
- fournisseur ;
- modèle ;
- schéma ;
- tokens entrée / sortie ;
- coût estimé si les tarifs sont configurés ;
- durée ;
- cache hit ;
- nombre de tentatives.

Aucune clé API n’est écrite dans le journal.

### 9.3 État du cache

Le cache contient uniquement les articles de l’échantillon rejoué. Aucun
lancement complet des 424 articles n’a été effectué. Un `--run` avec le prompt
v3 déclenchera de vrais appels API pour les articles non encore présents dans le
cache.

---

## 10. Commandes utiles

### 10.1 Environnement

Le `python` système n’est pas dans le `PATH`. Utiliser l’environnement virtuel :

```bash
env/bin/python --version
env/bin/ruff --version
```

Ou activer :

```bash
source env/bin/activate
```

Les secrets sont lus depuis `.env` par `python-dotenv`. Ne jamais afficher
`.env` ni recopier une clé dans une commande ou un fichier.

### 10.2 Tests et lint

```bash
env/bin/python -m unittest discover -s tests
env/bin/ruff check --select E9,F .
```

Résultat attendu au moment du brief :

```text
Ran 89 tests ... OK
All checks passed!
```

### 10.3 Extraction sans appel API

```bash
env/bin/python extract_infractions.py --dry-run --run
env/bin/python extract_infractions.py --dry-run --numero 275
```

Sortie actuelle du dry-run complet :

```text
Articles extractibles : 424 / 427.
424 articles seraient traités (--run).
```

### 10.4 Extraction réelle d’un article

```bash
env/bin/python extract_infractions.py --numero 164
```

Le fournisseur et le modèle viennent de `.env` :

```env
LLM_PROVIDER=openrouter
LLM_MODEL=<identifiant-du-modele>
OPENROUTER_API_KEY=<clé>
```

Pour les rejeux de cette session, le modèle était :

```text
openrouter:nvidia/nemotron-3-ultra-550b-a55b:free
```

> Les routes `:free` sont pratiques pour tester, mais le plan recommande un
> modèle payant de qualité pour du juridique. Le modèle doit rester
> interchangeable et configurable, jamais codé en dur.

### 10.5 Corpus complet

```bash
env/bin/python extract_infractions.py --run
```

**Ne pas lancer sans demande explicite de l’utilisateur.** C’est une action
coûteuse et longue.

### 10.6 Neo4j

```bash
env/bin/python check_db.py
env/bin/python load_neo4j.py code_penal_structure_docx.json
env/bin/python extract_renvois.py code_penal_structure_docx.json --load
env/bin/python embed_articles.py code_penal_structure_docx.json
```

`check_db.py` est en lecture seule. Si Neo4j est éteint, il affiche une erreur
claire et s’arrête. Ne pas boucler sur une dépendance absente.

---

## 11. État des tâches

Le découpage opérationnel utilisé dans cette session est le suivant. Il complète
le plan général ; les numéros peuvent évoluer si l’utilisateur les redéfinit.

### 11.1 Réalisé

- **Socle LLM** : fournisseurs interchangeables, JSON strict, retries, cache,
  journal, mode `--dry-run`.
- **Schéma** : `Fiche`, `Infraction`, `Peine`, `Element`.
- **Prompts v1 → v3**.
- **Extracteur** : `extract_infractions.py` avec `--dry-run`, `--numero`,
  `--limit`, `--run`.
- **Vérificateur** : citations, nombres, unités, renvois, pénalités manquantes,
  conditions à revoir.
- **Tests** : 89 tests, aucun appel réseau réel.
- **Rejeu** : huit articles, puis rejeu v3 de `164` et `289`.

### 11.2 Reste à faire

#### A. Revue de l’échantillon (étape de travail 1.7)

- Extraire un échantillon stratifié d’environ **40 articles** :
  - peine unique ;
  - peines multiples ;
  - amendes en francs ;
  - mort / emprisonnement à vie ;
  - renvois ;
  - formulations ambiguës.
- Relire les fiches avec une grille :
  - libellé ;
  - éléments constitutifs ;
  - nature et quantum des peines ;
  - citations.
- Mesurer :
  - exactitude des citations ;
  - exactitude des peines ;
  - rappel sur les infractions.
- Itérer le prompt ou le schéma si les seuils ne sont pas atteints.
- Rédiger un rapport de revue.

Critères d’acceptation de la Phase 1 :

- 100 % des citations vérifiées exactes ;
- ≥ 90 % des peines (nature + quantum) correctes sur l’échantillon ;
- ≥ 85 % de rappel sur les infractions ;
- 0 article inventé ;
- rechargement idempotent et reproductible.

#### B. Extraction complète (étape de travail 1.8)

- Lancer `--run` sur les 424 articles extractibles.
- Surveiller :
  - coût ;
  - taux de `auto_ok` / `a_revoir` / `rejete` ;
  - erreurs de validation JSON ;
  - articles sans infraction.
- Ne lancer qu’après validation de l’échantillon et demande explicite.

#### C. Chargement Neo4j (étape de travail 1.9)

Créer `load_infractions.py` :

- lire les fiches JSON ;
- créer les nœuds `Infraction`, `Peine`, et les éléments prévus ;
- relier à `Article` avec `DEFINIT` et `PUNIE_PAR` ;
- utiliser `MERGE` pour être idempotent ;
- conserver `extraction_id` et le statut ;
- vérifier les compteurs après chargement.

Ne pas inventer de relation pour les éléments constitutifs sans validation.

#### D. Phase 2 — Recherche hybride

- Vérifier le chargement des 271 renvois (`RENVOIE_A`) avec `check_db.py`.
  Le plan initial indiquait 0 relation chargée, mais un contrôle plus récent a
  compté 271 relations dans Neo4j. Revalider avant toute action pour éviter un
  double chargement.
- Reconstruire l’index plein texte avec l’analyseur `french`.
- Écrire `search_hybrid.py` :
  - vectoriel : top 20 ;
  - plein texte : top 20, titre boosté ;
  - graphe : expansion 1 saut via `RENVOIE_A` ;
  - fusion par RRF ;
  - provenance dans les résultats.
- Constituer un gold set de 30 à 40 scénarios.
- Mesurer Recall@5, Recall@10, MRR, nDCG.
- Faire des ablations : vectoriel seul, plein texte seul, hybride, hybride + renvois.

#### E. Phase 3 — Qualification

- `predict.py` : faits libres → faits structurés.
- Retrieval sur les faits.
- Qualification contrainte aux articles retrouvés.
- Vérification des citations et des peines.
- Boucle de correction, puis abstention si nécessaire.
- Mention obligatoire : aide à la décision, pas un avis juridique.
- Évaluation sur 20 à 30 dossiers.

---

## 12. Pièges connus

1. **`5.000` ≠ `5.5`**
   - `5.000` = 5000 (séparateur de milliers) ;
   - `5.5` = 5,5.
   - Ne pas appliquer la règle des milliers à un point suivi d’un ou deux
     chiffres.

2. **« puni comme… » n’est pas un renvoi**
   - « puni comme faux témoin » ou « mêmes peines » ne doit pas aller dans
     `peines_renvoi`.
   - C’est une infraction à part entière, avec peines vides.
   - Sa présence dans `conditions` déclenche `a_revoir`.

3. **`conditions` ne doit pas servir de fourre-tout**
   - Une peine explicitement fixée doit devenir une `Peine`, avec sa
     `condition`.
   - `conditions` est réservé aux clauses sans peine explicite.

4. **Article 164**
   - Quatre infractions attendues.
   - L’interprète judiciaire n’a ni peine ni renvoi : c’est normal qu’il soit
     `a_revoir`.
   - Ce `a_revoir` est un signal de relecture, pas un échec de l’extraction.

5. **Article 289**
   - Un seul contexte principal, mais plusieurs peines.
   - La peine accessoire de 3 ans et celle de 10 ans « en cas de récidive »
     doivent être deux `Peine` distinctes.
   - Ne pas confondre avec la granularité par contexte de l’article 164.

6. **Cache et prompt**
   - Changer le contenu d’un prompt sans changer son nom est détecté par le
     hachage du prompt complet.
   - Ne pas vider le cache à la main sans raison : il sert à éviter des appels
     coûteux.

7. **Tests**
   - Aucun test ne doit appeler OpenRouter, Gemini ou Neo4j.
   - Utiliser `FauxChat`, des fixtures et des `TemporaryDirectory`.
   - Les tests d’intégration Neo4j doivent être `skipUnless` sur
     `NEO4J_PASSWORD`.

8. **Neo4j**
   - Peut être éteint. `check_db.py` le dit clairement.
   - Ne pas boucler sur une connexion refusée.
   - Ne pas écrire dans Neo4j sans demande explicite.

9. **Git**
   - Ne jamais `git add .` ni `git add -A`.
   - Ne jamais committer `.env`, une clé, un cache, un journal, `JuriGraph.zip`.
   - Ne jamais `git push --force`, `git reset --hard`, ni fusionner dans `main`.
   - Si le push échoue faute de réseau : s’arrêter, ne pas réessayer en boucle.

10. **Secrets**
    - Les clés sont dans `.env`.
    - Ne jamais les afficher dans une réponse, un log ou un commit.
    - `.env.example` contient des placeholders, pas de vraies clés.

---

## 13. Ce qu’un nouvel agent doit faire en arrivant

Ordre recommandé :

```bash
# 1. Lire les règles et le plan
sed -n '1,220p' AGENTS.md
sed -n '1,260p' docs/PLAN.md

# 2. Vérifier l’état Git
git status --short --branch
git log --oneline -6

# 3. Vérifier les tests
env/bin/python -m unittest discover -s tests
env/bin/ruff check --select E9,F .

# 4. Vérifier le corpus sans appel API
env/bin/python extract_infractions.py --dry-run --run

# 5. Vérifier Neo4j si disponible
env/bin/python check_db.py
```

Ensuite :

- si la tâche est **documentaire** : ne pas toucher au code ;
- si la tâche est **extraction** : utiliser `--dry-run` d’abord, puis
  `--numero` ou `--limit`, jamais `--run` sans accord ;
- si la tâche est **Neo4j** : vérifier que la base est démarrée et faire un
  `--dry-run` quand le script le permet ;
- si la tâche est **recherche** : attendre que les renvois soient chargés et que
  l’index plein texte soit en français.

---

## 14. Exemple de fiche (structure)

Exemple **schématique** : les valeurs entre chevrons ne sont pas des citations
réelles. Ne jamais les utiliser comme texte de loi.

```json
{
  "article": "<numéro>",
  "infractions": [
    {
      "libelle": "<libellé>",
      "elements_constitutifs": [
        {
          "type": "materiel",
          "texte": "<description>",
          "citation": "<citation exacte>",
          "choix": null
        }
      ],
      "peines": [
        {
          "type": "principale",
          "nature": "emprisonnement",
          "quantum_min": 3,
          "quantum_max": 5,
          "unite_min": "ans",
          "unite_max": "ans",
          "perpetuite": false,
          "condition": null,
          "citation": "<citation exacte contenant les nombres>"
        }
      ],
      "peines_renvoi": [],
      "peines_au_choix": false
    }
  ],
  "conditions": [],
  "renvois": []
}
```

Une fiche réelle doit être lue et vérifiée avec `verify_extraction.py`. Le JSON
seul ne prouve pas que la citation est exacte.

---

## 15. Résumé en dix lignes

1. JuriGraph est un Graph-RAG sur le Code pénal camerounais.
2. La Phase 1 extrait des fiches `Infraction` / `Peine` depuis chaque article.
3. Le corpus contient 427 articles, dont 424 extractibles.
4. Le prompt actif est `prompts/extraction_v3.md`.
5. Le schéma Pydantic est strict et versionné.
6. Le vérificateur contrôle citations, nombres, unités et renvois.
7. Les statuts sont `auto_ok`, `a_revoir`, `rejete`, puis `valide`.
8. Aucun lancement complet des 424 articles n’a encore été fait.
9. `load_infractions.py` et les nœuds `Infraction` / `Peine` restent à créer.
10. La règle d’or : **ne jamais inventer un article, une peine ou une citation**.

---

*Fin du brief. Pour toute décision juridique ou tout lancement coûteux, demander
validation à l’utilisateur.*
