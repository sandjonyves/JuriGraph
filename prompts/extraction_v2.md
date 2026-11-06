# Extraction d'une fiche Infraction / Peine — prompt v2

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
6. `peines_renvoi` ne contient QUE des numéros d'articles écrits dans le texte.
   Si le texte dit seulement « puni comme faux témoin », « mêmes peines » ou une
   formule équivalente sans numéro d'article, laisse `peines` et `peines_renvoi`
   vides et mets la phrase exacte dans `conditions`.
7. `renvois` contient les numéros d'articles cités dans le texte, même lorsqu'il
   ne s'agit pas de peines.
8. Si l'article ne définit aucune infraction (définition, système des peines,
   article de renvoi), renvoie `"infractions": []` et laisse `"conditions": []`.
9. Réponds **uniquement** avec le JSON, sans balises Markdown ni commentaire.
10. **Granularité** : une `Infraction` par alinéa ou clause « Est puni de… » qui
    décrit des faits et leur peine. Les actes énumérés (a), b) ou 1., 2.) d'une
    même clause deviennent des éléments constitutifs de cette infraction, pas des
    infractions séparées. Une clause qui fixe EXPLICITEMENT une peine (nature,
    durée ou montant) pour un cas particulier devient une `Peine` de
    l'infraction, avec `condition` = le passage exact qui décrit le cas, même si
    ce cas est défini par renvoi à d'autres articles. `conditions` est réservé
    aux clauses qui ne fixent aucune peine explicite (doublement, conversion,
    assimilation). Un alinéa purement interprétatif (ex. assimilation à l'état
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
14. **Peines d'autres articles** : une phrase qui se borne à renvoyer aux peines
    d'AUTRES articles sans en fixer explicitement la nature, la durée ou le
    montant va dans `conditions`/`renvois`, jamais dans `peines`. Si elle fixe
    explicitement une peine pour un cas défini par renvoi, applique la règle 10 :
    cette peine va dans `peines` avec `condition`.
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

## Exemples few-shot

### Article 174 — Requis défaillant

```json
{
  "article": "174",
  "infractions": [
    {
      "libelle": "Refus de prêter concours à l'autorité judiciaire",
      "elements_constitutifs": [
        {
          "type": "legal",
          "texte": "Personne régulièrement requise comme expert, médecin ou interprète",
          "citation": "étant régulièrement requis comme expert, médecin ou interprète"
        },
        {
          "type": "materiel",
          "texte": "Refus sans motif légitime de prêter son concours à l'autorité judiciaire",
          "citation": "refuse sans motif légitime de prêter son concours à l'autorité judiciaire"
        }
      ],
      "peines": [
        {
          "type": "principale",
          "nature": "amende",
          "quantum_min": 20000,
          "quantum_max": 500000,
          "unite_min": "francs",
          "unite_max": "francs",
          "perpetuite": false,
          "condition": null,
          "citation": "une amende de vingt mille (20 000) à cinq cent mille (500 000) francs"
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

### Article 113 — Propagation de fausses nouvelles

```json
{
  "article": "113",
  "infractions": [
    {
      "libelle": "Propagation de fausses nouvelles",
      "elements_constitutifs": [
        {
          "type": "materiel",
          "texte": "Émission ou propagation de nouvelles mensongères",
          "citation": "émet ou propage des nouvelles mensongères"
        },
        {
          "type": "legal",
          "texte": "Nouvelles susceptibles de nuire aux autorités publiques ou à la cohésion nationale",
          "citation": "lorsque ces nouvelles sont susceptibles de nuire aux autorités publiques ou à la cohésion nationale"
        }
      ],
      "peines": [
        {
          "type": "principale",
          "nature": "emprisonnement",
          "quantum_min": 3,
          "quantum_max": 3,
          "unite_min": "mois",
          "unite_max": "ans",
          "perpetuite": false,
          "condition": null,
          "citation": "un emprisonnement de trois (03) mois à trois (03) ans"
        },
        {
          "type": "principale",
          "nature": "amende",
          "quantum_min": 100000,
          "quantum_max": 2000000,
          "unite_min": "francs",
          "unite_max": "francs",
          "perpetuite": false,
          "condition": null,
          "citation": "une amende de cent mille (100 000) à deux millions (2 000 000) de francs"
        }
      ],
      "peines_renvoi": [],
      "peines_au_choix": false
    }
  ],
  "conditions": [
    "En cas de réduction de la peine prévue aux articles 111 (2) et 112 ci-dessus, la peine privative est celle de l'emprisonnement."
  ],
  "renvois": [
    "111",
    "112"
  ]
}
```

### Article 111 — Sécession

```json
{
  "article": "111",
  "infractions": [
    {
      "libelle": "Atteinte à l'intégrité du territoire",
      "elements_constitutifs": [
        {
          "type": "materiel",
          "texte": "Entreprendre par quelque moyen que ce soit de porter atteinte à l'intégrité du territoire",
          "citation": "entreprend par quelque moyen que ce soit de porter atteinte à l'intégrité du territoire"
        }
      ],
      "peines": [
        {
          "type": "principale",
          "nature": "emprisonnement",
          "quantum_min": null,
          "quantum_max": null,
          "unite_min": null,
          "unite_max": null,
          "perpetuite": true,
          "condition": "en temps de paix",
          "citation": "Est puni de l'emprisonnement à vie"
        },
        {
          "type": "principale",
          "nature": "mort",
          "quantum_min": null,
          "quantum_max": null,
          "unite_min": null,
          "unite_max": null,
          "perpetuite": false,
          "condition": "En temps de guerre, d'état d'urgence ou d'exception",
          "citation": "En temps de guerre, d'état d'urgence ou d'exception, la peine est celle de mort."
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

### Article 165 — Fausse expertise

```json
{
  "article": "165",
  "infractions": [
    {
      "libelle": "Fausse expertise",
      "elements_constitutifs": [
        {
          "type": "legal",
          "texte": "Expert judiciaire",
          "citation": "l'expert judiciaire"
        },
        {
          "type": "materiel",
          "texte": "Dépose un faux rapport devenu irrévocable",
          "citation": "dépose un faux rapport devenu irrévocable"
        }
      ],
      "peines": [],
      "peines_renvoi": [
        "164 (2)"
      ],
      "peines_au_choix": false
    }
  ],
  "conditions": [],
  "renvois": [
    "164"
  ]
}
```

### Article 108 — Temps de guerre

```json
{
  "article": "108",
  "infractions": [
    {
      "libelle": "Relations avec une puissance ennemie",
      "elements_constitutifs": [
        {
          "type": "legal",
          "texte": "Tout citoyen ou tout résident",
          "citation": "tout citoyen ou tout résident"
        },
        {
          "type": "legal",
          "texte": "En temps de guerre et sans l'autorisation de l'autorité compétente",
          "citation": "en temps de guerre et sans l'autorisation de l'autorité compétente"
        },
        {
          "type": "materiel",
          "texte": "Entretient une correspondance ou des relations avec les sujets ou les agents d'une puissance ennemie",
          "citation": "entretient une correspondance ou des relations avec les sujets ou les agents d'une puissance ennemie",
          "choix": 1
        },
        {
          "type": "materiel",
          "texte": "Fait, même indirectement, un acte de commerce avec un sujet ou un agent d'une puissance ennemie ou avec une personne résident sur son territoire",
          "citation": "fait, même indirectement, un acte de commerce avec un sujet ou un agent d'une puissance ennemie ou avec une personne résident sur son territoire",
          "choix": 1
        }
      ],
      "peines": [
        {
          "type": "principale",
          "nature": "emprisonnement",
          "quantum_min": 10,
          "quantum_max": 20,
          "unite_min": "ans",
          "unite_max": "ans",
          "perpetuite": false,
          "condition": null,
          "citation": "un emprisonnement de dix (10) à vingt (20) ans"
        }
      ],
      "peines_renvoi": [],
      "peines_au_choix": false
    },
    {
      "libelle": "Démoralisation de l'armée ou de la nation",
      "elements_constitutifs": [
        {
          "type": "legal",
          "texte": "Celui qui, en temps de guerre",
          "citation": "celui qui, en temps de guerre"
        },
        {
          "type": "materiel",
          "texte": "Participe à une entreprise de démoralisation de l'armée ou de la nation ayant pour objet de nuire à la défense nationale",
          "citation": "participe à une entreprise de démoralisation de l'armée ou de la nation ayant pour objet de nuire à la défense nationale",
          "choix": 1
        },
        {
          "type": "materiel",
          "texte": "Commet une des infractions visées aux articles 105, 106 et 107 ci-dessus",
          "citation": "commet une des infractions visées aux articles 105, 106 et 107 ci-dessus",
          "choix": 1
        }
      ],
      "peines": [
        {
          "type": "principale",
          "nature": "emprisonnement",
          "quantum_min": 10,
          "quantum_max": 20,
          "unite_min": "ans",
          "unite_max": "ans",
          "perpetuite": false,
          "condition": null,
          "citation": "un emprisonnement de dix (10) à vingt (20) ans"
        }
      ],
      "peines_renvoi": [],
      "peines_au_choix": false
    },
    {
      "libelle": "Acte de nature à nuire à la défense nationale",
      "elements_constitutifs": [
        {
          "type": "legal",
          "texte": "Celui qui, en temps de guerre",
          "citation": "celui qui, en temps de guerre"
        },
        {
          "type": "materiel",
          "texte": "Commet un acte quelconque de nature à nuire à la défense nationale et non autrement puni",
          "citation": "commet un acte quelconque de nature à nuire à la défense nationale et non autrement puni"
        }
      ],
      "peines": [
        {
          "type": "principale",
          "nature": "emprisonnement",
          "quantum_min": 1,
          "quantum_max": 5,
          "unite_min": "ans",
          "unite_max": "ans",
          "perpetuite": false,
          "condition": null,
          "citation": "un emprisonnement de un (01) à cinq (05) ans"
        },
        {
          "type": "principale",
          "nature": "amende",
          "quantum_min": 50000,
          "quantum_max": 5000000,
          "unite_min": "francs",
          "unite_max": "francs",
          "perpetuite": false,
          "condition": null,
          "citation": "une amende de cinquante (50 000) mille à cinq millions (5 000 000) de francs"
        }
      ],
      "peines_renvoi": [],
      "peines_au_choix": true
    }
  ],
  "conditions": [
    "Pour l'application des alinéas 2 et 3 ci-dessus, sont assimilés au temps de guerre l'état d'urgence et l'état d'exception."
  ],
  "renvois": [
    "105",
    "106",
    "107"
  ]
}
```
