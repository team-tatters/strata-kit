# Frontend React Convention

> Canonical source: strata-kit `profiles/frontend.next-web/docs/en/frontend-react.md` — migrated from strata `docs/05-conventions/frontend-react.md` (order 2026.10.29-06, 2026-10-29). Rule YAML lives in `core/rules/`.

> Core boundary: `core/docs/en/architecture/frontend-web.md` · Design contract: `core/docs/en/architecture/frontend-design-contract.md`

This document describes the conventions for a React project implementing the Core web layers.
React is not a required prerequisite of Core.

## One-way chain — Page → Section → View → Primitive

Flow goes one way only, from route to screen. **The Section is the owner of the state for its use case** (a child Section that is an independent save unit owns its own) — the Section declares the Props, holds the state, and propagates it downward only.

```
route file (Route Surface)
  └─ params · guard · metadata · exactly one <XxxSection/>. Hooks: routing hooks only
      └─ XxxSection (Feature Block) — state owner
           │  useState · useEffect · local hooks · DataState adapter hooks (use*Query · use*Mutation) are called directly here
           ├─ <XxxView/>          Semantic Component — receives props only and renders
           └─ <XxxSubSection/>    child Section of the same domain if needed — a state owner when it is an independent save unit:
                                  fetches and saves its own use case data directly; only state shared with the parent comes in as props.
                                  An input submitted or cancelled together with the parent is a View or controlled component,
                                  not a Section; the parent owns the draft and the submit (atomic save: one command or transaction)
                └─ Primitive UI + alias tokens
```

## State ownership in a Section and where to split

What stays inside a Section and what moves out is decided by **kind, not count**. Splitting state logic into a hook is not an obligation.

| Kind | Location | Reason |
|---|---|---|
| Local state (`useState` · `useReducer`), effects (`useEffect`), derived values (`useMemo`), local hooks used only by this Section | **Inside the Section** | The owner of state must be visible in one place |
| Reading and writing server state | The Section **calls** DataState adapter hooks. The implementation is in `query-hooks/` | Transport does not appear in the Section |
| Service calls (HTTP · storage · external SDK) | **Always outside** — DataState transport | Components do not know about transport |
| Processing, computation or state logic used by two or more Sections | **Outside** — `features/{domain}/hooks/use{Thing}` or a Foundation util | Shared tiers use a reference structure |
| When another Section must reuse one Section's state logic wholesale, or it must be tested on its own | Optional — split out as `use{UseCase}Section` | Split only when needed. The default is inside the Section |

## Meaning of suffixes

| Suffix | Layer | DataState calls | Router hooks | Notes |
|---|---|---|---|---|
| `{Route}Page` / route file | Route Surface | Forbidden | Allowed | The principle is placing one Section. With two or more, a `{Route}Page` assembly component — a Route Surface wherever it sits, routes or features (its layer-map mapping comes before the Feature Block one). Sections of different domains are placed side by side here |
| `{UseCase}Section` | Feature Block | Allowed | Forbidden — the Page injects | State owner. A screen fragment without a route, reusable across several routes. Importing a Section of another domain is forbidden; a Section of the same domain may be contained as a child |
| `{UseCase}Panel` · `Dialog` · `Table` | Feature Block | Allowed | Forbidden | A Section shaped as an overlay, side panel or table |
| `{Domain}{Purpose}View` | Semantic Component | Forbidden | Forbidden | Props only. May hold only local UI state (open, hover) |
| Primitive component | Primitive UI | Forbidden | Forbidden | Alias + variant axes only |

The suffixes `Container`, `Block` and `Partial` are forbidden — use `Section` (or `Panel` · `Dialog` · `Table` by shape).

## Props naming — put owner and direction in the name

When state and hooks owned by a Section flow down to several children, the prop name alone must tell **who owns it, which way it flows, and whether it is a value or an action**. Prefixes and suffixes express those three. Machine-readable: `core/rules/naming-convention.yaml` → `frontend.Props`.

| Role | Form | Example | Rule |
|---|---|---|---|
| Current value of parent-owned state (read) | Noun, no prefix | `selectedIds` · `filter` · `page` | No prefix = "parent-owned, the child only reads" |
| Request to change parent state (child → parent) | `on{State}Change` | `onSelectedIdsChange` · `onFilterChange` | Do not pass the setter as-is. `set*` props are forbidden |
| Trigger a parent action (event) | `on{Event}` (verb) | `onSubmit` · `onRowClick` · `onDelete` | When the child does not need to know the result |
| A value + change pair **shared by several children** | `{state}Control` bundle | `selectionControl={{ value, onChange }}` | Multi-reference marker. Type `{State}Control`. Do not scatter the same state across several children as separate value and callback props |
| Bundle of derived/display-only data | `{name}Model` | `orderModel` | The Contract's ViewModel. Do not put callbacks in it |
| Initial value (owned by the child) | `default{State}` | `defaultPage` | Uncontrolled. The parent does not interfere afterwards |
| Boolean | `is` · `has` · `can` · `should` | `isEditing` · `canDelete` · `shouldAutoFocus` | Positive form. HTML attribute names such as `disabled` are an exception |
| Server-state slice | Data noun + `is{Entity}Loading` + `{entity}Error` | `orders` · `isOrdersLoading` · `ordersError` | Do not pass the whole query result object |
| Render delegation | `render{Slot}` | `renderRow` | |
| ref | `{name}Ref` | `scrollRef` | |

**Recommendation — use a Control bundle for multiple references.** When three children read and write one piece of parent state, bundle `value`, `onChange` and derived values into a single `{state}Control` object and pass it down. The suffix in the name shows that it is state owned by the parent and shared in several places, and the number of props does not grow as children are added. Flat prefixes such as `shared*` or `section*` say who owns it but not the direction (read/write), so do not use them.

```tsx
// Section — state owner
const [selectedIds, setSelectedIds] = useState<number[]>([]);
const selectionControl: SelectionControl = { value: selectedIds, onChange: setSelectedIds, count: selectedIds.length };
const { data: orders = [], isLoading: isOrdersLoading } = useOrderListQuery(filter);

<OrderTableView orders={orders} isOrdersLoading={isOrdersLoading} selectionControl={selectionControl} onRowClick={handleRowClick} />
<OrderBulkActionView selectionControl={selectionControl} onDelete={handleDelete} />
```

Internal handler functions are named `handle{Event}`, and the prop names passed to children are `on{Event}`. Do not use the same name for both.

## Component Boundary

- Put one exported component in a file.
- Helper functions and private subcomponents inside a file are allowed, but split them into a separate file once they are reused.
- Move DTOs, ViewModels, schemas and interfaces to Contract.
- A Semantic Component does not call DataState hooks directly; it receives them injected through props/callbacks.
- The data-state axes (loading · empty · error) are received as the View's props and rendered. The Section decides the values.

## State Boundary

- Use case assembly and DataState calls start in the Feature Block (Section).
- Do not put a server-state library dependency into shared UI components.
- Use a feature-local context only in a limited way, when prop passing gets deep. If a Control bundle solves it, do not create a context.
