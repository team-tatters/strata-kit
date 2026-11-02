# Frontend Atomic Variant Layer Architecture

> Canonical: strata-kit `core/docs/en/architecture/frontend-atomic.md` — migrated from strata `docs/03-architecture/frontend-atomic.md` (order 2026.10.29-06, 2026-10-29). The rule YAML is in `core/rules/`.

> Machine-readable rules: `core/rules/layer-rules.yaml` → `frontend.variants.atomic`
> The default variant for new web projects is `frontend.variants.web`; see `core/docs/en/architecture/frontend-web.md` for details.
> **Status: retained (legacy compatibility)** — adopting it for new work is not recommended. The size-based classification into Molecule/Organism has been replaced by the Composition Legality of the web variant (`core/docs/en/architecture/frontend-design-contract.md`).

## Mapping to the web variant

| Atomic | web variant | Criterion |
|---|---|---|
| Atom | Primitive UI | Domain-agnostic, alias tokens + variant axes only |
| Molecule | Semantic Component **or** Feature Block | A Feature Block if it calls DataState, otherwise a Semantic Component. **Not judged by size** |
| Organism | (retired) | Absorbed into Feature Block |
| Partial | Feature Block (`{UseCase}Section`) | A screen fragment without a route |
| Page · Layout | Route Surface · App Shell | As is |
| L2 Hook | DataState adapter | `useQuery{Name}` → `use{Entity}Query` |
| LM | Contract + DataState transport | ViewModel and DTO go to Contract, the API Client goes to `{name}.service` |

## Layer structure

```
Page / Layout
    ↓
Partial (a set of page-level common UI)
    ↓
Molecule (behavior-specific component)
    ↓
Atomic (pure UI component)
    ↓
L2 (state management Hook)
    ↓
LM (ViewModel, DTO, API Client)
    ↓
L1 (pure functions, types, constants)
```

## L1 — pure function layer

The same principle as backend L1. Pure logic that does not depend on a UI framework.
Pure state management Hooks are allowed, but API calls are forbidden.

**Examples:** useDebounce, useLocalStorage, formatDate, validateEmail

## LM — data model layer

The intermediate layer that handles communication with the server.

**Composition:** ViewModel (display-only data structure), DTO (server request/response mapping), 
API Port/Client Interface (the transport call boundary), Interface (contract definition)

**Rules:** No UI rendering logic. It handles only data transformation and communication.

## L2 — state management layer

Adapter Hooks for server/client state.

**Rules:** Use the LM API Client to synchronize server state.
Do not render UI components directly. Export Hooks only.

## Atomic — smallest-unit UI

A pure UI component with every dependency at L2 and below removed.
It works on props alone, and access to global state is forbidden.

**Examples:** Button, Input, Badge, Avatar, Tooltip, Card

## Molecule — behavior-specific UI

A component that combines Atomics and binds an L2 Hook.
It is specialized for a particular domain behavior.

**Examples:** SearchBar (Input + Button + useSearchStore),
OrderCard (Card + Badge + useOrderQuery)

## Partial — page-level common set

A UI block shared across several pages.
A combination of Molecules and Atomics.

**Examples:** OrderListPartial, UserProfilePartial, NotificationPanel

## Page — route target

The top-level component mapped to an actual URL.
It combines Layout, Partial, Molecule and Atomic into a complete screen.

## Layout — structural wrapper

Defines page structure such as navigation, sidebar and footer.
Receives the Page component as children.
