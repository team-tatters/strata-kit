# Niveau de vérification (Verification Tier)

> Canonique : strata-kit `core/docs/fr/methodology/verification-tier.md` (migré le 2026-10-29 depuis strata `docs/04-agents/verification-tier.md`, DEC-2026-10-29-11).

> Un axe d'indépendance de la vérification, orthogonal au mode d'exécution (Verbal/Task).
> Le mode d'exécution porte sur *la façon de travailler* ; le niveau de vérification définit *qui vérifie le résultat*.
> Ce document est la source of truth de l'enum `verification_tier`.

## Définitions des Tier

| Tier | valeur de l'enum | Définition | Indépendance de la vérification |
|------|------------------|------------|---------------------------------|
| **Solo** | `solo` | Celui qui a exécuté vérifie avec sa propre liste de contrôle | Aucune |
| **Self-Verified** | `self_verified` | Un Reviewer indépendant au sein du même environnement d'exécution/de la même famille d'outils vérifie | Moyenne |
| **Cross-Verified** | `cross_verified` | Un Reviewer d'un autre environnement d'exécution, d'une autre famille d'outils ou d'une autre famille de modèles vérifie | Élevée |

- Les noms d'outils ne sont pas écrits dans Core. Les correspondances du type « exécuté par X → vérifié par Y » vont dans l'adaptateur de chaque outil (AGENTS.md, settings).
- Le Reviewer ne voit pas toute la conversation, mais seulement **la demande + le diff + les règles + les résultats des tests + la liste de contrôle**.
- Le nom affiché est `Cross-Verified` ; la valeur de l'enum écrite dans `_order.yaml` est `cross_verified`.

## Valeurs par défaut et plage obligatoire

```text
Verbal Mode : si verification_tier est omis → solo
Task Mode :   il est recommandé d'indiquer verification_tier dans _order.yaml
Modifications d'une source de vérité de Core (layer-rules / naming-convention / task-spec-schema / agent-roles) :
              → cross_verified obligatoire
Autres modifications de documents et d'adaptateurs de Core (core/docs/, core/templates/, etc.) :
              → cross_verified recommandé
```

On ne fait pas déclarer un Tier pour chaque petite modification. Si le coût de la déclaration dépasse le bénéfice de la vérification, Strata devient lourd.

## Patterns d'implémentation

Le TDD Writer/Reviewer (`core/docs/fr/methodology/session-splitting.md` §2.4) est l'un des patterns d'implémentation du Tier Self/Cross-Verified.
Le document session-splitting traite de la façon de découper les sessions ; ce document porte le sens de l'indépendance de la vérification et l'enum.

L'implémentation outillée concrète de Cross-Verified est couverte par `skills/strata.review/SKILL.md`.
Ce skill est la procédure qui exécute réellement le `cross_verified` de ce document ; ce document ne définit pas la procédure.

## Relation avec les autres axes

- **Execution Mode** : le choix et le changement entre Verbal/Task sont définis par `core/docs/fr/methodology/execution-modes.md`.
- **Agent Operations** : le `reviewer: cross_verified` du Decision Inbox utilise ce Tier. La discipline d'exploitation est définie par `core/docs/fr/methodology/agent-operations.md`.
- **Methodology Feedback Loop** : les lacunes méthodologiques repérées par un Reviewer sont consignées dans le backlog et promues selon le flux de la Promotion Gate de `core/docs/fr/methodology/task-spec-schema.md`.

## Axe de vérification du design (design_verified)

Le troisième axe, orthogonal au mode d'exécution et au niveau de vérification. Il définit qui a vérifié **la cohérence entre le livrable de design et l'implémentation** (`core/docs/fr/architecture/frontend-design-contract.md` §Artefacts de design et alignement).
Ce document est la source of truth de l'enum `design_verified` de `_order.yaml`.

| Valeur | Définition |
|---|---|
| `none` | Aucun livrable d'UI (`design_ref.kind: none`), ou non vérifié |
| `self` | L'implémenteur a recoupé lui-même avec la définition de cohérence (nom, axe, alias, axe d'état) |
| `designer` | Le propriétaire du livrable de design (le designer ou le responsable de l'outil de design) l'a confirmé |
| `cross` | Un Reviewer d'un autre environnement d'exécution ou modèle l'a confirmé en comparant le rendu du story ou les frames |

Valeurs par défaut et plage obligatoire :

```text
Pas de design_ref, ou kind: none → none
Primitive UI · Semantic Component nouveau/modifié (paquet d'UI partagé) → designer ou supérieur recommandé
Feature Block · Route Surface → self ou supérieur
```

Si `completion.design_sync` vaut `stale`, le travail n'est pas terminé, quelle que soit la valeur de cet axe. `waived` porte un motif et une date d'expiration.
