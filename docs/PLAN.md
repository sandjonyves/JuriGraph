# Plan de travail — JuriGraph

## 1. État des lieux (vérifié sur votre base)

| Élément | État |
|---|---|
| Articles | 427 nœuds, 425 vectorisés (2048 dims, cosine) |
| Index vectoriel | `article_embedding` ONLINE |
| Index plein texte | `article_texte` ONLINE, mais analyseur `standard-no-stop-words` (pas français) |
| Renvois | 271 dans `renvois.json`, **0 relation `RENVOIE_A` chargée** |
| Couche LLM | inexistante (seule la couche embeddings existe) |
| Tests | 19 tests (embeddings) |
| Volume extraction | 266 articles « emprisonnement », 210 « amende », 44 « mort/à vie », 197 articles contenant le mot "francs" (le mot FCFA n'apparaît jamais dans le texte) |
| Taille max d'un article | ~3 580 caractères → **1 appel LLM par article suffit** |

Conclusion : les fondations (graphe, embeddings, recherche vectorielle) sont prêtes. Il manque la couche LLM, les nœuds métier, et l'évaluation.

---

## 2. Architecture cible

```text
llm/                     # équivalent de embeddings/ : fournisseurs de chat interchangeables
├── base.py              # JSON structuré, retries, cache, coûts, température 0
├── openrouter.py        # chat via OpenRouter
├── gemini.py            # Gemini
└── openai_compat.py     # Ollama / vLLM / OpenAI

schemas/                 # schémas JSON versionnés (pydantic)
├── extraction.py        # fiche Infraction/Peine
├── faits.py             # faits structurés d'un dossier
└── qualification.py     # sortie du pipeline de prédiction

prompts/                 # prompts versionnés (v1, v2…) + few-shots
├── extraction_v1.md
├── qualification_v1.md
└── structuration_faits_v1.md

extract_infractions.py   # article -> fiche JSON (cache + reprise)
verify_extraction.py     # contrôle citations, chiffres, cohérence
load_infractions.py      # chargement idempotent dans Neo4j
search_hybrid.py         # vectoriel + plein texte + renvois + fusion
predict.py               # dossier -> qualification justifiée vérifiée

data/
├── extractions/v1/*.jsonl
├── eval/faits_articles.jsonl      # gold set recherche
├── eval/dossiers.jsonl            # gold set qualification
└── reports/
```

### Schéma de graphe proposé

```cypher
(:Article)-[:DEFINIT_INFRACTION]->(:Infraction)
(:Infraction)-[:PUNIT_PAR]->(:Peine)
(:Infraction)-[:A_POUR_ELEMENT {type:'legal'|'materiel'|'moral'}]->(:ElementConstitutif)
(:Extraction {modele, prompt_version, date, statut, confiance})-[:PORTE_SUR]->(:Article)
```

Propriétés minimales :
- `Infraction {id, libelle, article_source, statut, confiance}`
- `Peine {id, type, nature, quantum_min, quantum_max, unite, quantum_texte, article_source}`
- `ElementConstitutif {id, type, texte, citation}`
- `statut ∈ {auto_ok, a_revoir, valide, rejete}` + `extraction_id` partout (traçabilité).

Identifiants : `INF-320-1`, `PEI-320-1`, `ELT-320-1-2`.

---

## 3. Phase 1 — Extraction Infraction / Peine (priorité, ~1,5 à 2 semaines)

### 1.1 Socle LLM (2 jours)
- [ ] Créer `llm/` sur le modèle de `embeddings/` : interface `BaseChat`, registre, cache.
- [ ] Sortie **JSON strict** (schéma imposé + validation pydantic), température 0.
- [ ] Retries ciblés, backoff, comptage tokens/coût, logs JSONL par run.
- [ ] Cache clé = `hash(modèle + prompt_version + texte article)`, écriture atomique.
- [ ] Mode `--dry-run` sans appel API.

> Choix à faire : un modèle chat **payant de qualité** pour l'extraction (quelques dollars pour 425 articles), ou Gemini gratuit. Les routes `:free` d'OpenRouter sont à éviter pour du juridique.

### 1.2 Schéma et prompt d'extraction (2 jours)
- [ ] Définir le schéma d'une fiche :

```json
{
  "article": "320",
  "infractions": [{
    "libelle": "Vol aggravé",
    "elements_constitutifs": [
      {"type": "materiel", "texte": "...", "citation": "soustraction frauduleuse"}
    ],
    "peines": [{
      "type": "principale", "nature": "emprisonnement",
      "quantum_min": 5, "quantum_max": 10, "unite": "ans",
      "citation": "de cinq (05) à dix (10) ans"
    }]
  }],
  "conditions": ["..."],
  "renvois": ["318"],
  "confiance": 0.0
}
```
- [ ] Règles du prompt : citation **verbatim obligatoire**, interdiction d'inventer, `null` si incertain, pas de conversion d'unité. L'unité d'un montant est recopiée telle qu'écrite dans le texte ("francs"), sans conversion.
- [ ] 3 à 5 exemples few-shot (peine simple, fourchette, amende en francs, mort/à vie, renvoi).
- [ ] Périmètre : 427 articles − 2 exclus (159 abrogé, 362-370 plage) = 425 vectorisés ; − l'article 1 (structurel) = 424 articles à extraire.

### 1.3 Vérificateur automatique (2 jours) — **cœur de la fiabilité**
- [ ] Toute citation doit être une **sous-chaîne exacte** de `Article.texte_complet` après normalisation des espaces/apostrophes/tirets.
- [ ] Tout nombre (quantum, amende) doit apparaître dans la citation ; unité cohérente.
- [ ] Comparer les nombres après suppression des espaces, y compris insécables (ex. "25 000" = "25000").
- [ ] `quantum_min <= quantum_max` ; conversion jours/mois/ans pour comparaison ; cas `à vie` / `mort`.
- [ ] Tout article cité doit exister (`numero` présent en base).
- [ ] Un même article ne peut pas produire deux infractions identiques.
- [ ] Rapport par article : `auto_ok`, `a_revoir`, `rejete`, avec la liste précise des erreurs.
- [ ] Tests unitaires sur fixtures : bonne fiche, citation modifiée, chiffre inventé, fourchette inversée, unité fausse.

### 1.4 Échantillon de relecture humaine (2 jours)
- [ ] 40 articles stratifiés : peine unique, peines multiples, amende en francs, mort/à vie, renvois, formulations ambiguës.
- [ ] Grille d'annotation : libellé, éléments, nature/quantum de peine, citations.
- [ ] Mesurer : exactitude des citations, exactitude des peines, complétude des infractions.
- [ ] Itérer prompt + schéma jusqu'aux seuils.

**Critères d'acceptation Phase 1**
- 100 % des citations vérifiées exactes (sinon article rejeté).
- ≥ 90 % des peines (nature + quantum) correctes sur l'échantillon.
- ≥ 85 % de rappel sur les infractions de l'échantillon.
- 0 article inventé.
- Rechargement idempotent (`MERGE`) et reproductible (cache + version de prompt).

**Livrables** : `extract_infractions.py`, `verify_extraction.py`, `load_infractions.py`, `schemas/extraction.py`, `prompts/extraction_v1.md`, rapport de revue, tests.

---

## 4. Phase 2 — Recherche hybride (~1 semaine)

### 2.1 Prérequis (0,5 jour)
- [ ] Charger les renvois : `python extract_renvois.py code_penal_structure_docx.json --load` (actuellement 0 en base).
- [ ] Reconstruire l'index plein texte avec l'analyseur **français** :

```cypher
DROP INDEX article_texte;
CREATE FULLTEXT INDEX article_texte
FOR (a:Article) ON EACH [a.titre, a.texte_complet]
OPTIONS {indexConfig: {`fulltext.analyzer`: 'french'}};
```

### 2.2 Retrieval (2 jours)
- [ ] `search_hybrid.py` avec 3 voies :
  1. **vectorielle** : top 20 (index existant) ;
  2. **plein texte** : top 20, titre boosté, requête Lucene construite depuis les faits ;
  3. **graphe** : expansion 1 saut via `RENVOIE_A` (entrant + sortant) depuis les 5 meilleurs seeds.
- [ ] Filtres : `abroge = false`, `est_plage = false`, éventuellement Livre/Titre.
- [ ] Fusion par **RRF** (Reciprocal Rank Fusion) plutôt que d'additionner des scores hétérogènes ; dédoublonnage.
- [ ] Sortie avec provenance : `{article, score, sources: ["vector","fulltext","renvoi:320"]}`.
- [ ] Génération de 2 à 4 requêtes par dossier (fait principal, conséquence, circonstances) via règles + LLM.

### 2.3 Évaluation (2 jours)
- [ ] Gold set de 30 à 40 scénarios « faits → articles attendus » (avec un juriste si possible).
- [ ] Métriques : Recall@5, Recall@10, MRR, nDCG.
- [ ] Ablations : vectoriel seul / plein texte seul / hybride / hybride + renvois.
- [ ] Latence cible < 500 ms hors embedding de requête.

**Critère d'acceptation** : Recall@10 ≥ 0,90 sur le gold set, et l'hybride fait mieux que chaque voie seule.

**Livrables** : `search_hybrid.py`, `data/eval/faits_articles.jsonl`, `evaluate_search.py`, rapport d'ablation.

---

## 5. Phase 3 — Pipeline de prédiction (~1,5 semaine)

### 3.1 Structuration des faits (2 jours)
- [ ] `predict.py` étape 1 : faits libres → JSON :
  - parties, action, intention, victime, dommage, arme, lieu, date, montant, circonstances aggravantes, tentative/complicité, incertitudes.
- [ ] Aucune conclusion juridique à ce stade ; questions de clarification si faits insuffisants.

### 3.2 Retrieval (1 jour)
- [ ] Requêtes multiples dérivées des faits structurés / bruts.
- [ ] `search_hybrid.py` → top 10–15 articles, avec texte exact.

### 3.3 Qualification (2 jours)
- [ ] Prompt contraint aux **articles retrouvés uniquement**.
- [ ] Sortie JSON : qualifications, articles cités, éléments satisfaits/non satisfaits, peine encourue, alternatives, confiance.
- [ ] Interdiction d'inventer un article ou une citation.

### 3.4 Vérification et garde-fous (2 jours)
- [ ] Chaque article cité existe en base **et** fait partie des articles retrouvés (sinon rejet).
- [ ] Chaque extrait cité est une sous-chaîne exacte de l'article.
- [ ] Chaque peine annoncée correspond aux nœuds `:Peine` (ou à l'extraction vérifiée).
- [ ] Boucle de correction : renvoyer les erreurs au LLM, 1 nouvelle tentative max, sinon **abstention**.
- [ ] Mention obligatoire « aide à la décision, pas un avis juridique » ; validation humaine.

### 3.5 Évaluation (2 jours)
- [ ] 20 à 30 dossiers (synthétiques + anonymisés) avec qualification attendue.
- [ ] Métriques : exactitude de la qualification principale, rappel des articles, exactitude des citations (100 % exigé), taux d'hallucination (0), taux d'abstention pertinente.
- [ ] Cas adverses : faits insuffisants, plusieurs infractions, tentative, complicité.

**Livrables** : `predict.py`, `schemas/faits.py`, `schemas/qualification.py`, prompts, `data/eval/dossiers.jsonl`, rapport.

---

## 6. Transverse (en continu)

- [ ] **CI GitHub Actions** : `ruff` + `python -m unittest` à chaque push.
- [ ] **Tests** : chaque nouveau module avec fixtures, sans appel réseau (faux fournisseur LLM).
- [ ] **Traçabilité** : version de prompt, modèle, date, hash d'entrée pour chaque fiche.
- [ ] **Confidentialité** : journaux de dossiers en local et gitignorés ; pas de données personnelles dans le dépôt.
- [ ] **Documentation** : README (schéma, commandes), `docs/schema.md`, runbook de relecture.
- [ ] **Coûts** : journaliser tokens et coût estimé par run.

---

## 7. Planning synthétique

| Semaine | Contenu | Jalon |
|---|---|---|
| S1 | LLM layer, schéma, prompt v1, extracteur | 10 fiches produites |
| S2 | Vérificateur, échantillon 40 articles, itérations, loader | Phase 1 validée |
| S3 | Renvois + fulltext FR, `search_hybrid`, gold set, ablations | Recall@10 ≥ 0,90 |
| S4 | Structuration faits, qualification, vérificateur | 1 dossier de bout en bout |
| S5 | Éval 20 dossiers, garde-fous, CI, docs | Phase 3 validée |

En solo à temps partiel, compter **6 à 8 semaines**. Le chemin critique est la **relecture humaine** et la constitution des gold sets, pas le code.

---

## 8. Risques et décisions

| Risque | Mitigation |
|---|---|
| Hallucination de chiffres/citations | vérificateur strict + rejet automatique |
| Modèle gratuit trop faible en juridique | tester 2–3 modèles sur l'échantillon, budget quelques dollars |
| Analyseur plein texte inadapté au français | passer à `french` dès la phase 2 |
| Renvois non chargés | étape 2.1 bloquante |
| Dérive du schéma | prompts et schémas versionnés, JSONL bruts conservés |
| Absence de juriste pour le gold set | commencer par 20 cas, assumer une éval partielle |

**Décisions à prendre maintenant**
1. Modèle LLM et budget (extraction + qualification).
2. Éléments constitutifs en nœuds ou en propriétés JSON.
3. Périmètre des peines : principales seulement, ou aussi accessoires/complémentaires, sursis, circonstances.
4. Politique en cas d'ambiguïté : abstention ou meilleure hypothèse signalée.
5. Qui relit l'échantillon de 40 articles.

---

## 9. Première action concrète

Je propose de démarrer le **lot 1 de la phase 1** :

1. créer `llm/` (interface + OpenRouter/Gemini + JSON strict + cache) ;
2. créer `schemas/extraction.py` et `prompts/extraction_v1.md` ;
3. créer `extract_infractions.py` avec `--dry-run`, cache et reprise ;
4. créer `verify_extraction.py` + tests sur fixtures ;
5. lancer sur **5 articles** pour un premier contrôle visuel, avant les 425.

En parallèle (5 minutes), je peux charger les 271 renvois dans Neo4j et passer l'index plein texte en analyseur français.

Voulez-vous que je commence par ce lot, et sur quel modèle LLM (OpenRouter payant, Gemini gratuit, ou local) ?
