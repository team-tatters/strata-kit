---
name: design.taste
description: Use when the person reacts to references, picks or rejects a look, or wants their design taste for a project or brand written down; when the user says taste, I like this, not this, why does this feel right, our look, style, glass, soft shadow, colour relation. Keeps one taste note and one expression note per project or brand — signals in the person's words, inferences marked, promotion only by the person after three different briefs; techniques written as primitives and computed relations. Keywords - taste, reference, reaction, rejection, promote, expression, technique, primitives.
---

# design.taste

```yaml
skill:
  id: design.taste
  version: '0.2'
  owner: builder
  triggers:
  - the person reacts to a reference, or picks or rejects a look, while designing
  - the person wants the taste of a project or a brand written down or revisited
  - a technique (a glass surface, a raised soft shadow, a stack of borders) must be written so it can be checked
  inputs:
  - the person's words and the references they bring
  - the project's or brand's taste note and expression note, when they exist
  - the briefs the signals come from (design.brief)
  outputs:
  - 'a taste note (type: design-taste) — projects/<p>/design/taste.md, or $STRATA_VAULT/designs/<brand>/taste.md'
  - 'an expression note (type: design-expression) beside it — primitives and one section per technique'
  - promotion candidates shown to the person, and the person's choice for each
  required_context:
  - rec.process.confirm-before-state-change
  - rec.data.soft-delete-only
  allowed_tools:
  - read
  - write(taste and expression notes, only with the person's words or text they approved)
  - 'bash(python3 -m kb taste check, python3 -m kb taste expression, python3 -m kb skills next)'
  validation:
  - every signal and rejection line quotes the person and names the brief it came from
  - every line the agent inferred sits in the inference section and is marked [추론]
  - a taste line exists only after the person promoted it, with three different briefs as its evidence
  - every technique references primitives by name and carries at least one relation; `kb taste expression` reports 0
  failure_modes:
  - 'the person asks the agent what their taste is: show the signals and candidates, then ask; an answer the agent proposes goes to the inference section, never to taste'
  - 'the work belongs to no project or brand yet: ask which one it is for; do not create a note for the person as a whole'
```

## Overview

Taste is a record of judgements, not a style the agent picks. This skill keeps that record for one project or one brand — never for a person as a whole, because taste is judged in the context the work sits in (DEC-2026-11-01-10). The taste note has four sections: taste (lines the person promoted), signals (reactions and picks), inferences (what the agent guessed, marked), rejections (what the person turned down and why). A tag that turns up in three different briefs becomes a promotion candidate; the person decides. The expression note writes how the taste looks: primitives (colour, blur, opacity, spacing, radius, type) once, and each technique as a readable paragraph with a YAML block of layers and relations — lighten and darken in OKLCH lightness, opacity, WCAG contrast — that `kb taste expression` computes (DEC-2026-11-01-11).

The procedure takes its shape from skeltonmedia/design-taste-skills (MIT; see the pack NOTICE — not Taste Skill, a different repository): interview over references, a rejection log, promotion only of recurring signals, inferences marked. The text and checks here are strata's own.

## When to use

While the person designs and reacts to something; when a project or brand needs its taste written down or revisited; when a technique must be written so it can be checked. Not for the brief itself (design.brief) and not for a product's tokens or component contract — that is the implementation's translation. Reading a taste note is read-only; writing a signal, an inference or a technique raises the session to single-session (DEC-2026-11-01-18).

## Process

1. **Find the note.** Ask which project or brand this is for. Open its taste note and expression note, or offer to create them from the pack's example; run `python3 -m kb taste check <taste.md>` and show the candidates. Evidence: the paths and the check output.
2. **Interview, one question at a time.** For each reference: what did you notice first, what in it produces that, does it belong here. Write the answer as a signal: `- YYYY-MM-DD 반응|고름 #tag [[brief]] — "their words"`. When the person starts from a value rather than a reference (a brand's core value, a word like "trust"), use five axes as the frame — shape, colour, feeling, texture, object — and ask for one association and one visible cue on each; the person's cues are signals, any association the agent adds is an inference. Narrow to about three keywords that do not clash only with the person; when two clash, ask which leads and which stays in the small accent share (DEC-2026-11-01-13). Evidence: the new signal lines, read back to the person.
3. **Rejections.** When the person turns something down, ask why and write `- YYYY-MM-DD #tag [[brief]] — "their words" — 이유: …`. A rejection without a reason is a question still open. Evidence: the rejection lines.
4. **Inferences.** Anything the agent concludes from the signals — "seems to prefer quiet colours" — goes to the inference section as `- [추론] #tag … — YYYY-MM-DD`, and is shown to the person as the agent's reading. Evidence: the marked lines.
5. **Promotion.** For each candidate the check shows (three different briefs; repeats inside one brief count once), show its signals and ask: promote, hold, or drop. Only on promote, write `- #tag <the person's sentence> — 승격 YYYY-MM-DD · 근거 [[a]] [[b]] [[c]]`. Never promote from one striking reaction. Evidence: the person's choice and the check passing.
6. **Expression.** When the person names how something should look, write or update primitives, then the technique: a paragraph in their words, a YAML block that references primitives by name only, layers, and the relations that hold the judgement (the edge is lighter than the page; text reads at 4.5:1 over the glass, large text at 3:1). For work that has no product contract (slides, posters, reports), a technique may name roles as derived values — `text.primary: color.ink`, `accent: color.accent` — so a brief can point at roles; component values stay with the product's contract. Run `python3 -m kb taste expression <expression.md> --show` and read the computed values back. Evidence: 0 problems and the values.
7. **Next.** `python3 -m kb skills next design.taste`: design.brief to start a piece of work that leans on these lines, or nothing.

## Rationalizations

| Thought | Rebuttal |
|---|---|
| "They clearly love this; I'll write it as their taste." | One reaction is a signal. Taste is what holds across three different pieces of work, and the person promotes it. |
| "I can tell their style from the references." | That is an inference. Write it marked, show it, let them correct it. |
| "A hex value is clearer than a name." | A raw value hides the judgement. Name the primitive and write the relation that makes it right. |
| "Let's keep one taste file for the person; it's simpler." | Taste is judged in a project's or brand's context. A shared note mixes judgements made for different things. |
| "They rejected it; the reason is obvious." | Ask. The reason is what makes a rejection reusable. |

## Red flags

- A taste line with no promotion date or fewer than three briefs behind it.
- An agent inference written outside the inference section or without its mark.
- A signal paraphrased instead of quoted.
- A technique with raw colour values or no relation.
- A taste note for a person rather than a project or brand.

## Verification

- `python3 -m kb taste check <taste.md>` reports 0; candidates were shown and the person chose for each.
- `python3 -m kb taste expression <expression.md>` reports 0 for every technique touched.
- Every new line is the person's words or text they approved, read back to them.
