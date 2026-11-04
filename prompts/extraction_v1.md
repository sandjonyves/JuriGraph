# Extraction d'une fiche Infraction / Peine — prompt v1

Tu extrais une fiche structurée à partir du texte **exact** d'un article du Code
pénal camerounais. Tu ne complètes jamais le texte avec tes connaissances.

## Règles

1. **Citation verbatim obligatoire** : chaque `citation` doit être une
   sous-chaîne exacte du texte fourni, accents et ponctuation compris.
2. **Interdiction d'inventer** : aucun numéro d'article, quantum, unité ou
   citation ne doit venir d'ailleurs que du texte fourni.
3. Si une information est absente ou incertaine, mets `null` pour un quantum et
   `[]` pour une liste. Ne devine pas.
4. **Unité recopiée telle qu'écrite** : si le texte dit « francs », mets
   `francs` dans `unite_min` et `unite_max`. N'écris jamais `FCFA` et ne
   convertis aucune unité.
5. Les nombres doivent apparaître dans la citation de la peine. `quantum_min`
   et `quantum_max` sont des nombres, sans espaces.
6. `peines_renvoi` sert uniquement quand le texte dit « puni des peines de
   l'article X » (ou une formule équivalente) : mets le numéro X, ou la
   référence complète avec l'alinéa si le texte la donne (ex. `164 (2)`).
7. `renvois` contient les numéros d'articles cités dans le texte, même lorsqu'il
   ne s'agit pas de peines.
8. Si l'article ne définit aucune infraction (définition, système des peines,
   article de renvoi), renvoie `"infractions": []`.
9. Réponds **uniquement** avec le JSON, sans balises Markdown ni commentaire.
10. **Granularité** : une `Infraction` par alinéa ou clause « Est puni de… » qui
    décrit des faits et leur peine. Les actes énumérés (a), b) ou 1., 2.) d'une
    même clause deviennent des éléments constitutifs de cette infraction, pas des
    infractions séparées. Une clause qui ne fait que modifier la peine (ex.
    « En temps de guerre, la peine est celle de mort ») ajoute une peine à la
    même infraction. Un alinéa purement interprétatif (ex. assimilation à l'état
    de guerre) va dans `conditions`, sans créer d'infraction.
11. **Condition de peine** : le champ `condition` d'une peine contient le passage
    exact du texte qui précise quand cette peine s'applique (ex. « En temps de
    guerre, d'état d'urgence ou d'exception »), ou `null` s'il n'y en a pas. Ce
    passage doit être une sous-chaîne exacte du texte fourni.
12. **Unités séparées** : une fourchette peut avoir deux unités différentes
    (ex. 3 mois à 3 ans) : renseigne `unite_min` et `unite_max` séparément, avec
    la même valeur si l'unité est commune. Ne laisse JAMAIS un quantum à `null`
    quand le texte le donne.
13. **Type de peine** : mort, emprisonnement et amende sont des peines
    PRINCIPALES (article 18). Le type `alternative` est réservé au travail
    d'intérêt général et à la sanction-réparation (article 18-1). Les peines
    accessoires sont celles de l'article 19.
14. **Peines d'autres articles** : une phrase qui précise ou modifie les peines
    d'AUTRES articles va dans `conditions`/`renvois`, jamais dans `peines`.
15. **Peines au choix** : `peines_au_choix` vaut `true` si le texte dit « ou de
    l'une de ces deux peines seulement » ou une formule équivalente ; sinon
    `false`.
16. **Circonstance de peine** : une circonstance qui ne change que la peine va
    dans `Peine.condition`, pas dans les éléments constitutifs ; elle est élément
    constitutif seulement si l'infraction n'existe pas sans elle (ex. en temps de
    guerre pour l'article 108).
17. **Choix entre éléments** : quand le texte énumère des actes a), b)… séparés
    par « ; » ou « ou », donne-leur le même `choix` (entier non nul). Des éléments
    avec le même entier sont des alternatives (l'un OU l'autre suffit) ; `null`
    = élément obligatoire.

## Format de sortie

```json
{
  "article": "<numéro>",
  "infractions": [
    {
      "libelle": "<libellé>",
      "elements_constitutifs": [
        {
          "type": "legal|materiel|moral",
          "texte": "<description>",
          "citation": "<extrait exact>",
          "choix": null
        }
      ],
      "peines": [
        {
          "type": "principale|alternative|accessoire",
          "nature": "emprisonnement|amende|mort|travail_interet_general|autre",
          "quantum_min": null,
          "quantum_max": null,
          "unite_min": "ans|mois|jours|francs|null",
          "unite_max": "ans|mois|jours|francs|null",
          "perpetuite": false,
          "condition": null,
          "citation": "<extrait exact>"
        }
      ],
      "peines_renvoi": ["<numéro>"],
      "peines_au_choix": false
    }
  ],
  "conditions": ["<condition>"],
  "renvois": ["<numéro>"]
}
```
