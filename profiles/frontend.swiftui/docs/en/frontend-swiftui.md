# Frontend Swift/SwiftUI Convention

> Canonical source: strata-kit `profiles/frontend.swiftui/docs/en/frontend-swiftui.md` — migrated from strata `docs/05-conventions/frontend-swiftui.md` (order 2026.10.29-06, 2026-10-29). The rule YAML lives in `core/rules/`.

> Core boundary: `core/docs/en/architecture/frontend-mobile.md` (`core/rules/layer-rules.yaml` → `frontend.variants.mobile`) · design contract: `core/docs/en/architecture/frontend-design-contract.md` · enforcement: `profiles/frontend.swiftui/enforcement/`
> v1 2026-09-10 (web variant binding, first applied to o-rot) → **v2 2026-09-11** (mobile variant — vocabulary, Feature assembly, targets, enforcement ladder, hooks, DEC-2026-09-11-01)

This document is the convention for a SwiftUI app that implements the Core mobile variant (Foundation → … → App Shell).
SwiftUI is not a required premise of Core. Core only decides "which layers a responsibility must pass through" and the rules for assembly and target sharing; this document attaches those to Swift constructs.

## Summary

- The first-class key for identifying a layer is **the role of the type a file holds**, not the directory. `.strata/layer-map.yaml` reclassifies by role, and files are not moved.
- **The compiler is the canonical enforcer.** The more layers you lift into local SPM packages, the more the boundaries show up as `import`. The type-reference checker (`check-swift-layers.py`) is an auxiliary that looks at the direction between files within one module.
- The state owner is the Feature Block: a view that creates its state with `@StateObject` or receives it with `@EnvironmentObject`. A view that receives only `props` is a Semantic Component. Store **creation** and the environment injection chain live in one place, the App Shell.
- A Feature assembles only **parent → child** within the same domain tree (`today` → `today/mood`). A piece shared between siblings moves down to a Semantic Component.
- Sharing across targets means adding the target, not copying. Foundation, Contract, Primitive and Semantic are free; DataState requires `stateful: true` plus an explicit instance separation; Feature, Route and Shell are forbidden.
- `tokens.json` in the code repository is canonical for tokens, and the Swift token file is generated. Hex values, system fonts and raw numbers are forbidden in views.

## Layer ↔ Swift constructs

| Layer | What it is in Swift | Marker | Forbidden |
|---|---|---|---|
| Foundation | Token enums (`Color`, `Font`, spacing), pure `Shape`, constant enums, pure utilities such as time zones | `enum {Name}Tokens` · `static let` only | `ObservableObject`, I/O, `UserDefaults`, views |
| Contract | `Codable` models and DTOs, screen state values `{Name}UiState`, pure calculation rules (`enum` + `static func`), deep link parsers, port protocols | value types · `import Foundation` only | SwiftUI import, **display properties** such as color or icon, **the name `ViewModel`** (on mobile it means a state owner) |
| DataState | `Store` (main-actor state owner) + `Repository`/`Service`/`Session` (isolated I/O) | `@MainActor final class {Name}Store: ObservableObject` · `actor {Name}Repository` | View rendering, direct reference to another domain's Store |
| Primitive UI | Domain-agnostic views of the design system package (Button, Chip, Row, TabBar) | `public struct {Name}: View` · axis props (variant, intent, size) · **must be a separate package** | Domain models, Store |
| Semantic Component | Meaningful views that draw from props/UiState only — charts, stages, headers, empty states, display-property extensions of models | `struct {Domain}{Purpose}View: View` · `{Model}+Style.swift` · `@EnvironmentObject` 0 | Store access, `@StateObject` |
| Feature Block | State owner of a screen fragment — holds a Store via `@StateObject`/`@EnvironmentObject` and propagates props downward | `struct {UseCase}View` · `{UseCase}Sheet` · domain tree `today/mood` | Referencing a sibling domain's Feature, owning the navigation graph |
| Route Surface | `TabView` and `NavigationStack` entry points, `navigationDestination`, tab selection, deep link resolution | `MainTabView` · `{Flow}Flow` | Store **creation or reference** (injection belongs to the App Shell), exporting reusable UI |
| App Shell | `@main struct App`, global Store creation and the `.environmentObject` chain, `WidgetBundle`, shell chrome (tab bar) | `{Name}App` · `{Name}Shell` · `{Name}Bundle` | Domain use case logic, direct reference to a Feature |

`can_reference` is exactly the Core table. Only three SwiftUI-specific points are added.

- **Environment injection is a reference.** `@EnvironmentObject var store: TodoStore` means that file references `TodoStore`. A Semantic Component must have no `@EnvironmentObject`.
- **`@StateObject` creation is ownership.** Store creation happens in the App Shell, and screen-local state only in a Feature Block. A Route Surface that creates a Store is a violation (the shape in which o-rot `MainTabView` created eight stores gave rise to this rule).
- **`@main` is the App Shell.** If an entry-point decision such as the onboarding/main branch lives in `@main`, move that branch down into a `{Name}Shell` view and leave only Store creation and injection in `@main`. Until it is separated, keep it in the layer-map `exceptions` together with a DEC.

## Feature assembly

```
Features/Today/TodayView.swift          domain: today        ← holds the Store via @EnvironmentObject
Features/Today/Mood/MoodSheetView.swift domain: today/mood   ← the parent (today) presents it with .sheet
Features/Activity/ActivityView.swift    domain: activity     ← sibling of today. Using MoodSheetView is a violation
```

- Write the domain in the `domain:` field of `layer-map.yaml` as a `/` path. The checker lets only parent → child references through.
- If two siblings present the same sheet, move the render part of that sheet down to a Semantic Component (`MoodPickerView`), and each Feature wraps it with its own Store.
- If you use TCA, the parent reducer's `Scope` is exactly this edge. No pattern name is prescribed — only the edge direction is kept.

## Targets

- Phone, widget, watch, complication and intent are each a target. Sharing means **adding a file** to the per-target `sources` in `project.yml`; no copies are made.
- Copy the shared list into `targets.shared` of `layer-map.yaml`. The checker cross-checks the layers (`target_share`).
- If two targets share a DataState (for example, the watch uses the phone's `HealthStore` file), declare it `stateful: true`, and document that each target has its own instance and what each one reads.
- Data exchange between targets (App Group `UserDefaults`, `WatchConnectivity`) is handled by a single DataState `{Name}Session`/`{Name}Bridge` file. A view that opens `UserDefaults(suiteName:)` directly is a violation.

## State ownership and the observation model

- The default is `ObservableObject` + `@Published` + `@MainActor`. Stores are classes, models are structs.
- Use `@Observable` (the Observation framework) **only when the deployment target is iOS 17 / watchOS 10 or later**. The two models differ in property wrappers (`@StateObject` ↔ `@State`) and in update granularity, so mixing them makes initialization timing diverge — one project uses only one model. ([Apple: Observation](https://developer.apple.com/documentation/observation), [Squires: not a drop-in replacement](https://www.jessesquires.com/blog/2024/09/09/swift-observable-macro/))
- A Store knows only its own domain. Assembly that ties two Stores together is done by a Feature Block. If a Store references another Store, it is a DataState cross-domain reference violation.
- Persistence ends inside the Store/Repository. If `UserDefaults.standard` or file I/O appears in a view or in Contract, it is a violation.

## Concurrency

- The Swift 6 language mode turns data races into compile errors. Adopt it **incrementally**: `SWIFT_STRICT_CONCURRENCY = targeted` → `complete` → language mode 6. Do not turn it all on at once. ([Apple: Adopting strict concurrency](https://developer.apple.com/documentation/swift/adoptingswift6))
- Every Store that a view touches is `@MainActor`. I/O goes back to the Store through `actor {Name}Repository` or `nonisolated` + `Task { @MainActor in … }`. Delegate callbacks (`WCSessionDelegate` and the like) follow the same convention.
- Models (structs) conform to `Sendable` by default. If the Contract package exports only `Sendable`, the actor boundaries line up on their own.

## Naming — follow the Swift API Design Guidelines as they are

The canonical source is the [swift.org API Design Guidelines](https://www.swift.org/documentation/api-design-guidelines/). Where they conflict with `common.case_styles` in Core `core/rules/naming-convention.yaml`, **the Swift convention wins** (table below). A file name is the same as the top-level type it holds.

| Item | Swift | Difference from the Core default |
|---|---|---|
| Types, protocols | `UpperCamelCase` | Same |
| Functions, variables, properties, cases | `lowerCamelCase` | **enum cases are lowerCamelCase** — do not use Core's `UPPER_SNAKE` |
| Constants | `lowerCamelCase` (`static let graceDays`) | Do not use Core's `UPPER_SNAKE` |
| Booleans | Read as assertions — `isEmpty` · `hasWatch` · `canDelete` | Same as the Core Props rule |
| Screen state value | `{Name}UiState` (Contract) | Do not use Core web's `{Name}ViewModel` — on mobile, ViewModel is a state owner |
| State owner | `{Name}Store` (DataState) | Counterpart of Core web's `use{Name}State` |
| Factory | `make…` | |
| Mutating/non-mutating pair | `sort()` / `sorted()`, `append` / `appending` | |
| Protocol | What it is → noun; capability → `-able` `-ible` `-ing` | |
| Acronyms | Keep case uniform — `hrvSeries` · `isHRV` (all caps only where it starts uppercase) | |
| Argument labels | Read like a sentence. If the first argument is a prepositional phrase, the label is required | |
| Forbidden suffixes | `Manager` · `Helper` · `Impl` | Same as Core. `Handler` only for delegate methods |

What corresponds to Props is a view's `init` arguments and stored properties. Apply the Core `Props` rule: parent state is a noun with no prefix, a change request is `on{State}Change`, an event is `on{Event}`, and an internal handler is `handle{Event}`. In SwiftUI, `Binding<T>` is a "value + change pair", so it corresponds to Core's `{state}Control` bundle — if several children use the same state, pass down one `Binding`.

The `naming:` block of `layer-map.yaml` is not enforced by the checker. File name = top-level type name is a convention and is checked in review.

## Enforcement ladder — the compiler is canonical

| Tier | Responsible for | Strength |
|---|---|---|
| Local SPM package (`Package.swift`) | Isolates Foundation, Contract, DataState and Primitive UI from the app target. A package cannot import the app, and dependencies between packages go only in the direction declared in `dependencies:` | **Compiler-enforced — canonical** |
| Target (`project.yml` / Xcode target) | App, widget, watch, tests. Shared sources are added to a target file by file | Compiler-enforced |
| `check-swift-layers.py` | Layer direction between files **within** one module, domain isolation, Feature assembly, target sharing | CI blocking |
| `--style` rule / SwiftLint custom_rules | New inflow of raw values, system fonts, `Color(hex:)` and the like | CI blocking, recommended on new lines only |
| Edit hook | The same checker on **files changed in the git working tree** (`--changed`) | exit 2 → agent feedback |

- **Package stages.** A brownfield project starts with one design system (Foundation + Primitive UI) package. Next is Contract (models, rules, `Sendable` values), then DataState. Each time you go up one stage, that boundary shows up in `import`, so Core's import-based hook also works in Swift, and the type-reference checker's share shrinks to the inside of the app target (Semantic → Feature → Route → Shell). Skeleton: `profiles/frontend.swiftui/enforcement/Package.swift.template`.
- **Package management uses SPM alone.** Do not newly adopt CocoaPods or Carthage. ([DECODE: modularize with SPM](https://decode.agency/article/project-modularization-swift-package-manager/), [Nimble](https://nimblehq.co/blog/modern-approach-modularize-ios-swiftui-spm))
- **Generate the project declaratively.** Do not edit `.xcodeproj` by hand; generate it from XcodeGen `project.yml` (or Tuist). The target graph must be reviewable as text so that layer and target decisions show up in the PR. ([XcodeGen vs Tuist](https://medium.com/@sayefeddineh/xcodegen-vs-tuist-choosing-the-right-tool-for-xcode-project-generation-bea093c6e105))
- Pin external packages' **versions** (`exact` or `upToNextMinor`) and commit `Package.resolved`.
- **Attach the edit hook by git, not by tool event.** If Claude Code's PostToolUse is attached only to `Write|Edit`, Bash edits (sed, heredoc) skip the check. Set the matcher to `Write|Edit|Bash`, and on a Bash event the checker falls back to `--changed` (based on git status). Settings template: `profiles/frontend.swiftui/enforcement/settings.json.template`.

## Tokens and typography (design contract binding)

- The canonical source is `tokens.json` in the repository. The Swift token file (`{Name}Tokens.swift`) is its generated output, and `Color(hex:)` initialization appears **only inside this file**.
- Views use only alias names: `OrotColor.sage700` ○ / `Color(hex: "507663")` ✗ / `.font(.system(size: 13))` ✗ / `.padding(14)` should use a spacing token.
- A new alias is an architecture decision — decision record + `tokens.json` → Swift, in that order. A temporary value is `/// @strata:token-exception … until YYYY-MM-DD`.
- Typography tokens have three axes: text scale (title, body, caption), **icon size** (`icon.sm/md/lg` — replaces `.font(.system(size:))` for SF Symbols), and **platform scale** (the watch is a separate scale, not a shrunken phone). If `.font(.system` remains because an axis is missing, the token-adding DEC comes first.
- Accessibility is carried by tokens: only aliases with a text contrast of 4.5:1 or higher are used for text, and those below that are marked in the name as non-text only. Dynamic Type is absorbed by the token through `Font.custom(_:size:relativeTo:)`.

## Format and lint

- For the formatter, use **swift-format** (`swift format`, `xcrun --find swift-format`), which ships in the Xcode 16+ toolchain. Configuration is a single `.swift-format` file (template: `profiles/frontend.swiftui/enforcement/swift-format.json.template`). ([Xcode 16 swift-format](https://mjtsai.com/blog/2024/11/06/swift-format-in-xcode-16/))
- Linting with SwiftLint is **optional**. Strata requires only a few `custom_rules`, so `check-swift-layers.py --style` runs the same regular expressions even without SwiftLint. If you use SwiftLint, merge `profiles/frontend.swiftui/enforcement/swiftlint-strata.yml.template` into `.swiftlint.yml`. ([SwiftLint custom rules](https://github.com/realm/SwiftLint#defining-custom-rules))

## Markers

Put them in `///` doc comments (`core/docs/en/conventions/strata-markers.md`):

```swift
/// Today state translation rules — pure functions only.
/// @strata:layer Contract
/// @strata:domain today
enum StateEngine { … }
```

## Tests

- A unit test target verifies Contract and DataState directly with `@testable import {App}`. A layer that has become a package is tested in the package's own test target. View tests verify the **Store → state → screen text** path, not snapshots.
- Isolate Store tests with `UserDefaults(suiteName: UUID)` or a temporary directory. Tests do not touch `.standard`.
- File names are `{Type}Tests.swift`, and the test target directory is excluded with `_test` in the layer-map. The checker silently skips files outside `swift.sources`.

## Brownfield adoption procedure

1. Create `.strata/layer-map.yaml` from `profiles/frontend.swiftui/enforcement/layer-map.yaml.template` (`variant: mobile`). Classify **by role** and do not move files. Write Feature domains as a `/` tree.
2. Bring unmapped files to 0 with `check-swift-layers.py --summary`.
3. Copy the per-target shared sources of `project.yml` into `targets.shared`. For DataState sharing, `stateful: true` + documentation.
4. Look at the violations with `--all`. Sort them into three — fix now / register in `exceptions` with a DEC / freeze with `--write-baseline` and block only new ones.
5. Turn on `--style` and repeat the same procedure.
6. Put `--all --style --ignore-known` in CI. The edit hook is `profiles/frontend.swiftui/enforcement/settings.json.template` (Write|Edit|Bash → stdin, `--changed` for Bash).
7. Climb the package ladder: design system → Contract → DataState. At each stage, update `swift.sources` and the mapping in the layer-map and regenerate the baseline.

## What this document does not decide

It does not decide an architecture pattern name (MVVM, TCA, Clean). Whatever name is used, it is enough that "Store is DataState, state ownership is the Feature Block, props views are Semantic, assembly is parent → child" is kept. The network layer and server-state cache tooling are also left as project constraints — but the Core rule is the same: transport is visible only inside DataState and is not exposed to views. For the Compose/Android binding, only the correspondence table in `core/docs/en/architecture/frontend-mobile.md` §Android exists, and there is no separate document yet.
