# Category adapters (DEC-2026-11-01-13)

design.brief reads this file at the make step, by the brief's `category`. These are craft rules, not taste: they
never replace the person's references, taste lines or acceptance criteria, and a number here is a starting point
the brief or the expression note may override. What the agent draws from them is an option on the agent's side.

Which adapter applies:

| category | adapter |
|---|---|
| `slides`, `report`, `infographic` | the document adapter below, in full |
| `web`, `app` | an installed external design skill when the person chooses one (Taste Skill, Impeccable) — then nothing below applies; otherwise the short fallback below |
| `poster`, `image`, `post`, `object`, `other` | the common checks only |

## Common checks (every category)

Offered at the judge step as acceptance-criterion candidates; only those the person picks become criteria.

- One focus per screen, page or slide; the rest is quieted rather than everything emphasised.
- Three-second test: someone seeing it first can say the first thing it tells them.
- Greyscale test: the hierarchy still reads in black and white.
- Contrast: body text 4.5:1, large text (18pt, or 14pt bold) and UI parts 3:1 (WCAG 2.2 AA). Computable as a relation
  in the expression note: `contrast(a, b[, on]) >= 4.5`.
- The accent carries one meaning on a screen or page; status colours are not the accent.
- Meaning is never carried by colour alone (add a word, an icon or a pattern).
- Same role, same style; elements sit on shared lines; space inside a group is smaller than space between groups.
- Values come from the expression note's primitives, not typed ad hoc.
- Blur test: blurred, the focus is still where it should be.

When a criterion fails, go back to the step that caused it — the message (purpose), the content order, the
hierarchy, the layout, the values or the focus — not only to the pixel that shows it.

## Document adapter — slides, reports, infographics

The fixed page and the line of argument are the constraint; visuals are evidence for a claim, not decoration.

| Aspect | Rule |
|---|---|
| Argument | Pyramid: conclusion, then about three supports, then data. The table of contents alone carries the conclusion. |
| Titles | Action titles: the conclusion as a sentence ("Q3 revenue rose 18% on the new channel"), not a topic ("Revenue"). |
| Grid | 16:9 slides on 12 columns, a fixed title band, margins 5–8% of the width. |
| Hierarchy | One message per slide or page: title, then the key visual, then the supporting note. |
| Colour | Data in greys; only the value tied to the conclusion takes the accent. |
| Data ink | Drop grid lines, borders, 3D and legends where a direct label works. |
| Icons | One style (stroke weight, filled or not) across the piece. |
| Type | Body 14–18pt; titles at least twice the body. |

Chart by what it says:

| What it says | Chart |
|---|---|
| Change over time | Line |
| Comparison of items | Horizontal bars, sorted largest first |
| Parts of a whole | 100% stacked bar; a donut only for three parts or fewer |
| What moved a total | Waterfall |
| Relation of two variables | Scatter |

Infographic structure by content:

| Type | Use | Layout |
|---|---|---|
| Flow | Procedures, processes | Steps left to right or top to bottom, with arrows |
| Comparison | Alternatives, before and after | Two symmetric columns |
| Hierarchy | Organisations, classifications | Tree or pyramid |
| Time | History, roadmap | Timeline with milestones |
| Figures | Key metrics | A large number and a short line of context |

## Web — short fallback (only when no external design skill is used)

- Columns 12 / 8 / 4 (desktop / tablet / phone); body line 65–75 characters.
- Information pages scan in an F (left-aligned, scannable subheads); landing pages run a Z (mark, call to action,
  visual, call to action).
- One message in the hero, three to five supporting sections, one primary call to action per screen.
- Fluid type with `clamp()`; motion only to show an order of reveal, and honour `prefers-reduced-motion`.

## App — short fallback (only when no external design skill is used)

- 8pt grid, side margins 16–20pt, safe areas respected.
- Touch targets at least 44pt (iOS) and 48dp (Android); the main action within thumb reach.
- One purpose per screen; follow the platform's navigation (tab bar of three to five) and transitions.
- Type follows Dynamic Type and Android font scaling; loading, success, error and empty states are designed.

## Source

Condensed from the person's document "디자인 스킬: 공통 코어와 카테고리 어댑터" (claude.ai, 2026-11-01, rev 11). Its
mind map moved to design.taste as an interview frame; its reference brands are interview material, not defaults.
