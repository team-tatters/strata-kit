# Frontend Design Contract

> Canonical: strata-kit `core/docs/en/architecture/frontend-design-contract.md` — migrated from strata `docs/03-architecture/frontend-design-contract.md` (order 2026.10.29-06, 2026-10-29). The rule YAML is in `core/rules/`.

> Machine-readable rules: `core/rules/layer-rules.yaml` → `frontend.variants.web` (Foundation · Primitive_UI · Semantic_Component),
> `core/rules/naming-convention.yaml` → `frontend.Foundation.token_alias` · `markers.token_exception`
> This document defines the **verifiable contract** between design (tokens, variants, composition) and implementation.
> It assumes no particular design tool, CSS tool or UI library. Tool bindings are in `profiles/frontend.next-web/docs/en/frontend-tokens.md`.

## Boundary principle

Core answers only two questions: "what does this component do" and "where is this component's appearance decided".
"How it looks" must be derived from a combination of tokens and variant axes, and must not be decided directly inside component code.

The single word "token" mixes three concepts. We separate them.

| Concept | Definition | Lives in |
|---|---|---|
| Token | The value system: raw values (primitive) and intents (alias) | Foundation |
| Variant | The axes a component exposes (variant · intent · size · state) | Primitive UI |
| Composition | How components are combined. Expressed as a **contract** (name = meaning, props = intent, slots), not by size | Semantic Component · Feature Block |

## Three token tiers

| Tier | Role | Naming example | References allowed | Design tool |
|---|---|---|---|---|
| T1 Primitive | Raw values: palette scales, spacing, typography | `cool-neutral-30` · `blue-80` · `space-4` | T2 only. Component references are forbidden | Variable collection "Primitive" |
| T2 Alias | Intent. **The only vocabulary shared by agents, designers and code** | `color.surface.default` · `color.text.muted` · `color.action.primary.bg.hover` · `color.status.pending.fg` | Primitive UI · Semantic · Feature | Variable collection "Semantic" (modes: light/dark/density) |
| T3 Component | Per-component override. Generated and optional. Points to a T2 alias, never to a raw value | `button.solid.primary.bg` | Only the component that owns it (and its internals) | Not kept by default |

**Alias naming**: `{category}.{object}.{role}.{state?}` — category (color · space · radius · shadow · typography), object (surface · text · border · action · status · …), role (default · muted · bg · fg · …), state (hover · active · disabled · …).
Modes (light, dark, density) diverge at the alias **value layer**, while the name stays one.

**Rules**
- T1 is referenced only from T2. A T1 name appearing in component code is a violation.
- A T3 component token is referenced only by the component that owns it (and its internals), and it points to an alias, never to a raw value. When another component or screen needs the same value, promote it to an alias.
- Raw values (hex · px · rgba · palette scale names) are forbidden outside Foundation, applied per design property: color, spacing, font size and line height, radius, shadow, z-index. Values computed or measured at runtime (virtual scroll offsets, measured reference widths, data column widths and similar continuous dimensions) are allowed as exceptions marked `@strata:computed <reason>` (no expiry; an empty reason does not count). An arbitrary value that references an alias variable is not a raw value. Utility CSS class names must mirror alias names as they are.
- Adding a new alias is an architecture decision — a decision record is required (`@strata:token-exception` is a temporary escape hatch with an expiry, see §Exception policy below).

## Variant axes

Primitive UI exposes four axes. **Do not use palette names as axis values** — define values by "what it means", not "how it looks".

| Axis | Values (default vocabulary) | Note |
|---|---|---|
| `variant` | solid · outline · subtle · clean | Form |
| `intent` | primary · neutral · danger · success · warning · info | Intent. A project may extend a domain status axis (for example `status: pending · completed`) as a **separate axis**. Do not mix it into the same axis |
| `size` | sm · md · lg | A project may redefine the values |
| `state` | default · hover · focus · active · disabled | Interaction state. **Data states** (loading · empty · error) start at Semantic Component |

The component property names in the design tool and the props names in code must be **identical**. This is the premise of the alignment check.

## Composition Legality

> The appearance of a Semantic Component and a Feature Block must be a **pure function of (the variant axis values of the Primitive UI below it) × (Alias tokens)**.

Here "appearance" means the component's own visual properties: color, typography, inner spacing (padding), border and the look of each state. Placement between components, outer margin, viewport and responsive behaviour, and content and assets are outside this rule; they belong to layout elements (grid, stack and the like) that the parent places. This scope is what the raw-value and palette checks measure.

This one line replaces Atomic Design's Molecule/Organism (a classification by size). Composition is judged by legality, not by size.

| Verdict | Example |
|---|---|
| Legal | `<Button intent="danger" variant="outline">` + `color.text.muted` · an arbitrary value that references an alias variable · a runtime-measured width with a reason comment |
| Violation | `bg-blue-80` (direct T1 reference) · `style={{color:'#303140'}}` (raw value) · `className="bg-[#fff]"` (arbitrary value) |

The mapping to the Atomic variant follows §Mapping in `core/docs/en/architecture/frontend-atomic.md`. In short: Atom → Primitive UI, Molecule → Semantic Component (data-agnostic) or Feature Block (calls DataState), Organism retired, Partial → Feature Block (Section).

## Design artifacts and alignment

A feature has three artifacts. Each has a version, and **any of them** can be the entry point. The gate is not an order but an alignment check between pairs.

| Artifact | What it holds | Form |
|---|---|---|
| Spec | What it does — requirements, behavior, states | task spec · KB specification |
| Design | How it looks | `design_ref` (below) |
| Impl | Code | Repository |

**design_ref** (`core/docs/en/methodology/task-spec-schema.md` → `inputs.design_ref`)

| kind | Meaning |
|---|---|
| `figma` | Reference to a design tool file or node |
| `storybook` | Stories are the design artifact (canonical when no design tool exists) |
| `claude_design` | Draft canvas. The artifact of the `spec_first` entry point; promoted to `storybook` or `figma` once confirmed |
| `none` | **Explicitly** states there is no design artifact — `reason` is required (for example internal tool, text only) |

**Definition of aligned**: the component contract — name, variant axes and values, aliases used, state axes — is identical in Design and Impl.
Tools compare on top of this definition (property-name comparison, story render versus frame comparison). Human review uses the same definition.

**Alignment state** (`completion.design_sync`)

```text
aligned   Design ↔ Impl contract matches
stale     One side changed and needs re-checking — completion cannot be declared in this state
waived    Intentional mismatch. reason + until (expiry date) required
none      Work with design_ref.kind: none
```

**Entry point** (`_order.entry_point`)

```text
design_first   Design → (Design↔Spec) → Impl → (Impl↔Design)
dev_first      Impl → (Impl↔Spec) → Design(retrofit) → (Impl↔Design)
spec_first     Spec → Design·Impl in parallel → both alignment checks
change         Any artifact changes → the others become stale → incomplete until alignment is restored   (default)
```

Review is not a separate step but **something every artifact transition triggers**. The order is not fixed.
Verification independence is defined by the `design_verified` axis in `core/docs/en/methodology/verification-tier.md`.

## Canonical scope of the design tool

What goes into the design tool (for example Figma) is kept narrow.

| Canonical candidates | References (not canonical) | Not kept |
|---|---|---|
| T1·T2 token variables (including modes) | Feature-level screen frames | Composition logic · data flow · hook boundaries |
| Primitive UI components and variant properties | | i18n copy (keys live in code; the tool holds key annotations) |
| State axes of Semantic Components (loading · empty · error) | | Routing · permission boundaries · raw layout values |

**The canonical token source is the token file in the code repository** (recommended). Reasons: agents and CI can read it reliably, an alias catalog that fits the context budget (`core/docs/en/methodology/context-protocol.md` CB-1) can be generated from it, and it does not depend on access to the design tool.
Syncing from the design tool to code is allowed, but conflicts are resolved with a decision record. The opposite choice (tool as canonical) is possible as a decision in the project profile.

**There is one token resolution point** — the Foundation build step (token file → CSS variables · TS constants · tool variables). Components reference alias names; a component token is referenced only by the component that owns it.

## When there is no design tool

There is one rule — **Primitive UI and Semantic Component have stories.** Without a design tool, the story is the `design_ref`; once a tool exists, this leads to a story↔tool alignment check.
The output of a draft tool (such as Claude Design) serves as `design_ref` only until confirmed, and is promoted on confirmation.

## Exception policy

When a one-off value introduced by a designer cannot be expressed as an alias:

1. **Promote** — add a new alias together with a decision record. The PR that changes the token file references the DEC id.
2. **Exception tag** — `@strata:token-exception {reason} until {YYYY-MM-DD}`. The check fails on expiry. The syntax is in `core/docs/en/conventions/strata-markers.md`.
3. **Measure** — keep the number of raw values outside Foundation at 0 by diff, counted per design property (`profiles/frontend.next-web/enforcement/`).

Values computed or measured at runtime (virtual scroll offsets, measured reference widths, data column widths and similar continuous dimensions) are not one-off design values. They stay in code as exceptions, each marked `@strata:computed <reason>`, and are not counted as raw values. One-off design values use `@strata:token-exception`, which expires.

## Core / Convention / Profile separation

| Nature | Location | Example |
|---|---|---|
| Verifiable contract | This document · `core/rules/layer-rules.yaml` · `core/rules/naming-convention.yaml` | Components reference aliases (component tokens only from their owner), the definition of alignment, the entry point enum |
| Tool binding | `profiles/frontend.next-web/docs/en/frontend-tokens.md` · `profiles/frontend.next-web/docs/en/frontend-styling.md` | Token file format, generator, utility CSS class mapping, story tool |
| Project policy | Project Tier P (`layer-map.yaml` · decisions) | Token file path, intent extension axes, canonical direction, enforcement strength per zone |
