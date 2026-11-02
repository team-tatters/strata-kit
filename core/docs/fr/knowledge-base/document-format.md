# Knowledge Base — Format des documents

> Référence : strata-kit `core/docs/fr/knowledge-base/document-format.md` (migré le 2026-10-29 depuis strata `docs/07-knowledge-base/document-format.md`, DEC-2026-10-29-11).

## Aperçu

Tout fichier `.md` du vault doit contenir un frontmatter YAML.
On utilise un format que peuvent analyser à la fois Obsidian et le serveur MCP (Phase 3).

## Schéma du frontmatter

```yaml
---
# === Champs obligatoires ===
title: "Titre du document"
id: "{préfixe}-{project}-{slug}"  # ID stable — inchangé par les déplacements et les renommages (schéma des préfixes : section ID stable de core/docs/fr/knowledge-base/vault-structure.md)
type: overview | decision | session | pattern | reference | glossary
      | concept | specification | flow | guide | runbook | constraint | epic | moc | node
created: YYYY-MM-DD

# === Obligatoires sous condition ===
project: {project-name}       # Pour les documents propres à un projet (pour les documents transversaux, mettre vault à la place de project dans l'id)
status: draft | active | review-needed | superseded | archived
sources: ["[[session/tâche source]]"]  # Obligatoire lors de la mise à jour d'un document de la couche Knowledge (KB, pattern) — lien vers l'Archive qui sert de preuve (DEC-2026-08-19-03)
nodes: ["{node-id}"]          # Appartenance à un nœud thématique — obligatoire pour decision, session, specification, concept, constraint (section « Champs de nœud et de couverture »)

# === Champs facultatifs ===
tags: [namespace/value, ...]  # Tags avec espace de noms recommandés
updated: YYYY-MM-DD           # Date de dernière modification
updated_by: {git user}@{machine}  # Dernier auteur de la mise à jour — le hook d'écriture l'estampille avec l'identité git et l'alias de la machine (DEC-2026-09-09-05)
page_order: 1                 # Ordre du document dans la catégorie (pour l'index du KB)
author: builder | worker | manual  # Qui l'a rédigé
machine: {alias}              # Machine qui l'a rédigé (alias dans env-config.yaml)
superseded_by: "[[nouveau document]]"   # Quand status vaut superseded (côté remplacé → côté remplaçant)
supersedes: ["[[décision précédente]]"]   # decision — les décisions précédentes que celle-ci remplace (sens inverse de superseded_by)
covers: {paths, symbols, endpoints, tables}  # specification, concept — la surface de code dont ce document est la référence
doc_change: none              # session, task — déclare que le code a changé mais que la forme réalisée n'a pas été mise à jour (doc_change_reason obligatoire)
aliases: ["ancien nom de fichier"]         # Conserve l'identifiant d'origine en cas de déplacement ou de renommage
related: ["[[document lié 1]]"]     # Wikilink Obsidian — relation de mention (la relation de propriété est covers)
---
```

## Champs obligatoires par type

| type | Champs obligatoires supplémentaires | Description |
|---|---|---|
| `overview` | `project` | Aperçu d'un projet ou d'une catégorie |
| `decision` | `project`, `status`, `nodes` | ADR. Inclut le contexte et la justification de la décision. `supersedes` facultatif |
| `session` | `project`, `machine`, `nodes` | Passation de session / ledger. **Seuls les métadonnées et le résumé sont indexés** (Archive — 2026.08.19-06). `doc_change` facultatif |
| `pattern` | — | Pattern réutilisable à travers les projets |
| `reference` | — | Référence résumée d'un document externe, d'une norme ou d'une spécification |
| `glossary` | — | Définitions de termes du domaine ou techniques |
| `concept` | `nodes` | Concept du domaine, règle métier ou explication d'un principe. `covers` facultatif |
| `specification` | `status`, `nodes` | Spécification fonctionnelle, exigences, contraintes, critères d'acceptation. La forme finale d'un nœud. `covers` recommandé |
| `flow` | — | Processus métier, flux de données, séquence |
| `guide` | — | Guide de procédure, document How-to |
| `runbook` | `status` | Procédure d'exploitation / de réponse aux incidents |
| `constraint` | `source_adr`, `severity`, `scope`, `rule`, `verification`, `status`, `nodes` | Une contrainte unique et exécutable extraite d'un ADR |
| `epic` | `constraints`, `domains`, `layers`, `personas`, `status` | Unité fonctionnelle du PRD. Un lien vers une constraint est obligatoire |
| `planning` | `project`, `status`, `nodes`, `source`, `implementation` | Texte original de planification importé d'un outil de planification externe (PRD, politique, Epic/Story). Le texte original est immuable, plus une section `## Revue d'implémentation`. `implementation.status` classe le résultat de la revue. status est l'état de la planification (lifecycle_override) |
| `moc` | — | Table des matières (Map of Content). `_index/`, chaque `_index.md` et les index statiques générés. **Généré uniquement** |
| `node` | `project`, `node` | Page de nœud thématique. Joint la forme finale, les politiques, les décisions, la planification, l'historique de travail et la dette. **Généré uniquement** |

`moc` et `node` appartiennent à la couche Index. On ne les écrit pas à la main ; on les régénère à partir des sources de référence (frontmatter, enregistrements, toc.yaml).

## Champs de nœud et de couverture

Un nœud thématique (node) est l'unité de la table des matières que lisent les personnes. Un nœud est la clé qui rassemble sur un seul écran la forme finale (spécification), les politiques (contraintes), les décisions et l'historique de travail. La source de référence de l'arbre des nœuds est le `_meta/toc.yaml` du projet, et un document se relie aux nœuds et au code par les quatre champs ci-dessous. **Cette section est la source de référence des formats de valeur.** La taxonomy ne décide que du caractère obligatoire.

### `nodes` — les nœuds thématiques auxquels ce document appartient

```yaml
nodes: ["orders.checkout-v2.coupon"]   # ids de nœud définis dans toc.yaml ; plusieurs sont permis
```

- Un id de nœud vit dans un **espace de noms différent** de celui de l'id du document (`{préfixe}-{project}-{slug}`). C'est un chemin joint par des points (.) depuis l'ancêtre, et chaque segment est en kebab-case.
- Obligatoire pour decision, session, specification, concept et constraint. Les spécifications de tâche utilisent le même champ (voir `core/docs/fr/methodology/task-spec-schema.md`).
- Les nœuds des sessions et des tâches sont dérivés par le résolveur de couverture (fichier modifié → la spécification qui possède ce fichier → le nœud de cette spécification). Une personne ne les choisit que pour les sessions sans changement de code.
- Un tableau vide est permis, mais la validation avertit. Si l'absence de nœud est voulue, on laisse la raison dans le corps.

### `covers` — la surface de code dont ce document est la référence

```yaml
covers:
  paths: ["service/order-api/src/main/kotlin/com/example/order/refund/"]   # chemin relatif au dépôt, correspondance par sous-chaîne
  symbols: ["RefundCalculationService"]                              # nom de classe ou de fonction
  endpoints: ["POST /v1/orders/{id}/refunds"]                    # METHOD + préfixe de chemin
  tables: ["refund_items"]                                      # nom de table
```

- À utiliser uniquement dans specification et concept. Les sessions, décisions et contraintes n'ont pas de `covers`. Elles ne font que pointer vers un nœud par `nodes`.
- On n'utilise pas de chemins au niveau du fichier. On n'utilise que des identifiants stables face aux déplacements, comme un préfixe de module, de package, de contrôleur ou de route. La règle de correspondance est la même que celle des chemins du layer-map (sous-chaîne, de haut en bas).
- Une surface est possédée par exactement un document. En cas de chevauchement, la validation avertit. Un document de concept de niveau supérieur se relie avec `up`.
- `covers` est une relation de **propriété**, pas une mention. Les mentions vont dans `related`. Si cette distinction se brouille, cinq documents finissent par posséder un même fichier, et la porte de couverture (gate) devient du bruit qu'on ignore.
- Un pointeur vers un chemin de code ne contredit pas le principe de ne pas conserver de code source dans le vault. On n'enregistre que des chemins relatifs au dépôt, pas du code (`core/docs/fr/knowledge-base/vault-structure.md`, « Ce qui n'est jamais inclus »).

### `doc_change` — quand le code a changé mais que la forme réalisée n'a pas été mise à jour

```yaml
doc_change: none
doc_change_reason: "Refactorisation uniquement — aucun changement des contrats externes ni des politiques"
```

- Utilisé dans session et task. Si un chemin de `covers` a changé, que le document qui possède cette surface n'a pas été mis à jour et que ce champ est absent, la porte (gate) de fin de session l'enregistre comme **dette** de ce nœud et avertit.
- Une valeur vide est interdite. Si la valeur est `none`, une raison doit être jointe. C'est le même principe que celui du ledger, qui exige une raison pour `next: "none"`.

### `supersedes` — les décisions précédentes que cette décision remplace

```yaml
supersedes: ["[[DEC-2026-08-13-05]]"]
```

- Utilisé dans decision. **L'état du côté remplacé n'est pas stocké, il est dérivé** (DEC-2026-09-30-03) : une décision qui apparaît dans le `supersedes` d'un enregistrement reçoit automatiquement `status: superseded` et `superseded_by` dans l'index et dans la note DEC. Le fichier d'enregistrement du côté remplacé n'est pas modifié.
- Pour ajouter après coup une relation de remplacement à une décision déjà enregistrée, on utilise `python3 "$STRATA_KIT/kb" decision supersede --id nouvelle --target ancienne` ; pour retirer une décision sans décision qui la remplace, on utilise `python3 "$STRATA_KIT/kb" decision withdraw --id X --reason ...`. Écrire simplement « remplacée » ou « retirée » dans le corps n'est pas reconnu comme un état.
- Les documents du KB (autres que decision) portent toujours `status: superseded` et `superseded_by` écrits à la main du côté remplacé.
- `superseded_by` est le champ existant pour le sens inverse (côté remplacé → côté remplaçant). Les deux sont les deux extrémités d'un même fait.
- La facette « décisions » d'une page de nœud montre le bout de cette chaîne comme la décision en vigueur et le reste comme l'historique.

## Cycle de vie du document

```
draft → active → review-needed → superseded → archived
                      ↓                ↓
                   active           archived
```

| État | Signification | Transitions possibles |
|------|------|-----------|
| `draft` | En cours de rédaction, pas encore relu | active, archived |
| `active` | Document en vigueur et valide | review-needed, superseded, archived |
| `review-needed` | Mise à jour nécessaire (signalé automatiquement après 90 jours) | active, superseded, archived |
| `superseded` | Remplacé par un nouveau document. Le champ `superseded_by` est obligatoire. Si la décision remplaçante déclare `supersedes`, la paire est soumise à la validation de symétrie | archived |
| `archived` | N'est plus valide. Le poids dans la recherche est réduit | — |

**Exception selon le type** : `constraint` utilise son propre cycle de vie —
`active → superseded → retired` (taxonomy.yaml `lifecycle_override`).
Une contrainte est créée active au moment où son ADR est accepted, sans état draft, et son retrait est noté `retired`.

## Règles du corps

### Règles générales

- Format Markdown (CommonMark + extensions Obsidian)
- Les titres commencent à `##` (on évite `#` pour ne pas dupliquer le title du frontmatter)
- Un document se concentre sur un seul sujet (principe MECE)
- Longueur maximale : aperçu/pattern/concept 500 lignes, ADR 200 lignes, résumé de session 100 lignes, spécification 1000 lignes, tables des matières et pages de nœud 300 lignes
- La source de référence des titres des sections du corps est `document_types.{type}.body_sections` de la taxonomy. Les blocs de structure ci-dessous en sont un rendu, et le générateur construit les titres à partir de la taxonomy

### Règles de lisibilité (obligatoires)

- **Termes autosuffisants** : un document doit pouvoir se comprendre à la seule lecture de ce document. On n'emploie pas tels quels des termes dont le sens est inaccessible sans contexte technique extérieur — jargon technique anglais, concepts internes à l'implémentation ou mots composés inventés par l'auteur. S'ils sont vraiment nécessaires, on les **explique en une ligne à leur première apparition**. (Exemple : au lieu de mots comme « materialize », « resolve », « single-flight », « degraded », on **décrit l'action**, par exemple « on le construit à l'avance à la première requête » ou « on le consulte et on l'assemble ».)
- **Cohérence entre le corps et la conclusion** : les éléments « en suspens / à confirmer / réponses aux demandes » à la fin d'un document sont tirés uniquement de ce que le corps a réellement défini et développé. On n'introduit pas pour la première fois un nouveau concept dans la section de clôture. Le lecteur doit pouvoir retrouver, un à un, à quelle partie du corps se rattache chaque élément en suspens.
- **Critère de jugement** : « Un collègue de la même équipe qui découvre ce document peut-il, sans recherche extérieure, comprendre tous les termes et tous les éléments en suspens à partir du seul corps ? » Sinon, on détaille ou on ajoute le fondement au corps.

### Règles pour les documents lus par des personnes (obligatoires — DEC-2026-09-10-01)

Le lecteur est une personne. On n'écrit pas sous une forme commode à analyser pour un agent. Ces règles s'appliquent de la même façon aux documents du KB, aux passations de session, aux enregistrements de décision et aux rapports par chat.

- **N'utiliser que des mises en forme qu'une personne peut assimiler.** On n'écrit pas de paragraphes ni de tableaux dont le sens ne se comprend pas en une lecture. On n'énumère pas de symboles de code, de chemins ou d'IDs de décision à la place d'une explication. Un tableau contient un fait par cellule, et on ne met pas de tableau dans un tableau.
- **Interdire la duplication et la prolixité ; écrire dans un seul contexte.** On ne répète pas le même fait dans plusieurs sections. On garde un seul fil pour que le point de vue ne change pas d'une section à l'autre.
- **Le résumé d'abord, les justifications ensuite.** Quand l'exposé s'allonge, on place en tête un résumé de la conclusion, et on joint les emplacements dans le code, les valeurs mesurées et les citations dans une section de justifications placée après. Le lecteur doit pouvoir décider à partir du seul résumé.
- **Ne pas utiliser d'étiquettes d'ordre sous forme de code.** On ne classe pas les tâches, l'ordre des documents ou les éléments avec des codes combinant une lettre et un chiffre, comme `A1·A2·B3`. L'ordre et les éléments s'écrivent en phrases courtes dont le sens se voit. (Pas « A3 élagage du hub », mais « supprimer les écrans que le hub n'utilise plus ».) On n'ajoute l'étiquette d'origine entre parenthèses que lorsqu'on cite un document existant qui en porte déjà une.

### Structure du corps d'une Decision (ADR)

```markdown
## 맥락
{le contexte qui a rendu la décision nécessaire}

## 결정
{la direction choisie et la raison}

## 대안
{les directions envisagées mais non retenues, et pourquoi}

## 결과
{les effets de cette décision, les compromis}
```

Une décision qui déclare `supersedes` laisse dans `## Conséquences` une ligne disant ce qu'elle remplace et pourquoi. Quand une page de nœud montre la chaîne de décisions, cette ligne sert d'explication.

### Structure du corps du résumé de Session

```markdown
## 완료
- {élément terminé}

## 진행 중
- {élément inachevé et son état actuel}

## 결정 사항
- {décision prise lors de cette session}

## 주의 사항
- {avertissement/problème que la prochaine session doit connaître}
```

- Les quatre sections ci-dessus constituent la structure du **résumé** de la passation. Le format des entrées d'acteur du ledger et du bloc `next_session` a pour référence `core/docs/fr/methodology/agent-operations.md` §5.3, et coexiste avec cette structure.
- Si le code a changé mais que la forme finale n'a pas été mise à jour, on déclare `doc_change: none` et une raison dans le frontmatter, et on écrit la même raison sous `## Points d'attention`.

### Structure du corps d'un Pattern

```markdown
## 문제
{le problème que résout ce pattern}

## 해결
{description du pattern}

## 적용 예시
{extrait de code ou exemple de structure}

## 적용 프로젝트
- [[project-a]] — {comment il a été appliqué}
```

### Structure du corps d'une Constraint Card

Une contrainte unique et exécutable extraite d'un ADR. On la garde concise, en 50 lignes au plus.

```yaml
---
title: "{titre de la contrainte — groupe nominal d'une ligne}"
type: constraint
created: YYYY-MM-DD
status: active
source_adr: "[[NNN-adr-slug|ADR-NNN]]"
severity: must-not        # must | must-not | should
scope:
  domains: [{domaine}]     # domaines métier auxquels s'applique cette contrainte
  layers: [{couche}]      # couches Strata auxquelles s'applique cette contrainte
rule: "{règle exécutable d'une ligne — une phrase en MUST/MUST NOT}"
verification: code-review  # code-review | unit-test | integration-test | static-analysis
tags: [constraint, severity/{level}, layer/{layer}, domain/{domain}]
aliases: [CC-NNN-NN]       # ID unique (numéro de l'ADR-numéro d'ordre)
---
```

```markdown
## 근거
{de quelle section de l'ADR elle est tirée et pourquoi cette contrainte est nécessaire, en 1-3 lignes}

## 위반 시 영향
{quels problèmes surviennent si cette contrainte est enfreinte, en 1-3 lignes}

## 검증 방법
{moyens concrets de contrôle, comme la revue de code, les tests, l'analyse statique}
```

**Règles de rédaction d'une Constraint Card :**
- On les extrait dans la même session que celle où un ADR passe à accepted (obligation du Builder)
- 1 ADR → N Cards (en général 3-10)
- La severity se décide d'après la formulation du texte de l'ADR : « doit/obligatoire/MUST » → must, « interdit/NEVER » → must-not, « recommandé/SHOULD » → should
- scope est l'étendue des domaines et des couches auxquels s'applique cette contrainte
- On enregistre en même temps un résumé d'une ligne dans constraint-registry.yaml

### Structure du corps d'un Epic

Unité fonctionnelle du PRD. Elle se relie aux contraintes des ADR par le champ constraints.

```yaml
---
title: "{titre de l'unité fonctionnelle}"
type: epic
project: {project-name}
created: YYYY-MM-DD
status: draft
constraints:                # ★ Obligatoire — les Constraint Cards que cet Epic doit respecter
  - "[[CC-NNN-01]]"
  - "[[CC-NNN-02]]"
domains: [{domaine}]
layers: [{couches concernées}]
personas: [{personas visés}]  # IDs de persona définis dans le projet
tags: [epic, domain/{domain}]
---
```

```markdown
## Objectifs
{le problème utilisateur que résout cet Epic, en 1-3 lignes}

## Critères d'acceptation
- {condition d'achèvement vérifiable}

## Résumé des contraintes
{un résumé de la façon dont chaque Constraint Card du champ constraints s'applique à cet Epic}
```

**Règles de rédaction d'un Epic :**
- Le champ constraints est obligatoire. Un tableau vide est un signal pour la revue (il faut distinguer un vide voulu d'un oubli)
- Lors du découpage en tâches, le Builder répartit les constraints de l'Epic dans le scope.constraints de chaque tâche

### Structure du corps d'un Planning

Texte original de planification importé d'un outil de planification externe (Notion et similaires). La plupart de ces documents ont dépassé le stade de la demande ou reflètent déjà des décisions ; on les traite donc comme de la **planification**, et non comme une « demande » (DEC-2026-09-09-01).
Le texte original est as-intended, et la spécification Knowledge est as-built. On ne mélange pas les deux dans un même document : on ne modifie pas les sections d'origine ; on ne met à jour que la section `## Revue d'implémentation` à la fin du document.

```yaml
---
title: "{titre original}"
id: plan-{project}-{id d'origine}          # inchangé lors d'une réimportation
type: planning
project: {project-name}
status: realized                      # état de la planification — requested | planned | in-progress | realized | on-hold | archived
nodes: ["orders.payments-v2"]           # enregistré après l'approbation de l'Inbox (l'importeur ne propose que des candidats)
source: "notion:{32hex}"              # identifiant d'origine (obligatoire)
source_name: notion-orders-intake        # sous-répertoire de planning/
source_path: "{chemin relatif de l'export d'origine}"  # suivi des éditions
up: "[[plan-{project}-{id parent}]]"    # quand il existe un document parent, comme pour Epic/Story
topic: "Catégorie : … · Regroupement des tâches : … · Sprint : …"   # une ligne de propriétés d'origine — cible de recherche du planificateur de rétro-remplissage des nœuds
owner: "{nom}"                        # facultatif — propriétaire du plan ; un jugement de plan incomplet lui est posé (sinon à l'utilisateur, DEC-2026-10-31-35)
implementation:                       # ★ Obligatoire — classification du résultat de la revue d'implémentation
  status: unreviewed                  # unreviewed | implemented | partial | diverged | not-implemented | superseded
  reviewed: YYYY-MM-DD                # à omettre si unreviewed
  spec: "[[kb-…]]"                    # le document distillé de la forme finale (s'il existe)
created: YYYY-MM-DD
---
```

```markdown
# {titre original}
{texte original — ne pas modifier}

## 구현 검토

| Élément | Plan | Implémentation | Écart | Preuve |
|---|---|---|---|---|
| {élément de politique} | {ce que dit le plan} | {ce que fait le code} | {aucun · différent · non implémenté} | {chemin de code · symbole · lien vers la spécification} |
```

**Règles de rédaction d'un Planning :**
- `## Revue d'implémentation` s'écrit par élément (phrase de politique, case à cocher, Story). Le résumé d'une ligne du document est porté par `implementation.status` ; s'il vaut diverged ou partial, le tableau doit comporter une ligne d'écart.
- Si la revue conduit à une mise à jour de spécification, on ajoute ce document aux `sources:` de cette spécification et on y renvoie avec `implementation.spec`.
- `status` (état de la planification) et `implementation.status` (revue d'implémentation) sont des axes différents. Un plan marqué « déployé » peut différer du code : c'est diverged.
- La facette « planification » d'une page de nœud ne joint que ce type et l'affiche avec des badges (non revu, implémenté, partiellement implémenté, diffère du plan, non implémenté, remplacé). Le nombre de unreviewed et les documents diverged ou partial sont comptés comme dette.
- Quand le plan et le code divergent, ne vous arrêtez pas à une ligne de différence dans `## Revue d'implémentation` : déposez une demande de jugement (`python3 -m kb divergence add` ; les lignes de revérification de la porte avec `kb coverage-gate --divergence-inbox`). Seule une personne juge, avec l'une de quatre valeurs : cohérent (pas de divergence), document périmé (mettre le plan ou la spécification à jour sur le code), plan incomplet (demander au `owner` de compléter le plan), défaut d'implémentation (une tâche de bogue). Enregistrer le jugement (`kb divergence judge`) met `implementation.reviewed` à ce jour, si bien que les mêmes changements ne redemandent pas de revérification ; `implementation.status` est mis à jour selon le jugement (DEC-2026-10-31-35).

### Dossiers de planification (strata.planning)

Quand une source de planification externe est épurée, utilisez un dossier plutôt qu'un seul document original (DEC-2026-11-01-04·05). Un répertoire `planning/<bundle>/` qui contient un répertoire `audit/` est un dossier. Les documents de planification hors dossier (le format ci-dessus) restent des originaux.

| Emplacement | Contenu | Injecté · partagé |
|---|---|---|
| `source/` (ou `category: source`) | la source d'origine, jamais modifiée | non — pièce justificative |
| `audit/facts*.md` | liste de faits `# \| source location \| type \| content \| role \| axes \| subtopic` | non — pièce justificative |
| `audit/coverage*.md` | table de correspondance `# \| source location \| destination \| note` — sept destinations | non — pièce justificative |
| `audit/defects*.md`, `audit/isolated*.md` | défauts (`# \| kind \| content \| handling`), règles isolées | non — pièce justificative |
| `*.md` directement dans le dossier | documents épurés : `planning_doc: prd \| tech-spec \| terms \| tree` | oui |

- Les documents épurés ne contiennent ni code ni architecture (tables, colonnes, schémas ; classes, modules, noms de services ; chemins d'API, codes HTTP ; frameworks, bibliothèques, fournisseurs). Ces faits vont à la destination `code` de la table de correspondance.
- Les tableaux sont lus par position de colonne, donc les en-têtes peuvent être dans n'importe quelle langue. Les destinations s'écrivent en anglais (`isolated:` `defect:` `code` `background` `duplicate:#n` `out of scope:`) ou en coréen (`격리:` `결함:` `코드` `배경` `중복:#n` `범위 밖:`) ; toute autre valeur est lue comme `<refined document> R<n>`.
- La recherche de connaissances ne trouve que les documents épurés. `python3 -m kb planning check <bundle>` vérifie la table de correspondance et les documents épurés ; `python3 -m kb planning boundary [--list]` affiche la frontière d'injection.

## Espaces de noms des tags

On recommande que tous les tags suivent le format `namespace/value`. Espaces de noms définis dans taxonomy.yaml :

| Espace de noms | Motif | Description | Restriction des valeurs |
|-------------|------|------|---------|
| `project` | `project/{name}` | Portée du projet | libre |
| `layer` | `layer/{name}` | Couche de l'architecture Strata | L1, LM1, L2, LM2, L3, Route, Atomic, Molecule, Partial, Page, Layout, Foundation, Contract, DataState, Primitive_UI, Semantic_Component, Feature_Block, Route_Surface, App_Shell |
| `domain` | `domain/{domain}` | Domaine métier | libre |
| `tech` | `tech/{technology}` | Technologie ou framework | libre |
| `audience` | `audience/{role}` | Lecteur visé | developer, planner, devops, all |

Exemple : `tags: [project/my-api, layer/L2, domain/auth, tech/jwt]`

Les tags sans espace de noms sont aussi permis, mais la construction émet un avertissement.
Règles de validation détaillées : `core/templates/vault/_meta/taxonomy.yaml` → `tag_namespaces`, `validation`
