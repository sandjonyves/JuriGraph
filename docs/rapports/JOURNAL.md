# Journal de bord — JuriGraph

Notes datées : ce qui est fait, chiffres, difficultés, et **ce que l'utilisateur doit relire**.

## 2026-11-28

### Décisions de l'utilisateur
- Modèle LLM retenu : `deepseek/deepseek-v4.1-flash` via OpenRouter (crédits à acheter).
- Relecture humaine faite par l'utilisateur (éviter le biais circulaire).
- Autorisation d'enchaîner étape 5 → étape 8, push après chaque tâche, jamais de fusion dans `main`.
- Les scénarios d'évaluation sont rédigés en brouillon par Claude ; résultats « provisoires » jusqu'à relecture.

### Git
- Modifications V4 de `verify_extraction.py` et de ses tests committées sur `etape-3-prompt-v5` (`8825945`).
- `main` ne contient pas les étapes 0–3 : `etape-5-graphe` est créée depuis `etape-3-prompt-v5`.
  **Fusionner dans l'ordre** : etape-0 → 1 → 2 → 3 → 5 → 8.

### Étape 5 — terminée
- Renvois en base : 271/271, identiques à `renvois.json`. Index plein texte : déjà en `french`.
- Aucune écriture dans Neo4j n'a été nécessaire. Rapport : `docs/rapports/R2_etape5_graphe.md`.

### Étape 8 — terminée (résultats PROVISOIRES)
- 45 scénarios en brouillon (`data/eval/faits_articles.jsonl`), recouvrement lexical médian 0,09.
- `search_hybrid.py` (V, PT, renvois, voisins, RRF pondérée) et `evaluate_search.py` (11 ablations,
  réglage sur dev, bootstrap, permutation).
- Résultat : **la voie vectorielle seule est la meilleure** (test : R@10 = 0,857, 18/21 ; MRR = 0,648).
  Plein texte et graphe n'apportent rien de significatif ; à poids égal ils dégradent le classement.
- Le test a été consulté une fois avant la 2ᵉ itération (documenté dans R4 § 2.3).
- Échecs typiques : article 318 (3 infractions dans un seul vecteur), tentative/complicité (0/2).
- Rapport : `docs/rapports/R4_etape8_recherche.md`. Coût : 0 $.

### À relire par l'utilisateur
1. **Les 45 scénarios** : `data/eval/grille_relecture_scenarios.csv` (garder / modifier / rejeter,
   articles attendus corrigés). Indispensable avant de citer les chiffres de R4.
2. Le rapport R4, en particulier les décisions du § 6 (V seule par défaut, graphe pour enrichir).

### Export Excel des statistiques
- `scripts/exporter_statistiques.py` → `data/reports/statistiques_jurigraph.xlsx` : 8 feuilles
  (ablations, réglage, scénarios filtrables, catégories, recouvrement, corpus, essais), graphiques
  Excel natifs, 75 formules recalculées sans erreur et contrôlées contre Python.
- Nouvelle dépendance : `openpyxl` (ajoutée à `requirements.txt`).
- Régénérer après chaque évaluation : `python scripts/exporter_statistiques.py`.

### En attente (hors étapes 5 et 8)
- Crédits OpenRouter + `LLM_PROVIDER` / `LLM_MODEL` dans `.env` pour l'extraction avec DeepSeek V4.1 Flash.
- Date de dépôt du mémoire.
