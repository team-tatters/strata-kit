# Frontend Mobile Layer Architecture

> Canonical: strata-kit `core/docs/en/architecture/frontend-mobile.md` — migrated from strata `docs/03-architecture/frontend-mobile.md` (order 2026.10.29-06, 2026-10-29). The rule YAML is in `core/rules/`.

> Machine-readable rules: `core/rules/layer-rules.yaml` → `frontend.variants.mobile` (DEC-2026-09-11-01)
> This document is the human-readable detailed description of the native mobile UI (SwiftUI, Jetpack Compose) variant.
> Bindings: `profiles/frontend.swiftui/docs/en/frontend-swiftui.md` (verified, o-rot) · there is no Compose binding yet (§Android).
> Tokens, variants, composition and the alignment of design artifacts are defined by `core/docs/en/architecture/frontend-design-contract.md`.

## Why a variant different from web

The eight layers and the `can_reference` table are **exactly the same** as `web`. In the first SwiftUI adoption (o-rot, 2026-09-10), all 46 violations
were file-boundary problems and none were design problems, so the layer semantics are carried over unchanged. Four things differ.

| Axis | web | mobile |
|---|---|---|
| Vocabulary | URL entry points, `use*Query`, `.service.ts`, the Contract's `{Name}ViewModel` = data shape | Navigation-graph entry points, `Store`/`Repository`, the Contract uses `UiState`/`UiModel`. **The name ViewModel means a state owner, so it is not used in Contract** |
| Feature assembly | References between Feature Blocks are forbidden | **Parent → child** assembly within the same domain tree is allowed (`composition: parent_child`). Siblings and the reverse direction are forbidden |
| Targets | Zones and packages | App, widget, watch and intent **put files into several targets** to share them. Core decides which layers may be shared |
| Enforcement ladder | Static analysis of import paths | The compiler (module boundary) is canonical; the type-reference checker is a supplement **inside** a module |

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

## Layers ↔ mobile constructs

| Layer | SwiftUI | Compose (unverified) |
|---|---|---|
| Foundation | Token `enum`, pure `Shape`, time-zone utilities | Token `object`, `MaterialTheme` extensions, pure utilities |
| Contract | `Codable` structs, `{Name}UiState`, pure-rule `enum` + `static func`, deep-link parser | `data class`, `sealed interface UiState`, pure use case functions |
| DataState | `@MainActor final class {Name}Store: ObservableObject` + `actor {Name}Repository` | `ViewModel` (state owner) + `Repository` (`suspend` + `Dispatchers.IO`), Room/DataStore |
| Primitive UI | `public struct: View` in the design system package | Stateless composables in the `core:designsystem` module |
| Semantic Component | Views that take only props, zero `@EnvironmentObject`, `{Model}+Style.swift` | Composables that take only `UiState`, zero `hiltViewModel()` |
| Feature Block | Screen fragments holding `@StateObject`/`@EnvironmentObject` | `{UseCase}Screen` + `hiltViewModel()` |
| Route Surface | `TabView`, `NavigationStack`, `navigationDestination`, deep-link resolution | `NavHost`, type-safe routes, deep links |
| App Shell | `@main App`, global Store creation and the `.environmentObject` chain, `WidgetBundle` | `Application`, `MainActivity`, Hilt modules, `Scaffold` |

## Feature assembly (composition)

A mobile screen is a hierarchy — the Today screen presents a mood sheet, and the Activity tab presents a session-complete sheet. If web's "no references between Feature Blocks"
were kept as is, all of this assembly would be a violation. Mobile uses the domain as a path.

- A domain forms a tree with `/`, as in `today` and `today/mood`. It is declared in `domain:` of `.strata/layer-map.yaml`.
- **A parent may reference its child.** The Feature Block of `today` assembles the sheet of `today/mood`.
- Child → parent and sibling-to-sibling (`today` ↔ `activity`) are forbidden. If two domains use the same fragment, that fragment moves down to Semantic Component.
- TCA's parent reducer → child reducer scope and Compose's parent Screen → child Screen follow the same rule.

## Targets

In Apple's platforms the app, widget, watch, watch complication and App Intents are each a target; on Android they are the app, widget and Wear modules. It is customary to put one file into several targets,
and copying is the seed of drift. Core decides only **what can be shared**.

| Layer | Sharing | Condition |
|---|---|---|
| Foundation · Contract · Primitive UI · Semantic Component | Free | They have no state |
| DataState | Conditional | `layer-map targets.shared[].stateful: true` + the document must state that **each target has its own instance** (for example, the watch HealthStore reads its own HealthKit) |
| Feature Block · Route Surface · App Shell | Forbidden | Each target has different screens, entry points and shell |

The checker reads `targets.shared` in `layer-map.yaml` and cross-checks it against the layers (a `target_share` violation). The canonical source is the project file
(`sources` per target in `project.yml`), and the layer-map transcribes that declaration.

## Enforcement ladder

| Tier | Owner | Strength |
|---|---|---|
| Module boundary (SPM package / Gradle module) | Isolates Foundation · Contract · DataState · Primitive UI from the app target. A package cannot import the app | **Compiler-enforced — canonical** |
| Target | App, widget, watch, tests. Sharing is done by adding a target per file | Compiler-enforced |
| Type-reference checker (`check-swift-layers.py`) / ArchUnit · Konsist | Direction between files **inside** one module, domain isolation, composition, target sharing | CI blocking |
| style rules | New introduction of raw values, system fonts, `Color(hex:)` | CI blocking, on new lines only |
| Edit hook | The same commands as above on the changed files — **based on the git working tree** (not on tool events) | warning → exit 2 as agent feedback |

Each time a package is raised, the checker's share shrinks. When Contract and DataState become packages, that boundary shows up in `import`,
and Core's import-based hook also works on Swift. A brownfield project starts with one design system package and raises Contract, then DataState, in that order.

## Android (unverified)

The Compose counterpart is only the right-hand column of the table above, and it has not been verified in a real project. Things to confirm when applying it:

- The three tiers UI / Domain / Data of Google's official guide correspond to mobile's (Primitive+Semantic+Feature+Route) / Contract / DataState. This is elaboration, not conflict.
- Enforcement reuses Gradle multi-module plus the brownfield mode (layer-map) of `profiles/backend.kotlin-spring-cqrs/enforcement/`. Kotlin's imports are explicit, so a type-reference checker is not needed.
- Process-death restoration (`SavedStateHandle`), lifecycle-aware collection, DI module placement (App Shell) and KMP `commonMain` (sharing Contract + DataState) are decided by the Compose binding document. Methodology backlog MB-o-rot-2026-004.

## Core / Convention / Profile separation

- **Core** (this document + `core/rules/layer-rules.yaml`): layers, `can_reference`, composition and target-sharing rules. Platform independent.
- **Convention** (`profiles/frontend.swiftui/docs/en/frontend-swiftui.md`, later `frontend-compose.md`): how to attach layers to language constructs, concurrency, naming, package management.
- **Profile** (the project's `.strata/layer-map.yaml` · `constraint-registry.yaml`): file mapping, domain tree, target-sharing list, exceptions.
