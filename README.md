# JuriGraph ⚖️🔗

**JuriGraph** est un pipeline d'ingestion, de modélisation en graphe de connaissances et de recherche sémantique (Legal Graph-RAG) appliqué au **Code pénal camerounais (Loi n° 2016/007)**.

Il combine la puissance d'une base orientée graphe (**Neo4j**) et des modèles d'embeddings de Google (**Gemini API**) pour permettre des recherches à la fois hiérarchiques, lexicales et vectorielles.

---

## 🚀 Fonctionnalités

1. **Extraction structurée** : Parsing de documents légaux `.docx` (via Pandoc) vers une structure JSON hiérarchique :
   $$\text{Code} \rightarrow \text{Livres} \rightarrow \text{Titres} \rightarrow \text{Chapitres} \rightarrow \text{Sections} \rightarrow \text{Articles} \rightarrow \text{Alinéas}$$
2. **Graphe de connaissances Neo4j** :
   - Relations hiérarchiques ordonnées : `(:Parent)-[:CONTIENT {ordre: n}]->(:Enfant)`
   - Relations croisées de renvois juridiques : `(:Article)-[:RENVOIE_A]->(:Article)`
   - Index plein texte (Fulltext search) sur le titre et le contenu des articles.
3. **Recherche sémantique vectorielle (Gemini Embeddings)** :
   - Calcul des vecteurs avec contexte légal (Livre, Titre, Chapitre).
   - Indexation vectorielle native dans Neo4j (dimension 768, similarité cosinus).
   - Requêtes en langage naturel (ex. *"Quelles sont les peines pour blessures volontaires ?"*).

---

## 📂 Structure du Projet

```text
├── parse_code_penal_docx.py       # Extraction du DOCX vers structure JSON
├── code_penal_structure_docx.json # Structure complète extraite
├── load_neo4j.py                  # Chargement de la hiérarchie dans Neo4j
├── extract_renvois.py             # Détection et création des relations de renvois
├── embed_articles.py              # Calcul d'embeddings Gemini & index vectoriel
├── renvois.json                   # Renvois extraits entre articles
├── neo4j-2026-10-23T02-35-31.dump # Dump de sauvegarde de la base Neo4j
├── requirements.txt               # Dépendances Python
├── .env.example                   # Modèle de variables d'environnement
└── .gitignore                     # Exclusion des fichiers sensibles et temporaires
```

---

## 🛠️ Installation & Configuration

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
```

### Étape 4 : Effectuer une recherche en langage naturel
```bash
python embed_articles.py code_penal_structure_docx.json --query "quelles peines pour diffamation ?"
```
