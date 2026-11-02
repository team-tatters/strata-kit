---
name: strata.translate
description: Use when a card, skill body, role text or document needs its other locales (en, ko, ja, zh, es, fr), when tools/i18n_check.py reports pending locales, or when the user says translate, localize, add Japanese. Keywords - translate, locale, i18n, pending locales, glossary.
---

# strata.translate

```yaml
skill:
  id: strata.translate
  version: '0.1'
  owner: supporter
  triggers:
  - i18n check reports pending locales
  - a new card, skill or document was written in one language
  - the user asks for a translation
  inputs:
  - the canonical text (en, or the authoring language)
  - i18n/glossary.yaml
  - LOCALES.md rules
  outputs:
  - locale map entries or i18n/<locale>.md bodies for the missing locales
  - unchanged identifiers, enums, keys and placeholders
  - an i18n check that passes with fewer warnings
  required_context:
  - LOCALES.md
  - i18n/glossary.yaml
  allowed_tools:
  - read
  - edit(locale fields and i18n bodies)
  - bash(tools/i18n_check.py)
  validation:
  - identifiers, enums, YAML keys and placeholders are byte-identical across locales
  - glossary terms are used consistently
  - no rule was added, removed or softened in translation
  - i18n check errors are zero and warnings decreased
  failure_modes:
  - 'the canonical text is ambiguous: ask one question instead of guessing in six languages'
```

## Overview

Fills the missing locales of cards, skill bodies, roles and documents from the canonical text, using the glossary, without changing meaning, identifiers or structure.

## When to use

When the i18n check reports pending locales, after new text is authored, or on request. Translate meaning; never translate identifiers.

## Process

1. Run tools/i18n_check.py and list the pending items. Evidence: the output.
2. Read the glossary and the canonical text. Evidence: paths.
3. Write each missing locale, keeping identifiers, enums, keys and placeholders identical; keep section order in skill bodies. Evidence: the diff.
4. Re-run the check; errors must be zero and warnings fewer. Evidence: the output.
5. Flag any sentence where the canonical text was ambiguous, with the question for the author.

## Rationalizations

| Thought | Rebuttal |
|---|---|
| "A rough translation is better than none." | A rough rule is a different rule. Translate precisely or flag. |
| "The identifier reads badly in the target language, I will localize it." | Identifiers are English by policy. Localize the label, not the id. |
| "Placeholders can move." | Placeholders must match exactly or the generator breaks. |

## Red flags

- A translated enum or key.
- A locale with an extra or missing sentence.
- Check warnings that did not decrease.

## Verification

- Identifiers identical.
- Check errors zero, warnings decreased.
- Ambiguities flagged.
