# Frontend Query / State Convention

> Canonical source: strata-kit `profiles/frontend.next-web/docs/en/frontend-query-state.md` — migrated from strata `docs/05-conventions/frontend-query-state.md` (order 2026.10.29-06, 2026-10-29). Rule YAML lives in `core/rules/`.

> Core boundary: `core/docs/en/architecture/frontend-web.md`

This document is the convention that maps the DataState layer onto a specific library.
Core's source of truth is "the UI does not call transport directly"; this document describes the implementation choices.

## Two segments inside DataState

| Segment | File | Role | May reference |
|---|---|---|---|
| transport | `{name}.service.ts` | HTTP client calls, returns DTOs | Foundation · Contract |
| adapter | `use{Entity}Query.ts` · `use{Entity}{Action}Mutation.ts` · `use{Name}State.ts` | Server/client state hooks | Foundation · Contract · **transport** |

Only an adapter may import transport. Components (Section), the Route Surface and shared hooks see only adapters.

## Hook naming

| Kind | Name | Location (layer) |
|---|---|---|
| Reading server state | `use{Entity}Query` · `use{Entity}ListQuery` | DataState adapter |
| Writing server state | `use{Entity}{Action}Mutation` (Create · Update · Delete · Submit …) | DataState adapter |
| Splitting out Section state logic (optional) | `use{UseCase}Section` — only when another Section reuses it or it is tested on its own. The default is inside the Section | Feature Block |
| Shared processing/computation | `use{Thing}` — logic used by two or more Sections | Feature Block hooks or Foundation |
| Client state | `use{Name}State` · `use{Name}Store` | DataState adapter |
| Pure utility | `use{Thing}` — depends only on framework hooks | Foundation |

**Forbidden prefixes**: `useFetch · useGet · usePost · usePut · usePatch · useDelete`. HTTP verbs are transport vocabulary; hooks use domain vocabulary.
Existing code is left untouched and only new lines are checked (`profiles/frontend.next-web/enforcement/`).

## Query Key — shape · ownership · enforcement

Keys are created only through a key factory — one per feature (domain), kept in that feature's `{domain}.keys.ts`.

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

- **Shape**: `[scope, domain, entity/scope…, params]`. The first element is an app/zone identifier — several apps may share a QueryClient, so this prevents collisions.
- **Hierarchy**: `all → lists → list(p)`, `all → details → detail(id)`. A flat key (`['orders']`) cannot be partially invalidated, so it falls short.
- **Ownership**: Invalidate only from a mutation hook, and only the keys that hook **declares as affected** — through a tag list in the mutation's `meta.invalidates` or an explicit list inside the hook. The declared keys may be a partial tree such as `keys.lists()`, an exact detail key such as `keys.detail(id)`, or another domain's keys, always built with the owning feature's key factory. Calling `invalidateQueries` directly in a component is forbidden.
- **Enforcement**: Static dependency analysis cannot catch inline literals — block only new lines with diff rules (`no-inline-query-key`, `no-component-invalidate`).

## Basic rules

- Wrap server state in query/mutation adapters.
- Put the cache invalidation policy after a mutation in DataState.
- Global state is not the default choice. Consider URL state, the query cache and local state first.
- If prop passing becomes excessive, introduce a composition boundary inside the Feature Block or a feature-local context.

## Prohibitions

- Calling the transport client directly from a UI component
- A Route Surface holding per-use-case mutation details
- A Semantic Component calling a server-state adapter directly
- queryKey literals outside `*.keys.ts`

## Library mapping

In React-family projects, DataState can be implemented with query hooks, mutation hooks and client-state hooks.
The concrete library and its version-specific API are decided in the project profile or the framework convention.
