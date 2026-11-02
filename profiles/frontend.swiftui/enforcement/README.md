# Swift/SwiftUI layer enforcement templates

These templates **read at run time** `layer-rules.yaml` (the Core source of truth) and the project's `layer-map.yaml`,
and check the layer dependency direction of the mobile variant. Same One Fact in One File principle as the Kotlin
(ArchUnit) and TypeScript (dependency-cruiser) templates — when the rules change, the change applies without
regenerating anything. Core explanation: `core/docs/en/architecture/frontend-mobile.md`, binding: `profiles/frontend.swiftui/docs/en/frontend-swiftui.md`.

## Why Swift needs its own checker

Swift's `import` works per module (SwiftUI, Foundation, SPM packages). When file A in a target uses a type from
file B, nothing is left on the import line. Core's `check-layer-violation.py` reads imports, so for Swift it sees
none of the violations between files (o-rot measurement on 2026-09-10: 0 found in 90 files). So this template looks
at **type references** — it builds a symbol table from each file's top-level type declarations (`struct`, `class`,
`enum`, `protocol`, `actor`, `typealias`), treats a use of that name in another file as a reference, and compares it
with `can_reference`, `cross_reference` and `composition`.

## Enforcement ladder — the compiler is the source of truth

| Level | Covers | Strength |
|---|---|---|
| Local SPM packages (`Package.swift.template`) | Isolate Foundation, Contract, DataState and Primitive UI from the app. Direction between packages comes only from the `dependencies:` declaration | **Enforced by the compiler — source of truth** |
| Targets (project.yml) | Boundaries between app, widget, watch and tests. Sharing means adding the file to a target | Enforced by the compiler |
| **`check-swift-layers.py`** | Layer direction between files inside one module + domain isolation + Feature parent→child composition + target sharing | CI blocking |
| `--style` / SwiftLint custom_rules | New raw values, system fonts and `Color(hex:)` | CI blocking, recommended for new lines |
| Hook (stdin / `--changed`) | Live feedback while editing — **based on the git working tree**, so it also catches Bash edits | exit 2 → agent |

Each time a layer moves up into a package (design system → Contract → DataState), that boundary shows up as an
`import` and the Core hook takes it over; this checker's share shrinks to the inside of the app target.

## Files

| File | Role |
|---|---|
| `check-swift-layers.py.template` | The checker. No dependency besides PyYAML. `--summary` classification · `--all` everything · `--file` one file · `--changed` git changes · `--style` regex rules · `--write-baseline`/`--ignore-known` freeze · `--json` · stdin hook |
| `Package.swift.template` | Skeleton of one SPM package per layer — pins the dependency direction in the compiler through `dependencies:` |
| `swiftlint-strata.yml.template` | The same rules as `custom_rules`, for projects that use SwiftLint |
| `swift-format.json.template` | Settings for the swift-format built into Xcode 16+ (`.swift-format`) |
| `../../settings/project.swift.json.template` | Claude Code settings — PostToolUse `Write\|Edit\|Bash` → checker on stdin, TaskCompleted → xcodebuild test |

## Applying

1. `check-swift-layers.py.template` → the project's `tools/check-swift-layers.py` (drop the suffix). Keep the project copy identical to the template (diff 0).
2. `templates/strata-config/layer-map.frontend-swiftui.yaml.template` → `.strata/layer-map.yaml` (`variant: mobile`). Put the roots to check in `swift.sources`; classify `mappings` **by role** (keep the directories as they are); Feature domains form a `/` tree such as `today/mood`.
3. `python3 tools/check-swift-layers.py --project-root . --summary` — add mappings until nothing is unmapped.
4. Copy the sources each `project.yml` target shares into `targets.shared`. For DataState, set `stateful: true` and document that instances are separate.
5. `--all` lists violations. Sort them three ways: fix now / register in `exceptions:` with a DEC id / freeze with `--write-baseline .strata/known-violations.json`.
6. CI: `python3 tools/check-swift-layers.py --project-root . --all --style --ignore-known .strata/known-violations.json`.
7. Edit hook: put `templates/settings/project.swift.json.template` into `.claude/settings.json`. The checker reads `tool_name` from stdin: for Write/Edit it checks the one file in `file_path`, for Bash it falls back to `--changed`.
8. Package ladder: use `Package.swift.template` to move up in the order design system → Contract → DataState, and update `swift.sources`, mappings and the baseline at each step.

The rules are read from `$STRATA_KIT/core/rules/layer-rules.yaml` (default `~/workspace/strata-kit`). If they live
elsewhere, pass `--kit-root` or copy the rules to `.strata/layer-rules.yaml` (same lookup order as the Kotlin template).

## What counts as a finding

- A reference is the top-level type name of another file appearing in a file's body (comments and strings excluded). References inside the same file are ignored.
- If the same name is declared in two or more files, **no verdict** is given (a missed finding is preferred to a false one). Check symbol table clashes in the `--json` output.
- `@EnvironmentObject var x: TodoStore` is a reference to `TodoStore`. It is caught in Semantic Component.
- For layers with `cross_reference: false` (DataState, Feature Block), a different mapping `domain:` is a cross-reference violation. Without `domain:`, the domain is the path segment after `feature_root`.
- For layers with `composition: parent_child` (Feature Block), the reference passes when `my_domain` is a prefix of `t_domain` (`today` → `today/mood`). Child→parent and sibling references get "Compose from the parent domain" added to the violation message.
- Files in `targets.shared[]` must be in the variant's `targets.shareable_layers`. DataState only with `stateful: true` (`target_share` violation).
- `.swift` files outside `swift.sources` (test targets, token mirrors, etc.) are not checked, and the hook exits 0 quietly for them too.
- Types from external modules (`View`, `Color`, `HKHealthStore`) are not in the symbol table, so they are not checked. Forbidden framework imports (SwiftUI in Contract, etc.) are caught by `style_rules`.
- The `naming:` block is not enforced (reference only).

## Limits (known going in)

- Only type names are seen. Method calls added in another file through an `extension` are not.
- Generic and nested types are caught only by their top-level name.
- It is regex based, so code inside macros and string interpolation can be missed. If precise analysis is needed, move to SwiftSyntax — methodology backlog MB-o-rot-2026-002.
- All of these limits matter only **inside one module**. Boundaries moved into packages are checked by the compiler.
