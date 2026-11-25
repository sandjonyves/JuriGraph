# Rapport — Lot 3 : prompt d'extraction V5

## 1. Fichiers créés

| Fichier | Rôle |
|---|---|
| `prompts/extraction_v5.md` | Prompt d'extraction aligné sur `FicheV5` et sur les décisions de la spécification V5. |
| `tests/test_prompt_v5.py` | 9 tests hors ligne de conformité du prompt au schéma et aux cas critiques. |

Aucun prompt V1–V4, aucun JSON d'extraction, aucun fichier du corpus et aucun
cache n'a été modifié.

## 2. Règles ajoutées dans le prompt

- Sortie JSON unique, sans Markdown ni commentaire, avec tous les champs racine
  de `FicheV5`.
- Interdiction d'inventer un article, une peine, un quantum, une condition ou
  une citation ; les formules et renvois ne sont jamais convertis en montants
  fixes.
- Arbre de décision explicite pour `type_article` : `definit_infraction`,
  `regle_generale`, `regime_peines`, `mixte`, `sans_objet`, `indetermine`.
- Règles de granularité : une infraction par fait punissable autonome ; les
  anaphores (« ce concert », « cette infraction ») ne créent pas de nouvelle
  infraction ; les clauses qui ne changent que la peine deviennent des
  conditions.
- Registres séparés : `conditions`, `groupes_conditions`, `groupes_peines`,
  `renvois`, `incertitudes`.
- Règles de sources : citation exacte, `Source.article` égal à l'article
  courant, alinéa exact ou `null`, offsets laissés à `null`, interdiction de
  citer le texte de l'article cible.
- Règles de peines : catégories et natures autorisées, `objet` obligatoire pour
  confiscation/retrait/suspension/déchéance, `sous_type` obligatoire pour
  `autre`, quantum en fourchette/minimum/maximum/perpétuité/formule.
- Règles de groupes de peines : `alternative`, `cumulative`,
  `cumul_ou_alternative`, `echelle_conditionnelle`, avec rattachement à
  l'infraction ou à la règle.
- Règles de conditions : `commune` utilisée au moins deux fois, `propre`
  utilisée une seule fois, `generale` rattachée à une règle, `interpretative`
  non rattachée à une peine.
- Règles de renvois : cible `article` pour un numéro explicite, cible `libelle`
  de statut `textuelle` pour « faux témoin » ou « mêmes peines », `non_resolue`
  réservé aux cibles internes réellement introuvables.
- Règles de régime : les articles 17, 18, 18-1, 19 et 21 ne produisent jamais
  d'infraction ; leur contenu est conservé dans `DispositionRegime`.
- Règles d'incertitude : toute ambiguïté réelle est signalée, sans masquer un
  champ obligatoire manquant.
- Cas critiques documentés : `124`, `158`, `289`, `347`, `135-2`, `226`,
  `164`, `17`, `18`, `18-1`, `19`, `21`.
- Exemple complet validé pour l'article 226 (amende principale, confiscation
  accessoire explicite, groupe cumulatif).

## 3. Compatibilité avec le schéma V5

Les tests vérifient automatiquement :

- la présence de **tous les champs** de `FicheV5`, `Source`, `Mesure`,
  `FormulePeine`, `QuantumPeine`, `Peine`, `ElementConstitutif`, `Infraction`,
  `Condition`, `GroupeConditions`, `GroupePeines`, `EffetRegle`,
  `RegleGenerale`, `Cible`, `Renvoi`, `DispositionRegime` et `Incertitude` ;
- la présence de **toutes les valeurs** des énumérations V5
  (`type_article`, statuts, natures, catégories, modes de quantum, types de
  renvoi, types d'effet, etc.) ;
- la validité structurelle du gabarit racine et de l'exemple 226 avec
  `FicheV5.model_validate` ;
- l'absence des champs V4 obsolètes (`peines_au_choix`, `quantum_min`,
  `quantum_max`, `unite_min`, `unite_max`, `peines_renvoi`) ;
- la présence des cas critiques et des règles de non-régression.

## 4. Vérifications exécutées

### Tests du prompt V5

```text
$ env/bin/python -m unittest tests.test_prompt_v5 -v
...
Ran 9 tests in 0.016s

OK
```

### Tous les tests hors ligne

```text
$ env/bin/python -m unittest discover -s tests
...
Ran 192 tests in 6.491s

OK (expected failures=10)
```

Les 10 échecs attendus sont ceux déjà présents dans le dépôt. Les tests qui
démarrent un faux serveur HTTP local ont été exécutés ; aucun appel réseau réel
et aucune connexion Neo4j n'ont été effectués.

### Ruff

```text
$ env/bin/ruff check --select E9,F .
All checks passed!

$ env/bin/ruff check tests/test_prompt_v5.py
All checks passed!
```

## 5. Points restant à valider

- Le prompt V5 n'est **pas encore branché** dans `extract_infractions.py` :
  l'extraction réelle utilise toujours `extraction_v4.md`. Le câblage et la
  validation d'une sortie réelle relèvent d'un lot ultérieur.
- Aucune extraction réelle, aucun appel LLM et aucune connexion Neo4j n'ont été
  lancés, conformément à la consigne.
- La lecture de référence de `158` est la `RegleGenerale`, conformément à la
  spécification V5. La variante « infraction par renvoi » reste mentionnée dans
  les documents de conception mais n'est pas imposée par le prompt.
- Pour `289`, le prompt autorise deux peines accessoires (lecture de référence)
  ou une peine avec deux durées ; le point important est la condition commune.
  Une relecture humaine devra fixer la granularité retenue.
- Pour `164`, le prompt impose la conservation du renvoi textuel « faux témoin »
  en statut `textuelle`. La résolution éventuelle vers une infraction précise
  reste une décision de relecture, pas une obligation du schéma.
- Les tests vérifient la conformité de forme et de structure, pas la qualité
  juridique finale. Toute extraction réelle devra passer par le vérificateur et
  une relecture humaine.

## 6. État Git

- Branche : `etape-3-prompt-v5`.
- Fichiers du lot : `prompts/extraction_v5.md`, `tests/test_prompt_v5.py`,
  `docs/RAPPORT_LOT_3_PROMPT_V5.md`.
- Les modifications préexistantes (`verify_extraction.py`,
  `tests/test_verify_extraction.py`, `data/`, `AGENTS.md`,
  `docs/SCHEMA_EXTRACTION_V5_PROPOSITION.md`, `tests/test_audit_v4.py`) ne sont
  pas incluses dans le commit du Lot 3.

## 7. Conclusion

✅ Lot 3 terminé : le prompt V5 est créé, testé hors ligne et aligné sur les
champs, énumérations et cas critiques du schéma V5.

⏸️ Lot 4 non commencé, conformément à la consigne.
