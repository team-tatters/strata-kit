# Standard des skills

Un skill de strata-kit est un flux de travail qu'un agent suit, et non une référence qu'il survole. Le schéma de `core/schemas/skill.schema.yaml` fixe la forme ; cette page explique pourquoi chaque partie existe et comment l'écrire.

## Forme

```text
skills/<name>/
├── SKILL.md            English canonical: frontmatter + yaml block + six sections
├── i18n/ko.md …        localized bodies, same section order
├── evals/              pressure scenarios and results (RED / GREEN / REFACTOR)
├── references/         long material the body links to
└── scripts/            bundled tools, run through their interpreter
```

## Frontmatter

`name` est l'identifiant à plat que le harnais fait correspondre. Les skills du noyau sont `strata.<verb>` ; le skill d'entrée est `using-strata`.

`description` est la seule chose qu'un agent voit avant de décider d'ouvrir le skill. Elle commence par « Use when », puis liste des situations, des symptômes et des mots-clés. Elle ne résume jamais le flux de travail : un agent qui lit un résumé suit le résumé au lieu du corps, et c'est dans le corps que se trouvent les points de contrôle.

## Le bloc yaml

Juste après le H1 vient un bloc `yaml` délimité contenant `id`, `version`, `owner`, `triggers`, `inputs`, `outputs`, `required_context`, `allowed_tools`, `validation`, `failure_modes`. C'est le jumeau lisible par machine de la prose, et le générateur le lit pour construire les adaptateurs et le registre. `validation` correspond un à un à la section Vérification.

## Les six sections

1. **Aperçu** : un paragraphe, ce que ce skill produit.
2. **Quand l'utiliser** : les déclencheurs et les non-déclencheurs explicites.
3. **Procédure** : des étapes numérotées. Chaque étape nomme un point de contrôle et la preuve qu'elle laisse (un fichier, la sortie d'une commande, un id d'enregistrement).
4. **Rationalisations** : les excuses qu'un agent utilise pour sauter une étape (« ce n'est qu'un petit changement », « je me souviens de la règle »), chacune avec une réfutation. Les agents prennent par défaut le chemin le plus court ; cette section est le contrepoids.
5. **Signaux d'alerte** : des signes observables que le skill est sauté ou mal appliqué, écrits de façon qu'un relecteur ou une porte puisse les détecter.
6. **Vérification** : ce qui doit être vrai, et quelle preuve l'établit, avant que le skill puisse rapporter l'achèvement. « Cela semble correct » n'est jamais une preuve.

## Écrire pour l'agent

- Des interdictions pour les étapes que les agents sautent sciemment. Des modèles avec emplacements obligatoires pour les omissions. Des conditionnelles pour les comportements qui dépendent d'une condition.
- Pas de clauses nuancées. « Ne faites pas X sauf si c'est important » rouvre la négociation ; écrivez les vraies exceptions comme des conditionnelles distinctes.
- Gardez `SKILL.md` sous 300 lignes. Les longues références vont dans `references/` et sont liées, de sorte que le skill coûte peu de tokens tant qu'il n'est pas nécessaire.
- Un exemple complet et exécutable vaut mieux que trois exemples partiels.

## Tester un skill

Écrire un skill, c'est du développement piloté par les tests appliqué au processus. Exécutez les scénarios de `evals/` avec un sous-agent qui n'a pas le skill et consignez ce qu'il a sauté et comment il l'a justifié (RED). Écrivez le skill minimal qui répond à ces échecs et relancez (GREEN). Fermez les échappatoires qu'il a trouvées et relancez une dernière fois (REFACTOR). Conservez le scénario, le résumé de la transcription et le verdict dans `evals/`. Un skill sans exécution RED consignée est un brouillon.

## Localisation

Ne traduisez que le corps. Le bloc yaml, le frontmatter et tous les identifiants restent en anglais. `en` et `ko` sont requis avant que le skill soit `active` ; les quatre autres locales retombent sur l'anglais avec un avertissement (voir `LOCALES.md`).
