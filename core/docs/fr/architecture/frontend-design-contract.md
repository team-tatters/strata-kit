# Contrat de design du frontend (Design Contract)

> Canonique : strata-kit `core/docs/fr/architecture/frontend-design-contract.md` — migré depuis strata `docs/03-architecture/frontend-design-contract.md` (ordre 2026.10.29-06, 2026-10-29). Le YAML des règles se trouve dans `core/rules/`.

> Règles lisibles par machine : `core/rules/layer-rules.yaml` → `frontend.variants.web` (Foundation · Primitive_UI · Semantic_Component),
> `core/rules/naming-convention.yaml` → `frontend.Foundation.token_alias` · `markers.token_exception`
> Ce document définit le **contrat vérifiable** entre le design (tokens, variantes, composition) et l'implémentation.
> Il ne suppose aucun outil de design, outil CSS ni bibliothèque d'UI en particulier. Les liaisons avec les outils sont dans `profiles/frontend.next-web/docs/fr/frontend-tokens.md`.

## Principe de frontière

Core ne répond qu'à deux questions : « que fait ce composant » et « où se décide l'apparence de ce composant ».
« À quoi cela ressemble » doit être dérivé d'une combinaison de tokens et d'axes de variante, et ne doit pas être décidé directement dans le code du composant.

Le seul mot « token » mélange trois concepts. Nous les séparons.

| Concept | Définition | Où il vit |
|---|---|---|
| Token | Le système de valeurs : valeurs brutes (primitive) et intentions (alias) | Foundation |
| Variant | Les axes qu'un composant expose (variant · intent · size · state) | Primitive UI |
| Composition | La façon dont les composants sont combinés. Exprimée par un **contrat** (nom = sens, props = intention, slots), et non par la taille | Semantic Component · Feature Block |

## Trois niveaux de tokens

| Niveau | Rôle | Exemple de nom | Références autorisées | Outil de design |
|---|---|---|---|---|
| T1 Primitive | Valeurs brutes : échelles de palette, espacements, typographie | `cool-neutral-30` · `blue-80` · `space-4` | T2 uniquement. Les références depuis les composants sont interdites | Collection de variables « Primitive » |
| T2 Alias | Intention. **Le seul vocabulaire partagé par les agents, les designers et le code** | `color.surface.default` · `color.text.muted` · `color.action.primary.bg.hover` · `color.status.pending.fg` | Primitive UI · Semantic · Feature | Collection de variables « Semantic » (modes : light/dark/density) |
| T3 Component | Override par composant. Généré et facultatif. Pointe vers un alias T2, jamais vers une valeur raw | `button.solid.primary.bg` | Uniquement le composant qui le possède (et ses éléments internes) | Non conservé par défaut |

**Nommage des alias** : `{category}.{object}.{role}.{state?}` — category (color · space · radius · shadow · typography), object (surface · text · border · action · status · …), role (default · muted · bg · fg · …), state (hover · active · disabled · …).
Les modes (clair, sombre, densité) divergent dans la **couche de valeurs** de l'alias, tandis que le nom reste unique.

**Règles**
- T1 n'est référencé que depuis T2. Un nom T1 qui apparaît dans le code d'un composant est une violation.
- Un token de composant T3 n'est référencé que par le composant qui le possède (et ses éléments internes), et il pointe vers un alias, jamais vers une valeur raw. Quand un autre composant ou un autre écran a besoin de la même valeur, promouvez-la en alias.
- Les valeurs raw (hex · px · rgba · noms d'échelle de palette) sont interdites en dehors de Foundation, propriété de design par propriété de design : couleur, espacement, taille de police et hauteur de ligne, rayon, ombre, z-index. Les valeurs calculées ou mesurées à l'exécution (décalages de défilement virtuel, largeurs de référence mesurées, largeurs de colonnes de données et autres dimensions continues de ce type) sont admises comme exceptions marquées `@strata:computed <reason>` (sans expiration ; une raison vide ne compte pas). Une valeur arbitraire qui référence une variable d'alias n'est pas une valeur raw. Les noms de classes CSS utilitaires doivent refléter tels quels les noms d'alias.
- Ajouter un nouvel alias est une décision d'architecture — un enregistrement de décision est requis (`@strata:token-exception` est une échappatoire temporaire avec expiration, voir §Politique d'exception ci-dessous).

## Axes de variante

Primitive UI expose quatre axes. **N'utilisez pas de noms de palette comme valeurs d'un axe** — les valeurs se définissent par « ce que cela signifie », et non par « à quoi cela ressemble ».

| Axe | Valeurs (vocabulaire par défaut) | Remarque |
|---|---|---|
| `variant` | solid · outline · subtle · clean | Forme |
| `intent` | primary · neutral · danger · success · warning · info | Intention. Un projet peut étendre un axe d'état de domaine (par exemple `status: pending · completed`) comme **axe séparé**. Ne le mélangez pas dans le même axe |
| `size` | sm · md · lg | Un projet peut redéfinir les valeurs |
| `state` | default · hover · focus · active · disabled | État d'interaction. Les **états de données** (loading · empty · error) commencent au niveau Semantic Component |

Les noms de propriétés du composant dans l'outil de design et les noms de props dans le code doivent être **identiques**. C'est la prémisse du contrôle d'alignement.

## Composition Legality — légalité de la composition

> L'apparence d'un Semantic Component et d'un Feature Block doit être une **fonction pure de (les valeurs des axes de variante du Primitive UI sous-jacent) × (tokens Alias)**.

Ici, « apparence » désigne les propriétés visuelles propres au composant : couleur, typographie, espacement interne (padding), bordure et aspect de chaque état. Le placement entre composants, la marge extérieure, le viewport et le comportement responsive, ainsi que le contenu et les assets, sont hors du champ de cette règle ; ils relèvent des éléments de layout (grille, stack, etc.) que le parent place. C'est ce périmètre que mesurent les contrôles de valeurs raw et de palette.

Cette seule ligne remplace le Molecule/Organism d'Atomic Design (une classification par taille). La composition se juge par sa légalité, non par sa taille.

| Verdict | Exemple |
|---|---|
| Légal | `<Button intent="danger" variant="outline">` + `color.text.muted` · une valeur arbitraire qui référence une variable d'alias · une largeur mesurée à l'exécution accompagnée d'un commentaire de raison |
| Violation | `bg-blue-80` (référence directe à T1) · `style={{color:'#303140'}}` (valeur raw) · `className="bg-[#fff]"` (valeur arbitraire) |

La correspondance avec la variante Atomic suit le §Correspondance de `core/docs/fr/architecture/frontend-atomic.md`. En bref : Atom → Primitive UI, Molecule → Semantic Component (indifférent aux données) ou Feature Block (appelle DataState), Organism supprimé, Partial → Feature Block (Section).

## Artefacts de design et alignement

Une fonctionnalité a trois artefacts. Chacun a une version, et **n'importe lequel** peut être le point d'entrée. La porte (gate) n'est pas un ordre mais un contrôle d'alignement entre paires.

| Artefact | Ce qu'il contient | Forme |
|---|---|---|
| Spec | Ce qu'il fait — exigences, comportement, états | spécification de tâche · KB specification |
| Design | À quoi cela ressemble | `design_ref` (ci-dessous) |
| Impl | Code | Dépôt |

**design_ref** (`core/docs/fr/methodology/task-spec-schema.md` → `inputs.design_ref`)

| kind | Signification |
|---|---|
| `figma` | Référence à un fichier ou à un nœud de l'outil de design |
| `storybook` | Les stories sont l'artefact de design (canonique en l'absence d'outil de design) |
| `claude_design` | Canevas de brouillon. Artefact du point d'entrée `spec_first` ; promu en `storybook` ou `figma` une fois confirmé |
| `none` | Indique **explicitement** qu'il n'y a pas d'artefact de design — `reason` est obligatoire (par exemple outil interne, texte seul) |

**Définition de aligné (aligned)** : le contrat du composant — nom, axes de variante et valeurs, alias utilisés, axes d'état — est identique dans Design et Impl.
Les outils comparent à partir de cette définition (comparaison des noms de propriétés, rendu de la story comparé au frame). La revue humaine utilise la même définition.

**État d'alignement** (`completion.design_sync`)

```text
aligned   Le contrat Design ↔ Impl correspond
stale     Un côté a changé et doit être recontrôlé — on ne peut pas déclarer l'achèvement dans cet état
waived    Écart intentionnel. reason + until (date d'expiration) requis
none      Travail avec design_ref.kind: none
```

**Point d'entrée** (`_order.entry_point`)

```text
design_first   Design → (Design↔Spec) → Impl → (Impl↔Design)
dev_first      Impl → (Impl↔Spec) → Design(retrofit) → (Impl↔Design)
spec_first     Spec → Design·Impl en parallèle → les deux contrôles d'alignement
change         Un artefact quelconque change → les autres passent à stale → incomplet tant que l'alignement n'est pas rétabli   (par défaut)
```

La revue n'est pas une étape séparée mais **ce que déclenche chaque transition d'artefact**. L'ordre n'est pas figé.
L'indépendance de la vérification est définie par l'axe `design_verified` de `core/docs/fr/methodology/verification-tier.md`.

## Périmètre canonique de l'outil de design

Ce que l'on met dans l'outil de design (par exemple Figma) est volontairement restreint.

| Candidats canoniques | Références (non canoniques) | Ce qu'on n'y met pas |
|---|---|---|
| Variables de tokens T1·T2 (modes inclus) | Frames d'écran au niveau Feature | Logique de composition · flux de données · frontières de hooks |
| Composants Primitive UI et propriétés de variante | | Textes i18n (les clés vivent dans le code ; l'outil porte des annotations de clé) |
| Axes d'état des Semantic Component (loading · empty · error) | | Routage · frontières de permissions · valeurs brutes de layout |

**La source canonique des tokens est le fichier de tokens du dépôt de code** (recommandé). Raisons : les agents et la CI peuvent le lire de façon fiable, on peut en générer un catalogue d'alias qui tient dans le budget de contexte (`core/docs/fr/methodology/context-protocol.md` CB-1), et il ne dépend pas de l'accès à l'outil de design.
La synchronisation de l'outil de design vers le code est autorisée, mais les conflits se résolvent par un enregistrement de décision. Le choix inverse (l'outil comme source canonique) est possible comme décision dans le profile du projet.

**Il n'y a qu'un seul point de résolution des tokens** — l'étape de build de Foundation (fichier de tokens → variables CSS · constantes TS · variables de l'outil). Les composants référencent des noms d'alias ; un token de composant n'est référencé que par le composant qui le possède.

## Quand il n'y a pas d'outil de design

Il n'y a qu'une règle — **Primitive UI et Semantic Component ont des stories.** Sans outil de design, la story est le `design_ref` ; dès qu'un outil existe, cela mène à un contrôle d'alignement story↔outil.
La sortie d'un outil de brouillon (comme Claude Design) ne sert de `design_ref` que jusqu'à sa confirmation, et est promue à la confirmation.

## Politique d'exception

Quand une valeur ponctuelle introduite par un designer ne peut pas s'exprimer comme alias :

1. **Promouvoir** — ajouter un nouvel alias avec un enregistrement de décision. La PR qui modifie le fichier de tokens référence l'id DEC.
2. **Étiquette d'exception** — `@strata:token-exception {reason} until {YYYY-MM-DD}`. Le contrôle échoue à l'expiration. La syntaxe est dans `core/docs/fr/conventions/strata-markers.md`.
3. **Mesurer** — maintenir à 0 le nombre de valeurs raw hors de Foundation, mesuré par diff et compté par propriété de design (`profiles/frontend.next-web/enforcement/`).

Les valeurs calculées ou mesurées à l'exécution (décalages de défilement virtuel, largeurs de référence mesurées, largeurs de colonnes de données et autres dimensions continues de ce type) ne sont pas des valeurs de design ponctuelles. Elles restent dans le code comme exceptions, chacune marquée `@strata:computed <reason>`, et ne sont pas comptées comme valeurs raw. Les valeurs de design ponctuelles utilisent `@strata:token-exception`, qui expire.

## Séparation Core / Convention / Profile

| Nature | Emplacement | Exemple |
|---|---|---|
| Contrat vérifiable | Ce document · `core/rules/layer-rules.yaml` · `core/rules/naming-convention.yaml` | Les composants référencent des alias (les tokens de composant uniquement depuis leur propriétaire), la définition de l'alignement, l'enum des points d'entrée |
| Liaison avec les outils | `profiles/frontend.next-web/docs/fr/frontend-tokens.md` · `profiles/frontend.next-web/docs/fr/frontend-styling.md` | Format du fichier de tokens, générateur, correspondance des classes CSS utilitaires, outil de stories |
| Politique du projet | Tier P du projet (`layer-map.yaml` · decisions) | Chemin du fichier de tokens, axes d'extension d'intent, direction canonique, intensité d'application par zone |
