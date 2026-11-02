# TypeScript frontend layer enforcement templates

These templates **read `layer-rules.yaml` (the Core SoT) and the project's `layer-map.yaml` at runtime** to check
the direction of layer dependencies for the frontend web variant. The same One Fact in One File principle as the
Kotlin templates (`../kotlin/`) — when the rules change, the change takes effect without regenerating anything.

## Enforcement tiers

| Tier | Covers | Strength |
|---|---|---|
| Package boundaries (pnpm workspace + dependency-cruiser package rules) | dependency direction between apps and packages | CI blocking |
| **dependency-cruiser layer rules** (`depcruise-layers.cjs.template`) | import direction between layers (`can_reference`) | CI blocking (source of truth) |
| **diff rules** (`check-diff-rules.cjs.template` + `diff-rules.json.template`) | what static dependency analysis cannot catch — inline query keys, invalidation outside mutation hooks, banned hook prefixes and component suffixes, raw values for design properties, expired exceptions | CI blocking, **new lines only** |
| Hook (`kb check-layer`, `kb validate-naming`) | Live feedback while editing. It reads layer-map's `zones.legacy` (left out of the direction check, no warning), `exceptions` (valid unless `retired`; a reference let through is reported with the exception id) and `feature_root` (the Feature_Block domain; if absent, the prefix of layer-rules `domain_slice`) with the same meaning as CI, and warns when a newly defined hook name starts with one of the `forbidden_hook_prefixes` in `naming-convention.yaml`. The stack comes from `STRATA_PROJECT_TYPE`, or else layer-map `project_type` and `variant` | Resolves imports through relative paths, tsconfig `paths` and workspace packages (`exports`, `main`) down to the real file and picks the target layer from the layer-map mappings (the same way as CI; on a web monorepo baseline, 133 of 139 pairs agree). Non-code imports (CSS and so on) are not checked. **Only violations this edit adds** are blocked (exit 2) — violations already in the file are only reported. Naming gives warnings. The authoritative verdict is CI's |

## Files

| File | Role |
|---|---|
| `depcruise-layers.cjs.template` | Loader for layer-rules and layer-map. Rule generation is in `depcruise-layers.core.cjs.template` (a pure function — reproduces first-match-wins, allows references inside the same layer, leaves out the legacy zone, isolates by feature_root (or else the domain_slice prefix), an exception lifts only its one to_layer, transport (`*.service`) may be imported only by DataState (`layer:transport-adapter-only`, changed with layer-map `transport_pattern`), a target in no mapping gives a warn (`layer:unmapped-target`), `variant` or `frontend_variant`) |
| `check-diff-rules.cjs.template` | Script that applies regex rules to the added lines of `git diff`. The rules are kept apart in JSON |
| `diff-rules.json.template` | Default frontend rule set (see "What is checked" below) |

## How to apply

1. Copy the four template files (`depcruise-layers.cjs.template`, `depcruise-layers.core.cjs.template`, `check-diff-rules.cjs.template`, `diff-rules.json.template`) into one directory at the project root (or `scripts/`) and drop the `.template` suffix. If you only use the diff rules, the two files `check-diff-rules.cjs` and `diff-rules.json` are enough — the script reads `diff-rules.json` from its own directory (`--rules` changes that).
2. Put `layer-map.yaml` in the Tier P location (by default `.strata/layer-map.yaml`; for a detached project, the vault path). This profile has no web layer-map template yet — write one by hand with the web variant layers, using `profiles/frontend.swiftui/enforcement/layer-map.yaml.template` as a guide to the format. If the path differs from the default, point to it with the `STRATA_LAYER_MAP` environment variable.
3. `package.json`:
   ```json
   "depcruise:layers": "depcruise --config depcruise-layers.cjs apps shared",
   "check:diff-rules": "node check-diff-rules.cjs --base-ref main"
   ```
4. Add both commands to CI. If there are many existing violations, freeze the baseline with `--ignore-known` and block only new ones.
5. For the edit hook (after.file.change), use `check-diff-rules.cjs --file {path}` — it checks only the uncommitted changes of one file.

**Detached projects** (no Strata traces may be committed to the team repo): put the scripts, baseline and layer-map in the vault at `projects/{n}/strata/enforcement/`, and have a runner call `pnpm exec depcruise` from the repo root. To avoid depending on a YAML parser, the runner can make a JSON snapshot with Python and the loader reads the JSON (as done for a web monorepo).

## Strength per zone

Paths in `zones.legacy` of `layer-map.yaml` are **left out** of the dependency-cruiser rules and get only the diff rules.
`zones.target` (or a path in no zone) gets both. When a path has finished migrating, just remove it from legacy.

## Exceptions

Declare an intended allowance in `exceptions:` of `layer-map.yaml` together with a decision id. The dependency-cruiser rules leave out only that one `from_path → to_layer` — the other banned layers of the same file stay blocked. Expire it with `status: retired`.

## What is checked (default diff-rules set)

| Rule | Catches | Basis |
|---|---|---|
| `no-http-verb-hook` | `useFetch* · useGet* · usePost* · usePut* · usePatch* · useDelete*` | naming-convention `DataState.forbidden_hook_prefixes` |
| `no-forbidden-component-suffix` | new component declarations in `.tsx` and `.jsx` ending in `Block · Container · Partial` (`function`, `const`, `let`, `var`, `class`, a name carried onto the next line, an `export { X as …Block }` alias) — styled wrappers included. It misses destructuring and the second name in one declaration, and it also catches upper-case constants that are not components (a regex approximation). The edit hook warns on the same list | naming-convention `Feature_Block.forbidden_suffixes`, DEC-2026-11-01-19 |
| `no-inline-query-key` | a `queryKey: [` literal outside key factory files (`*.keys.ts`, `keys.ts`, `queryKeys.ts`) | frontend-query-state.md, DEC-2026-10-31-06 |
| `no-component-invalidate` | `invalidateQueries(` (in `.ts` and `.tsx`) outside mutation hook files (`use*Mutation`, `useMutation*`) and the `queryClient` / `query-client` files that hold the global MutationCache — inside a mutation hook, keys of other domains and exact detail keys are allowed too | frontend-query-state.md, DEC-2026-10-31-06 |
| `no-arbitrary-design-value` | raw arbitrary values (`p-[13px]`, `z-[60]`) in spacing (`p`, `m`, `gap`, `space`), font size (`text`), line height (`leading`), radius (`rounded`), shadow (`shadow`) and `z` utilities | frontend-design-contract.md, DEC-2026-10-31-05 |
| `no-arbitrary-color-value` | raw color arbitrary values in color utilities (`bg-[#fff]`, `text-[rgb(…)]`) | same |
| `no-raw-style-value` | numbers, hex, rgb or `px/rem/em` strings on design properties of a style object (color, margin/padding/gap, fontSize/lineHeight, borderRadius, boxShadow, zIndex) | same |
| `no-raw-css-value` | raw values in design property declarations in `.css` and `.scss` | same |
| `no-primitive-token-class` | T1 palette scale classes outside Foundation (`bg-blue-500` and so on; the project sets the palette names) | frontend-tokens.md |
| `token-exception-expiry` | expiry of `@strata:token-exception … until YYYY-MM-DD` — on every tracked line, not only added lines | core/docs/en/conventions/strata-markers.md |
| `no-any` | `any` on new lines | existing practice |

What the raw-value rules **do not catch**: arbitrary values that reference an alias variable (`bg-[var(--x)]`, `p-[--space-3]`, Tailwind v4 `p-(--space-3)`, `text-[length:var(--x)]`), the value `0`, computed geometry such as width, height and position (`w-[320px]`, `style={{ top: offset }}`), and `12px` in prose inside comments, JSX text or strings. When a design property takes a value computed or measured at runtime, put `@strata:computed {reason}` (no expiry) on the same line or the line just above; for a one-off design value, put `@strata:token-exception {reason} until YYYY-MM-DD` — a marker with an empty reason or a past date does not turn the violation off, and `computed` has no effect on palette classes (DEC-2026-10-31-05).

Rule option keys: `joinNext` (check the line joined with the next added line — a `queryKey:` broken across lines), `fileContains` (only when the file contains this expression — `no-inline-query-key-variable` catches a query key array built in a variable only in files that use `queryKey`), `scope: "tracked"` (every line of every tracked file — `token-exception-expiry` also catches expiry on unchanged lines). Limits that remain because these are regexes: a variable whose name has no "key" in it, and a key array imported from another file. Regression tests: `tools/tests/test_next_web_diff_rules.py` and `tools/tests/test_nextweb_enforcement.py` (fixtures run with real dependency-cruiser and node).
