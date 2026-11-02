# Frontend Token Convention

> Canonical source: strata-kit `profiles/frontend.next-web/docs/en/frontend-tokens.md` — migrated from strata `docs/05-conventions/frontend-tokens.md` (order 2026.10.29-06, 2026-10-29). Rule YAML lives in `core/rules/`.

> Core contract: `core/docs/en/architecture/frontend-design-contract.md`

This document is the convention that maps the three token tiers (Primitive → Alias → Component) onto files, builds and utility CSS.
A project may change the format and tools; if it does, record that in the project profile, not here.

## Canonical file

- Location: a single file inside the Foundation package (for example `tokens/tokens.json`).
- Format: W3C Design Tokens (DTCG) JSON is recommended — it supports `$value`, `$type` and alias references (`{color.blue.80}`), and design-tool sync plugins read it.
- Keep both T1 and T2 in one file, separated by top-level groups (`primitive.*`, `alias.*`). T3 is `component.*`, only when needed.
- Modes are expressed on the alias value with `$extensions.modes` or in a separate mode file. The name is one, regardless of mode.

```json
{
  "primitive": { "color": { "blue": { "80": { "$type": "color", "$value": "#1b4380" } } } },
  "alias": {
    "color": {
      "action": { "primary": { "bg": { "default": { "$value": "{primitive.color.blue.80}" } } } },
      "surface": { "default": { "$value": "{primitive.color.common.0}" } }
    }
  }
}
```

## Outputs (resolved only at the build stage)

| Output | Consumer | Notes |
|---|---|---|
| CSS variables (`--color-action-primary-bg-default`) | Utility CSS · runtime theme | Expose aliases only. T1 variables are hidden behind an internal prefix or not generated |
| TS constants (`tokens.color.action.primary.bg.default`) | Wherever a style object is needed | Types are derived from the alias path |
| Design-tool variables | Designers | Sync tool (for example Tokens Studio · Variables API) — the direction is decided by the profile |
| **alias catalog** (`tokens.md`, generated) | Agents · reviewers | One line each for name, meaning and usage. Keep it small enough to fit in the T0 context budget |

Component code uses only the **alias names** of the outputs. It does not import the token file directly or compute values.

## Utility CSS mapping

Utility classes are a delivery vehicle for aliases. A class name mirrors the alias path as is.

| Allowed | Forbidden |
|---|---|
| `bg-surface-default` · `text-muted` · `border-status-pending` | `bg-blue-80` (T1) · `bg-[#1b4380]` (arbitrary value) · `text-[13px]` |

Theme configuration (for example Tailwind `@theme` or a preset) is an output and is not hand-edited. Not generating T1 utilities (`bg-blue-80`) is the simplest enforcement.

## Stories (canonical when there is no design tool)

- Primitive UI: at least one story per component, exposing every variant · intent · size combination in a table.
- Semantic Component: one story for each data-state axis (default · loading · empty · error).
- Foundation: provide alias catalog stories (color · spacing · shadow · typography) — a screen designers use to review without a tool.

## Checks

| Check | Method | Location |
|---|---|---|
| Raw values outside Foundation | New-line diff check — hex · rgba · px literals · `[…]` arbitrary values · T1 class patterns | `profiles/frontend.next-web/enforcement/diff-rules.json.template` |
| Exception expiry | Parse `@strata:token-exception … until YYYY-MM-DD`; fail once today is past that date | Same script |
| Token change approval | A PR with a token file diff carries a DEC id in its body | CI rule or PR template |

## Prohibitions

- Using T1 names, raw values or arbitrary values in components
- Hand-editing a theme in a way that bypasses the token file
- Putting palette names or screen names in alias names (`color.blue.button`, `color.dashboard.header`)
