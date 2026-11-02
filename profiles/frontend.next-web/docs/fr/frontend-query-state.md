# Convention Query / State pour le frontend

> Source canonique : strata-kit `profiles/frontend.next-web/docs/fr/frontend-query-state.md` — migré depuis strata `docs/05-conventions/frontend-query-state.md` (ordre 2026.10.29-06, 2026-10-29). Le YAML des règles se trouve dans `core/rules/`.

> Frontière de Core : `core/docs/fr/architecture/frontend-web.md`

Ce document est la convention qui associe la couche DataState à une bibliothèque précise.
La source of truth de Core est « l'UI n'appelle pas transport directement » ; ce document décrit les choix d'implémentation.

## Deux tronçons dans DataState

| Tronçon | Fichier | Rôle | Peut référencer |
|---|---|---|---|
| transport | `{name}.service.ts` | Appels du HTTP client, retourne des DTO | Foundation · Contract |
| adapter | `use{Entity}Query.ts` · `use{Entity}{Action}Mutation.ts` · `use{Name}State.ts` | Hooks d'état serveur/client | Foundation · Contract · **transport** |

Seul un adapter peut importer transport. Les composants (Section), le Route Surface et les hooks communs ne voient que les adapters.

## Nommage des hooks

| Type | Nom | Emplacement (couche) |
|---|---|---|
| Lecture de l'état serveur | `use{Entity}Query` · `use{Entity}ListQuery` | DataState adapter |
| Écriture de l'état serveur | `use{Entity}{Action}Mutation` (Create · Update · Delete · Submit …) | DataState adapter |
| Séparer la logique d'état d'une Section (facultatif) | `use{UseCase}Section` — seulement quand une autre Section la réutilise ou qu'elle est testée seule. Par défaut, dans la Section | Feature Block |
| Traitement/calcul commun | `use{Thing}` — logique utilisée par au moins deux Sections | Feature Block hooks ou Foundation |
| État client | `use{Name}State` · `use{Name}Store` | DataState adapter |
| Utilitaire pur | `use{Thing}` — ne dépend que des hooks du framework | Foundation |

**Préfixes interdits** : `useFetch · useGet · usePost · usePut · usePatch · useDelete`. Les verbes HTTP sont le vocabulaire de transport ; les hooks utilisent le vocabulaire du domaine.
Le code existant n'est pas touché et seules les nouvelles lignes sont vérifiées (`profiles/frontend.next-web/enforcement/`).

## Query Key — forme · propriété · application

Les clés ne sont créées que via une key factory — une par fonctionnalité (domaine), placée dans le `{domain}.keys.ts` de cette fonctionnalité.

```ts
// features/{domain}/{domain}.keys.ts
export const orderKeys = {
  all:     ['shop', 'order'] as const,                       // [scope, domain]
  lists:   () => [...orderKeys.all, 'list'] as const,
  list:    (p: OrderListRequest) => [...orderKeys.lists(), p] as const,
  details: () => [...orderKeys.all, 'detail'] as const,
  detail:  (id: number) => [...orderKeys.details(), id] as const,
};
```

- **Forme** : `[scope, domain, entity/scope…, params]`. Le premier élément est l'identifiant d'application ou de zone — plusieurs applications pouvant partager le QueryClient, cela évite les collisions.
- **Hiérarchie** : `all → lists → list(p)`, `all → details → detail(id)`. Une clé plate (`['orders']`) ne permet pas l'invalidation partielle ; elle est donc insuffisante.
- **Propriété** : l'invalidation se fait uniquement depuis un hook de mutation, et uniquement sur les clés que ce hook **déclare comme affectées** — via une liste de tags dans `meta.invalidates` de la mutation ou une liste explicite dans le hook. Les clés déclarées peuvent être un **sous-arbre** tel que `keys.lists()`, une clé de détail exacte telle que `keys.detail(id)`, ou les clés d'un autre domaine, toujours construites avec la key factory de la fonctionnalité propriétaire. Appeler `invalidateQueries` directement dans un composant est interdit.
- **Application** : l'analyse statique des dépendances ne détecte pas les littéraux en ligne — on bloque uniquement les nouvelles lignes avec des règles de diff (`no-inline-query-key`, `no-component-invalidate`).

## Règles de base

- L'état serveur est enveloppé dans des adapters query/mutation.
- La politique de cache invalidation après une mutation est placée dans DataState.
- L'état global n'est pas le choix par défaut. On examine d'abord l'URL state, le query cache et le local state.
- Si le passage de props devient excessif, on met en place un composition boundary à l'intérieur du Feature Block ou un feature-local context.

## Interdictions

- Appeler le transport client directement depuis un composant UI
- Qu'un Route Surface détienne les détails de mutation propres à un use case
- Qu'un Semantic Component appelle directement un server-state adapter
- Des littéraux de queryKey en dehors de `*.keys.ts`

## Association des bibliothèques

Dans les projets de la famille React, DataState peut être implémenté avec des query hooks, des mutation hooks et des client-state hooks.
La bibliothèque concrète et son API selon la version sont décidées dans le profile du projet ou dans la framework convention.
