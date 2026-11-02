# Frontend Styling Convention

> Canonical source: strata-kit `profiles/frontend.next-web/docs/en/frontend-styling.md` — migrated from strata `docs/05-conventions/frontend-styling.md` (order 2026.10.29-06, 2026-10-29). Rule YAML lives in `core/rules/`.

> Core boundary: `core/docs/en/architecture/frontend-web.md` · Design contract: `core/docs/en/architecture/frontend-design-contract.md` · Token binding: `profiles/frontend.next-web/docs/en/frontend-tokens.md`

This document is the convention that maps styling tools onto the Core layers.
Core does not require any specific UI library or CSS tool.

## Layer Mapping

- Primitive UI decides its appearance using only alias tokens and the variant axes (`variant · intent · size · state`).
- A Semantic Component decides its appearance only through a combination of Primitive axis values and alias tokens (Composition Legality).
- A Feature Block is a screen fragment for a specific use case, and expresses layout through aliases too (space · radius).

## Axis value rules

- The value of a color axis is an intent (`intent`). Do not use palette names (`green · red · blue`) as axis values.
- If a domain status (for example `pending · completed`) is needed, do not mix it into `intent`; keep it as a separate `status` axis.
- Keep the component property names in the design tool the same as the props names in code — this is the premise of the consistency check.

## Project-Specific Mapping

Choices such as MUI, Tailwind, CSS-in-JS and design-system packages belong in the project profile or in a project-specific extension of this convention.
Whichever tool is used, the rule is the same: utility classes and style objects mirror alias names, and raw values and T1 names never appear outside Foundation.
That choice is a project constraint, not a Core rule.
