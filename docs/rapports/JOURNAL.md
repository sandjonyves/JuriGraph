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

### À relire par l'utilisateur
- (rien pour l'étape 5)
