# Convention Styling pour le frontend

> Source canonique : strata-kit `profiles/frontend.next-web/docs/fr/frontend-styling.md` — migré depuis strata `docs/05-conventions/frontend-styling.md` (ordre 2026.10.29-06, 2026-10-29). Le YAML des règles se trouve dans `core/rules/`.

> Frontière de Core : `core/docs/fr/architecture/frontend-web.md` · Contrat de design : `core/docs/fr/architecture/frontend-design-contract.md` · Liaison des tokens : `profiles/frontend.next-web/docs/fr/frontend-tokens.md`

Ce document est la convention qui associe les outils de styles aux couches de Core.
Core n'exige aucune bibliothèque d'UI ni aucun outil CSS particulier.

## Layer Mapping

- Primitive UI détermine son apparence uniquement à partir des tokens alias et des axes variant (`variant · intent · size · state`).
- Un Semantic Component détermine son apparence uniquement par une combinaison de valeurs d'axes de Primitive et de tokens alias (Composition Legality).
- Un Feature Block est un fragment d'écran propre à un use case précis, et exprime aussi le layout par des alias (space · radius).

## Règles sur les valeurs d'axe

- La valeur d'un axe de couleur est une intention (`intent`). On n'utilise pas de noms de palette (`green · red · blue`) comme valeurs d'axe.
- Si un statut de domaine est nécessaire (par exemple `pending · completed`), on ne le mélange pas à `intent` ; on le garde dans un axe `status` distinct.
- Les noms des propriétés de composant dans l'outil de design et les noms de props dans le code restent identiques — c'est le préalable du contrôle de cohérence.

## Project-Specific Mapping

Les choix tels que MUI, Tailwind, CSS-in-JS et les paquets de design-system relèvent du profile du projet ou d'une extension propre au projet de cette convention.
Quel que soit l'outil, la règle est la même : les classes utilitaires et les objets de style reflètent les noms alias, et les valeurs raw et les noms T1 n'apparaissent jamais hors de Foundation.
Ce choix n'est pas une règle de Core, mais un constraint du projet.
