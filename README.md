# JuriGraph ⚖️🔗

**JuriGraph** est un pipeline d'ingestion, de modélisation en graphe de connaissances et de recherche sémantique (Legal Graph-RAG) appliqué au **Code pénal camerounais (Loi n° 2016/007)**.

Il combine la puissance d'une base orientée graphe (**Neo4j**) et des modèles d'embeddings de Google (**Gemini API**) pour permettre des recherches à la fois hiérarchiques, lexicales et vectorielles.

---

##  Fonctionnalités

1. **Extraction structurée** : Parsing de documents légaux `.docx` (via Pandoc) vers une structure JSON hiérarchique :
   $$\text{Code} \rightarrow \text{Livres} \rightarrow \text{Titres} \rightarrow \text{Chapitres} \rightarrow \text{Sections} \rightarrow \text{Articles} \rightarrow \text{Alinéas}$$
2. **Graphe de connaissances Neo4j** :
   - Relations hiérarchiques ordonnées : `(:Parent)-[:CONTIENT {ordre: n}]->(:Enfant)`
   - Relations croisées de renvois juridiques : `(:Article)-[:RENVOIE_A]->(:Article)`
   - Index plein texte (Fulltext search) sur le titre et le contenu des articles.
3. **Recherche sémantique vectorielle (modèle interchangeable)** :
   - Calcul des vecteurs avec contexte légal (Livre, Titre, Chapitre).
   - Fournisseurs interchangeables : Gemini, OpenRouter, ou tout serveur compatible OpenAI (Ollama, vLLM, LM Studio, OpenAI).
   - Indexation vectorielle native dans Neo4j (similarité cosinus).
   - Requêtes en langage naturel (ex. *"Quelles sont les peines pour blessures volontaires ?"*).

---

##  Structure du Projet

```text
├── parse_code_penal_docx.py       # Extraction du DOCX vers structure JSON
├── code_penal_structure_docx.json # Structure complète extraite
├── load_neo4j.py                  # Chargement de la hiérarchie dans Neo4j
├── extract_renvois.py             # Détection et création des relations de renvois
├── embed_articles.py              # Orchestration : embeddings & index vectoriel
├── embeddings/                    # Fournisseurs d'embeddings interchangeables
│   ├── base.py                    # Interface commune : lots, retry, normalisation
│   ├── gemini.py                  # Google Gemini
│   ├── openrouter.py              # OpenRouter (multi-modèles)
│   └── openai_compat.py           # Ollama, vLLM, LM Studio, OpenAI, Mistral...
├── renvois.json                   # Renvois extraits entre articles
├── neo4j-2026-10-23T02-35-31.dump # Dump de sauvegarde de la base Neo4j
├── requirements.txt               # Dépendances Python
├── .env.example                   # Modèle de variables d'environnement
└── .gitignore                     # Exclusion des fichiers sensibles et temporaires
```

---

##  Installation & Configuration

### 1. Cloner le projet et créer l'environnement virtuel

```bash
git clone https://github.com/sandjonyves/JuriGraph.git
cd JuriGraph
python -m venv env
# Activation :
# Windows PowerShell :
.\env\Scripts\Activate.ps1
# Linux/macOS :
source env/bin/activate
```

### 2. Installer les dépendances

```bash
pip install -r requirements.txt
```

### 3. Configurer les variables d'environnement

Copiez `.env.example` en `.env` et renseignez vos clés :
```bash
cp .env.example .env
```

Dans `.env` :
```env
GEMINI_API_KEY=votre_cle_gemini
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=votre_mot_de_passe_neo4j
NEO4J_DATABASE=neo4j
```

> Prérequis : **Neo4j 5.11+** (index vectoriels natifs). Le script utilise
> automatiquement la clause `SEARCH` sur Neo4j 2026.01+ et l'ancienne procédure
> `db.index.vector.queryNodes` sur 5.x.

---

## 💻 Utilisation

### Étape 1 : Charger les données dans Neo4j
```bash
python load_neo4j.py code_penal_structure_docx.json
```

### Étape 2 : Extraire et charger les renvois entre articles
```bash
python extract_renvois.py code_penal_structure_docx.json --load
```

### Étape 3 : Calculer les embeddings et indexer dans Neo4j
```bash
python embed_articles.py code_penal_structure_docx.json
# aperçu sans clé API ni Neo4j :
python embed_articles.py code_penal_structure_docx.json --dry-run
```

### Étape 4 : Effectuer une recherche en langage naturel
```bash
python embed_articles.py code_penal_structure_docx.json --query "quelles peines pour diffamation ?" --top-k 5
```

---

## 🔄 Changer de modèle d'embeddings

La couche modèle est isolée dans `embeddings/`. `embed_articles.py` ne connaît que
l'interface `BaseEmbedder` (lots, retries, normalisation, dimensions) : changer de
fournisseur ou de modèle ne touche ni le cache, ni le graphe, ni la recherche.

| Fournisseur | `EMBEDDING_PROVIDER` | Variables principales |
|---|---|---|
| Google Gemini | `gemini` (défaut) | `GEMINI_API_KEY`, `EMBEDDING_MODEL`, `EMBEDDING_DIM` |
| OpenRouter | `openrouter` | `OPENROUTER_API_KEY`, `EMBEDDING_MODEL`, `EMBEDDING_DIM` |
| Ollama | `openai` | `EMBEDDING_BASE_URL=http://localhost:11434/v1`, `EMBEDDING_MODEL`, `EMBEDDING_DIM` |
| vLLM / LM Studio / llama.cpp | `openai` | `EMBEDDING_BASE_URL`, `EMBEDDING_MODEL`, `EMBEDDING_DIM` |
| OpenAI / Mistral | `openai` | `EMBEDDING_BASE_URL`, `EMBEDDING_MODEL`, `EMBEDDING_DIM`, `OPENAI_API_KEY` |

Exemple avec Ollama, sans clé API :

```bash
ollama pull nomic-embed-text
python embed_articles.py code_penal_structure_docx.json \
    --provider openai --model nomic-embed-text \
    --base-url http://localhost:11434/v1 --dim 768
```

Exemple avec OpenRouter (clé sur https://openrouter.ai/keys) :

```bash
export OPENROUTER_API_KEY=sk-or-v1-...
python embed_articles.py code_penal_structure_docx.json \
    --provider openrouter --model openai/text-embedding-3-small --dim 1536
```

Modèles d'embeddings utiles sur OpenRouter — attention, le catalogue des embeddings
est distinct de `/models` et se consulte via
`GET https://openrouter.ai/api/v1/embeddings/models` :

| Modèle | Dimensions | Remarque |
|---|---|---|
| `openai/text-embedding-3-small` | 1536 | défaut, bon rapport qualité/prix |
| `baai/bge-m3` | 1024 | multilingue, open weights |
| `qwen/qwen3-embedding-8b` | 4096 | multilingue, contexte 32k |
| `voyageai/voyage-4` | 1024 | contexte 32k |
| `nvidia/nemotron-3.5-embed-1b:free` | 2048 | **gratuit**, validé par lots de 20 |
| `nvidia/nemotron-3.5-embed-8b:free` | 4096 | **gratuit**, mais le fournisseur n'accepte que des lots de 1 |

Deux options OpenRouter sont désactivées par défaut, car tous les modèles ne les
acceptent pas :

- `OPENROUTER_DIMENSIONS=1` : envoie `dimensions` pour réduire la taille des vecteurs
  (par exemple `--dim 768` avec `text-embedding-3-small`) ;
- `OPENROUTER_INPUT_TYPE=1` : envoie `search_document` / `search_query` aux modèles
  de retrieval.

`OPENROUTER_SITE_URL` et `OPENROUTER_APP_NAME` alimentent les en-têtes recommandés
`HTTP-Referer` / `X-Title`.

Les mêmes options existent en variables d'environnement (`EMBEDDING_PROVIDER`,
`EMBEDDING_MODEL`, `EMBEDDING_DIM`, `EMBEDDING_BASE_URL`, `EMBEDDING_BATCH_SIZE`,
`NEO4J_VECTOR_INDEX`, `OPENROUTER_API_KEY`, `OPENROUTER_DIMENSIONS`,
`OPENROUTER_INPUT_TYPE`).

**Cache** : `embeddings_cache.json` est indexé par `(provider, modèle, dimension, texte)`.
Changer de modèle recalcule automatiquement les vecteurs ; revenir à l'ancien modèle
réutilise ses vecteurs. En cas de changement de dimension, l'index Neo4j existant est
détecté comme incompatible et le script indique de le supprimer :

```cypher
DROP INDEX article_embedding
```

### Ajouter un nouveau fournisseur

1. Créer `embeddings/mon_fournisseur.py` avec une sous-classe de `BaseEmbedder`
   définissant `name`, `default_model`, `default_dim`, `max_chars` et
   `_embed_batch(texts, kind)` (lever `EmbeddingError(..., transient=True/False)`).
2. L'enregistrer dans `PROVIDERS` (`embeddings/__init__.py`).

Le découpage en lots, le backoff exponentiel, la validation des dimensions et la
normalisation L2 sont déjà pris en charge par la classe de base.

```python
from embeddings.base import BaseEmbedder, EmbeddingError

class MonEmbedder(BaseEmbedder):
    name = "mon-modele"
    default_model = "mon-modele-v1"
    default_dim = 1024

    def _embed_batch(self, texts, kind):
        try:
            return mon_api.embed(self.model, texts)   # liste de listes de floats
        except MonApiErreur as exc:
            raise EmbeddingError(str(exc), transient=exc.retryable) from exc
```
