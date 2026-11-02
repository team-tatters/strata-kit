---
name: design.brief
description: Use when the person is about to design something — a document, a physical object, an image, a post, a screen; when the user says design, poster, layout, visual, mockup, banner, slide look, brief. The person's design stage: starts each piece of work from a brief (purpose, audience, medium, constraints, references, acceptance, deliverable) written in the person's words, with the taste and techniques it leans on. Independent of the frontend design contract; the deliverable reaches a product only through design_ref. Keywords - design, brief, poster, image, post, references, taste.
---

# design.brief

```yaml
skill:
  id: design.brief
  version: '0.5'
  owner: builder
  triggers:
  - the person is about to design something, in any medium
  - a specification or a release needs a document, an image, a post or a screen designed
  - the person wants to judge a design they made against what it was for
  inputs:
  - the person's request and the references they bring
  - the project's or brand's taste note and expression note (design.taste), when they exist
  - an external design skill the person has installed (Taste Skill, Impeccable), when they choose one for a web page or app screen
  - data/adapters.md — the category adapters and the common checks (DEC-2026-11-01-13)
  outputs:
  - 'a design brief (type: design-brief) — in projects/<p>/design/briefs/ for project work, otherwise in $STRATA_VAULT/designs/'
  - questions for the person, one at a time; their verdicts on the acceptance criteria
  required_context:
  - rec.process.confirm-before-state-change
  allowed_tools:
  - read
  - write(design brief, only with the person's words or text they approved)
  - 'bash(python3 -m kb search, python3 -m kb skills next)'
  validation:
  - the brief has its seven sections and a category; an unknown answer is written as unknown, not invented
  - the purpose says what is being designed (the category) before the one sentence it must convey
  - the purpose, the audience and the acceptance criteria are the person's words or text they approved
  - the references name what in each reference the person reacted to, not only its link
  - every acceptance criterion carries the person's verdict before the work is called done
  failure_modes:
  - 'the person wants the artefact now: write the brief in a few lines with them first; a design without a purpose and an audience cannot be judged'
  - 'the person asks the agent to choose the look: offer options labelled as the agent''s and let the person choose; do not record the agent''s choice as their taste'
```

## Overview

This is the person's design stage. Whatever is designed — a document, a physical object, an image, a post, a screen — the work starts from a brief: what it is for, who sees it, in what medium, under which constraints, with which references, and what must be true for it to be done. The brief is the person's; the agent asks and writes down, it does not decide taste. A design leans on the person's taste and on the techniques that express it (a glass surface, a raised soft shadow, a stack of borders and shades); the brief names the ones this work uses.

The frontend design contract (core/docs/<locale>/architecture/frontend-design-contract.md) is a separate thing: the technical flow that carries a decided design into code. This pack does not follow it and does not change it (DEC-2026-11-01-09). The two meet in one place: when a deliverable goes into a product, the contract points at it with `design_ref`. Translating the person's expression into the product's tokens is the implementation's work.

## When to use

The person is about to design something, in any medium; a specification or a release needs something designed; the person wants to judge a design against its purpose. Not for writing the specification (strata.spec) and not for implementing a screen (strata.build-task). Talking a design through is read-only; writing the brief raises the session to single-session (DEC-2026-11-01-18).

## Process

1. **Brief.** Ask, one question at a time, and write the seven sections: Purpose, Audience, Medium and format, Constraints, References, Acceptance criteria, Deliverable. The Purpose starts with what is being designed — a web page, an app screen, slides, a report, an infographic, a poster, an image or post, a physical object, or something else — written in the brief's frontmatter as `category` (`web`, `app`, `slides`, `report`, `infographic`, `poster`, `image`, `post`, `object`, `other`); then the one sentence this piece must convey; then the content in order — what must be there and what can go. The category decides the adapter at step 3. An unanswered section says unknown. Evidence: the brief and its category.
2. **References.** For each reference, ask what the person noticed first, what in it produces that, and whether it belongs in this work. Write their answer next to the link. When the project or brand has a taste note and an expression note (design.taste), name the taste lines (#tag) and techniques this work leans on. A reaction or rejection the person approves as written goes to the taste note as a signal from this brief, through design.taste. Evidence: the References section.
3. **Make or commission.** The person designs, or the agent drafts within the brief. Options the agent offers are labelled as the agent's; the person chooses. Read the adapter for the brief's category in `data/adapters.md`: slides, reports and infographics take the document adapter (argument, action titles, chart and structure choice); web and app take an external design skill when the person chooses one, otherwise the short fallback there — never both. When the deliverable is a web page or an app screen and the person wants it, use a design skill they already have installed — for example Taste Skill (Leonxlnx/taste-skill, `design-taste-frontend`) or Impeccable (pbakaus/impeccable); ask which, never install one yourself. Hand it the brief's purpose, audience and constraints, and the project's or brand's primitives and techniques when they exist (Taste Skill: `--keep palette,type`; Impeccable: its `DESIGN.md`). What that skill picks is an option on the agent's side, not the person's taste; the brief's acceptance criteria and the person's verdict still decide (DEC-2026-11-01-12). Evidence: the drafts, the skill used if any, and the person's choice.
4. **Judge.** Offer the common checks in `data/adapters.md` as candidate acceptance criteria, as the agent's suggestions; only those the person picks join the criteria. The person judges each acceptance criterion; write their verdict. A criterion that fails sends the work back to the step that caused it — purpose, content order, hierarchy, layout, values or focus — not only to the spot that shows it. Point at the result in the Deliverable section with `design_ref` (`kind`, `ref`, `version`). When the result goes into a product, that `design_ref` is where the product's own process takes over. Evidence: the verdicts and the reference.
5. **Next.** `python3 -m kb skills next design.brief`: design.taste when the work produced reactions or rejections to record, strata.order when the deliverable goes into a product, strata.review, or nothing.

## Rationalizations

| Thought | Rebuttal |
|---|---|
| "It's just a poster; a brief is overkill." | Five lines are enough. Without a purpose and an audience nobody can say whether it is done. |
| "I know what looks good here." | That is the average of what the model has seen. The person's reaction to their references is the taste; ask for it. |
| "The reference link is enough." | A link does not say what mattered. Write what the person reacted to. |
| "The product's token rules should shape this." | Not here. The contract takes the deliverable at design_ref; the implementation translates. |
| "Medium and format already says what it is." | That section holds size and file type. What is being designed decides the adapter and the external skill; ask it first. |
| "The adapter has good defaults; I'll apply them." | They are craft checks and starting points, not the person's look. Their references and taste come first. |

## Red flags

- An artefact delivered with no brief.
- A purpose, an audience or an acceptance criterion the person never said.
- References listed as bare links.
- The agent's choice of look recorded as the person's taste.

## Verification

- The brief has seven sections in the person's words, unknowns marked, and a category.
- Each acceptance criterion carries the person's verdict.
- The Deliverable section points at the result with design_ref.
