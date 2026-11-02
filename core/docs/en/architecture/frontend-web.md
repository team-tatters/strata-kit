# Frontend Web Layer Architecture

> Canonical source: strata-kit `core/docs/en/architecture/frontend-web.md` — migrated from strata `docs/03-architecture/frontend-web.md` (order 2026.10.29-06, 2026-10-29). Rule YAML is in `core/rules/`.

> Machine-readable rules: `core/rules/layer-rules.yaml` → `frontend.variants.web`
> This document is the human-readable detail for the framework-independent web frontend variant.
> The consistency between tokens, variants, compositions and design deliverables is defined by `core/docs/en/architecture/frontend-design-contract.md`.

## Boundary principles

Strata Core's frontend guidance does not define a specific UI framework, router, state-management library or styling tool.
Core holds only responsibility boundaries that can be verified by import, path and static analysis.

The layer relationship is a DAG, not a single linear tree.
`can_reference` in the table below is the source of truth. References to layers outside the table, and same-level cross references among layers with `cross_reference: false`, are forbidden (for Feature Block this means across domains; see below).

| Layer | can_reference |
|---|---|
| Foundation | none |
| Contract | Foundation |
| DataState | Foundation, Contract |
| Primitive UI | Foundation |
| Semantic Component | Foundation, Contract, Primitive UI |
| Feature Block | Foundation, Contract, DataState, Primitive UI, Semantic Component |
| Route Surface | Foundation, Contract, Feature Block, App Shell |
| App Shell | Foundation, Contract, DataState, Primitive UI, Semantic Component |

## Variants

Strata frontend supports three variants.

| Variant | Purpose | Status |
|---|---|---|
| `atomic` | The existing L1/LM/L2/Atomic/Molecule/Partial/Page/Layout structure, and compatibility with legacy projects | Maintained |
| `web` | Framework-independent web application boundaries | Default |
| `mobile` | Native mobile UI (SwiftUI, Compose) — layers and can_reference are the same as web, but vocabulary, composition and target rules differ (`core/docs/en/architecture/frontend-mobile.md`) | 2026-09-11 |

A project makes its choice in `variant` or `frontend_variant` of `.strata/layer-map.yaml`.
If no value is chosen, the Core default is `web`.

## Foundation

Holds semantic tokens, pure functions, constants and primitive types.

**Allowed:** token, const, type, util

**Forbidden:** UI rendering, transport calls, global state access, framework-dependent implementations

## Contract

The stable contract between the UI and transport.
It holds DTOs, ViewModels, schemas, API ports/interfaces and cache key contracts.

**Rules:**
- Reference Foundation only.
- Do not reference UI layers or DataState.
- Do not call transport implementations directly.
- Gather into this layer the interfaces and types that tend to be scattered across component files.

## DataState

The adapter layer for server state, mutations and client state.
The concrete library is decided in the convention; Core defines only the boundary that keeps the UI from seeing transport directly.

**Rules:**
- Reference Foundation and Contract only.
- Do not render UI components.
- Do not expose the transport client directly to the UI.
- Cache keys and DTO/ViewModel contracts refer to Contract.

**Two sections:** transport (`{name}.service` — HTTP calls, returns DTOs) and adapter (`use{Entity}Query` · `use{Entity}{Action}Mutation` · `use{Name}State`).
Only the adapter may import transport. Upper layers see only the adapter.

## Primitive UI

Low-level UI bound to semantic tokens.
It must not know domain meaning or server state.

**Rules:**
- Reference Foundation only.
- Do not reference Contract's domain models, DataState or transport.
- Work with Props and Foundation tokens alone.

## Semantic Component

A UI component that carries user or domain meaning.
Rather than a size classification like Atomic/Molecule, it expresses "what this component does" through its name and responsibility.

**Core verifiable boundary:** a Semantic Component does not call DataState directly.
Server state and mutations are injected through props or callbacks.

A component split off as the render half of a Feature Block is named `{Domain}{Purpose}View`. The data-state axis (loading · empty · error) is received as props.
Appearance is decided only by a combination of Primitive UI variant-axis values and Foundation aliases (Composition Legality — `core/docs/en/architecture/frontend-design-contract.md`).

## Feature Block

The layer that assembles a screen fragment and its data/state for a specific use case.
DataState calls are allowed from this layer up.

**Rules:**
- Direct references between Feature Blocks of different domains are forbidden. Inside one domain, a Section may contain another Section as a child. When screens of different domains must appear together, the Route Surface's `{RouteName}Page` places each domain's Section side by side and connects them through props and events.
- A domain is one directory directly under the feature root (layer-map `feature_root`, or else the prefix of layer-rules `Feature_Block.domain_slice`). Feature Block files outside the root are not domain-isolated. This boundary is a boundary of code slices and does not guarantee the meaning of a business domain.
- Assemble Semantic Component, Primitive UI, DataState and Contract.
- Do not take on routing or app-level provider responsibilities.

The suffix is `{UseCase}Section` (a screen fragment without a route — the counterpart of Partial in the atomic variant); depending on the form, use `Panel` · `Dialog` · `Table`. The suffixes `Block`, `Container` and `Partial` are forbidden (`core/rules/naming-convention.yaml` → `Feature_Block.forbidden_suffixes`).
The Section is the **owner of the state for its use case** (a child Section that is an independent save unit owns its own) — it declares Props, holds local state, effects and DataState adapter hooks directly, and propagates them downward only. Rendering is left to a `View` (Semantic Component):
`Route Surface → Section → View → Primitive UI`. State ownership is split three ways — owning a local draft, observing the server cache, and being responsible for the save command. A same-domain child Section owns the draft and mutations only when it is its own use case and an independent save unit; only state shared with the parent comes in as props. A draft edited by several Sections has one owner, and submit, cancel or atomic save across Sections belongs to one coordinator (the parent Section), with the inner inputs as Views or controlled components. Atomicity comes from a single DataState/API command or transaction, not from invalidation after several mutations. Several Sections observing the same query key is not duplicate ownership. Separating state logic into hooks is not an obligation; only the service call (transport) and processing shared by two or more Sections are kept outside, as a reference structure. For the criteria of separation and Props naming, see `profiles/frontend.next-web/docs/en/frontend-react.md`.

## Route Surface

Responsible for URL entry points, route params, permission boundaries and screen assembly.

**Rules:**
- Place Feature Blocks — in principle one Section. With two or more, add a `{RouteName}Page` assembly component. That assembly component is a Route Surface wherever it sits (routes or features) — in the layer-map, put its mapping before the Feature Block mapping.
- Do not export it as reusable UI.
- Direct transport calls are forbidden. DataState hook calls are also forbidden — DataState is not in `can_reference`.

File rules per router are defined in the framework convention, not in Core.

## App Shell

Responsible for global providers, navigation and app-level layout.

**Rules:**
- Do not reference Feature Blocks directly.
- Do not hold domain use case logic.
- Handle only global providers and shell-level layout.
- A shell package shared by several apps (zones) is also an App Shell. Moving across an app boundary is done by URL only.

## Core / Convention / Profile separation

| Nature | Location | Example |
|---|---|---|
| Verifiable architecture boundary | Core `core/docs/en/architecture/frontend-web.md`, `core/rules/layer-rules.yaml` | Semantic Component must not reference DataState |
| Design contract (tokens · variants · composition · consistency) | Core `core/docs/en/architecture/frontend-design-contract.md` | Components reference aliases (component tokens only from their owner); design_ref and alignment status |
| Framework/library binding | `profiles/<id>/docs/en/` | query hook, router, styling tool, token file mapping |
| Project legacy/transition policy | Project `.strata/` | legacy/bridge/target zone |

Strata Core defines not "which library is used" but "which responsibility must pass through which layer".
