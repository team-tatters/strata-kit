# Knowledge Base — Structure du vault

> Canonique : strata-kit `core/docs/fr/knowledge-base/vault-structure.md` (migré le 2026-10-29 depuis strata `docs/07-knowledge-base/vault-structure.md`, DEC-2026-10-29-11).

## Vue d'ensemble

Le vault est une base de connaissances compatible Obsidian, partagée par tous les projets.
Il est géré comme un dépôt Git indépendant, séparé du code des projets.

## Modèle à trois couches (Archive / Knowledge / Index)

Tout le contenu du vault appartient à l'une de trois couches, et chaque couche a sa propre discipline de maintenance (DEC-2026-08-19-04) :

| Couche | Répertoire | Discipline |
|---|---|---|
| **Archive** | `projects/*/sessions/`, `projects/*/tasks/`, `projects/*/relays/` | append-only. Le write-once est **normal** : aucune obligation de révision ni de lien. Un magasin de preuves, pas une KB |
| **Planning** (variante d'Archive) | `projects/*/planning/{source}/` | Texte de planification d'origine (`type: planning`) importé d'un outil de planification externe (Notion, etc.). **Les sections d'origine sont immuables** (discipline d'Archive) ; seule la section `## 구현 검토` (revue d'implémentation) à la fin du document est mise à jour : elle consigne dans un tableau, pour chaque élément de politique, s'il est implémenté, en quoi il diffère du plan et la preuve, et se classe par le `implementation.status` du frontmatter. Les politiques substantielles sont distillées en spécifications Knowledge, et le `sources:` de cette spécification pointe vers l'original (DEC-2026-09-09-01) |
| **Knowledge** | `projects/*/knowledge-base/`, `patterns/`, `_index/glossary.md` | **Obligation d'update-in-place** : lors d'une mise à jour, `updated:` est obligatoire, et un lien de provenance vers le document d'Archive qui sert de preuve (frontmatter `sources:`) est obligatoire |
| **Index** | `_index/`, chaque `_index.md`, les notes DEC de `projects/*/decisions/`, les pages de nœud de `projects/*/nodes/` | **Généré uniquement : modification manuelle interdite.** Régénéré à partir de la source canonique (enregistrements, frontmatter, toc.yaml) (DEC projection generator, générateur de pages de nœud ; correspondance avec l'implémentation : `python3 -m kb --help` · `core/docs/fr/kb-engine.md`) |

La promotion de connaissances (Archive → Knowledge) est effectuée par une session de distillation et passe par la porte (gate) du Decision Inbox.
Mettre à jour un document Knowledge existant a priorité sur la création d'un nouveau (principe du document vivant).

### Rôles et emplacements des trois sortes de documents (DEC-2026-09-30-03)

| Document | Ce qu'il contient | Où il se trouve | Recherche par défaut |
|---|---|---|---|
| Spécification (décision) | La décision prise au moment de l'implémentation sur le code et les exigences d'implémentation, avec son motif, les symboles de code visés, et si elle est en vigueur ou remplacée | enregistrement decision (Tier P) → miroir en note DEC | avant indexation : on lit directement l'index (`decisions.yaml`) et les notes DEC (leur inclusion dans l'index est un suivi) |
| KB (Knowledge) | La forme finale du service et du domaine, expliquée par une table des matières et un flux compréhensibles par des personnes | `knowledge-base/`, table des matières dans `_meta/toc.yaml` | inclus |
| Historique de travail (Archive·Planning) | Journaux de session, spécifications de tâches, diagnostics et rapports datés, texte d'origine de la planification externe | `sessions/`, `tasks/`, `relays/`, `planning/` | exclu (sur demande explicite seulement) |

- **Un seul document de KB par emplacement de la table des matières.** On ne crée pas de nouveau document sur le même sujet ; on réécrit l'existant. Si un nouveau document le remplace inévitablement, l'ancien est clos par `status: superseded` + `superseded_by`.
- **Les rapports, diagnostics et instantanés datés ne sont pas de la KB.** Un document dont le nom de fichier ou le titre contient une date (comme `*-2026-09-16.md`) consigne les faits de ce jour ; il va donc dans l'historique de travail (`tasks/{date}/` ou `sessions/`). La KB ne reflète que la forme finale modifiée en conséquence, et pointe vers le rapport avec `sources:`.
- **La recherche par défaut ne regarde que la KB.** L'historique de travail n'est inclus que lorsqu'on le demande explicitement à l'outil de recherche (`search_docs(include_history=true)` ou en précisant `category`, CLI `--include-history`). C'est pour que l'historique ne chasse pas les documents canoniques des résultats.

La clé qui traverse les trois couches est le **nœud de sujet**. Un nœud est une unité de la table des matières que lisent les personnes, et sa source canonique est le `_meta/toc.yaml` du projet.
Un document déclare son appartenance par le `nodes:` du frontmatter, et la page de nœud est générée en **joignant** le Knowledge (forme finale, politique), les décisions et l'Archive (historique de travail) qui pointent vers ce nœud.
Une page de nœud n'est pas une promotion. Elle n'écrit rien de nouveau ; elle rassemble seulement sur un écran ce qui existe déjà, et s'il y a un trou, elle le laisse visible. Ce trou est la visualisation de ce qui manque.

## Structure des répertoires

```
vault/
├── .obsidian/           Paramètres de l'application Obsidian (partagés, suivis par git)
│   └── plugins/         Paramètres des plugins Custom Sort, Dataview, etc.
├── .kb/                 ★ Gestion de l'index de la KB
│   ├── manifest.json    Hash SHA256 par fichier (suivi par git)
│   ├── schema.sql       Définition du schéma de la BD (suivi par git)
│   └── store.sqlite     Store de la KB (strata-kit kb, .gitignore — le kb.sqlite legacy a été supprimé par DEC-2026-10-28-13)
├── .local/              Paramètres par machine (.gitignore)
│   └── resolved-paths.yaml
├── .gitignore
├── env-config.yaml      Alias de machines enregistrées avec empreintes (hachage de l'identifiant machine de l'OS, sans chemins)
│
├── _index/              MOC (Map of Content)
│   ├── projects.md      Liste des projets + liens
│   ├── decisions.md     Index des ADR inter-projets
│   ├── patterns.md      Index des patrons/leçons
│   └── glossary.md      Glossaire du domaine
│
├── _meta/               ★ Paramètres globaux
│   └── taxonomy.yaml    Définition du système de classification (catégories, types, étiquettes)
│
├── projects/            Connaissances par projet
│   └── {project-name}/
│       ├── overview.md          Pile technique, objectif, état actuel
│       ├── _meta/               Paramètres du projet
│       │   ├── taxonomy.yaml    Taxonomy étendue du projet (hérite de la globale) — axe des répertoires
│       │   └── toc.yaml         ★ Arbre des nœuds de sujet (source canonique de la table des matières lue par les personnes) — axe des sujets
│       ├── knowledge-base/      ★ KB du projet (cible de l'indexation)
│       │   ├── _index.md        MOC (table des matières dynamique Dataview)
│       │   ├── domain/          Connaissances du domaine (catégorie 1)
│       │   │   ├── _index.md    MOC de la catégorie
│       │   │   ├── epics/       Connaissances du domaine par epic
│       │   │   └── {topic}/     Répertoire de sujet (défini dans la taxonomy du projet)
│       │   │       ├── _index.md
│       │   │       └── *.md     Documents de la KB
│       │   ├── architecture/    Architecture technique (catégorie 2)
│       │   │   ├── _index.md
│       │   │   ├── decisions/   ADR
│       │   │   ├── constraints/ Constraint Card
│       │   │   ├── api-contracts/
│       │   │   ├── data-models/
│       │   │   ├── infrastructure/
│       │   │   └── *.md
│       │   ├── guides/          Guides (catégorie 3)
│       │   │   ├── _index.md
│       │   │   ├── onboarding/
│       │   │   ├── conventions/
│       │   │   ├── troubleshooting/
│       │   │   └── *.md
│       │   └── references/      Références (catégorie 4)
│       │       ├── _index.md
│       │       └── *.md
│       ├── tasks/               ★ Spécifications de tâches (Builder→Worker)
│       │   └── {yyyy.mm.dd}/    Groupées par date
│       │       └── {nn}-{title}/  Dossier de Work Order
│       │           ├── _order.yaml    Ordre de travail
│       │           └── task-{nn}-*.yaml  Spécification d'exécution du Worker
│       ├── strata/              ★ Tier P canonique d'un detached profile (core/docs/fr/environment/data-placement.md §1.5)
│       │   ├── profile.yaml     placement profile manifest (ancre de bootstrap pour un nouveau PC)
│       │   ├── decisions/       enregistrements decision (DEC-*.yaml, une décision = un fichier)
│       │   ├── decisions.yaml   index généré (modification manuelle interdite)
│       │   ├── constraint-registry.yaml
│       │   └── layer-map.yaml
│       ├── decisions/           Notes DEC — générées uniquement (DEC projection generator, modification manuelle interdite)
│       │   └── DEC-YYYY-MM-DD-NN.md
│       ├── nodes/               Pages de nœud — générées uniquement (générateur de pages de nœud, modification manuelle interdite)
│       │   └── {node-id}.md     ex. orders.checkout-v2.coupon.md
│       ├── planning/            ★ Documents de planification (type planning) — créés par l'importateur de documents de planification, original immuable + section de revue d'implémentation
│       │   └── {source-name}/   Par source (ex. notion-orders-intake). Nom de fichier {slug-du-titre-d'origine}--{8 premiers caractères de l'id de la source}.md — la langue du titre d'origine est conservée
│       └── sessions/            Passations de session · ledger (Archive)
│           └── session-YYYY-MM-DD-{slug}.md
│
├── patterns/            Patrons transversaux aux projets
│   └── {pattern-name}.md
│
├── strata-feedback/     Enregistrements de retours sur la méthodologie
│   └── {topic}.md       Retours appliqués/non appliqués
│
├── references/          Références externes, résumés d'API
│   └── {reference-name}.md
└── assets/              Ressources binaires (images, Excel, etc. — interdit à la racine du vault)
```

## Règles de nommage

| Cible | Format | Exemple |
|---|---|---|
| Répertoire de projet | kebab-case | `my-api-server` |
| Nom de fichier de document | kebab-case.md | `auth-strategy.md` |
| Note DEC (générée) | DEC-YYYY-MM-DD-NN.md | `DEC-2026-08-19-01.md` |
| Page de nœud (générée) | {node-id}.md — l'id du nœud tel quel, points (.) compris | `orders.checkout-v2.coupon.md` |
| Document de session | session-YYYY-MM-DD-{slug}.md | `session-2026-08-19-vault-restructure.md` |
| Fichier MOC | nom au singulier | `projects.md`, `glossary.md` |

Les noms de fichier de session n'utilisent que le format unique ci-dessus : le préfixe `handoff-*`, les noms de fichier à date sans préfixe et les fichiers de session `.yaml` sont abandonnés (les legacy sont à migrer). Le véritable identifiant est le slug, pas un numéro de séquence (NN).

## ID stable (frontmatter `id:`)

Tout document du vault a dans son frontmatter un ID stable, invariant lors d'un déplacement ou d'un renommage :

```yaml
id: "kb-shop-api-order-concepts"   # {préfixe}-{project}-{slug} — immuable après création
aliases: ["ancien nom de fichier"]     # lors d'un déplacement ou renommage, conserve l'identifiant d'origine (absorbe les unlinked mentions d'Obsidian)
```

Les préfixes couvrent toutes les classes de documents (intégrant la cross-review du 2026-08-19) :

| Préfixe | Cible | Exemple |
|---|---|---|
| `kb` | documents de knowledge-base/ et patterns/ | `kb-shop-api-order-concepts` |
| `session` | sessions/ (passations · ledger) | `session-strata-2026-08-19-vault-restructure` |
| `order` | ordre de travail `_order.md` | `order-strata-2026.08.19-01` |
| `task` | documents de spécification de tâche | `task-strata-2026.08.19-01-task-03` |
| `dec` | notes DEC (générées) | `dec-strata-2026-08-19-01` |
| `relay` | packet·feedback de relays/ | `relay-strata-2026-08-19-task01-core-spec-review` |
| `moc` | MOC de `_index/` et de chaque `_index.md` | `moc-shop-api-knowledge-base` |
| `node` | pages de nœud de `nodes/` (générées) | `node-shop-api-orders.checkout-v2.coupon` |
| `plan` | documents de planification de `planning/` (importés) | `plan-shop-api-0123456789abcdef0123456789abcdef` — le slug est l'id de la source (Notion), immuable lors des réimportations |
| `doc` | tout autre document non couvert ci-dessus | `doc-vault-env-config` |

- **La valeur de {project}** : sous `projects/{name}/`, c'est le nom de ce projet. Les **documents transversaux aux projets** (`patterns/`, `references/`, `_index/`, la racine du vault) utilisent `vault` (ex. `kb-vault-{slug}`, `moc-vault-decisions`).
- Un chemin n'est qu'un moyen de navigation, pas une identité à long terme. L'identité des liens et des références est portée par `id:`.
- Lors d'une migration (déplacement ou renommage), on conserve l'`id:` et on ajoute l'ancien nom de fichier à `aliases:`.
- **Un id de nœud est un espace de noms distinct de l'id d'un document.** C'est un chemin joint par des points (.) à partir des ancêtres, comme `orders.checkout-v2.coupon`, qui ne suit pas le système de préfixes ci-dessus. Un document écrit les ids de nœud dans son champ `nodes:`, et seul l'id de **document** d'une page de nœud entre dans le système de préfixes, sous la forme `node-{project}-{node-id}`. Les points dans le slug ne sont permis qu'avec le préfixe `node`.

## Système de catégories de la KB

Défini dans taxonomy.yaml, composé de quatre catégories :

| Catégorie | Objectif | limite de depth | Types principaux |
|----------|------|:---:|-----------|
| `domain` | Connaissances du domaine métier | 3 | concept, specification, flow |
| `architecture` | Décisions de conception, API, infrastructure, contraintes | 2 | specification, decision, overview, constraint |
| `guides` | Prise en main, conventions, dépannage | 2 | guide, pattern, runbook |
| `references` | Normes externes, références de spécifications | 2 | reference, glossary |

- Pas de préfixe NN : l'ordre suit le champ `order` de la taxonomy
- La catégorie est déduite du répertoire (non écrite dans le frontmatter)
- Les children de la catégorie `domain` sont définis dans la taxonomy du projet
- Règles détaillées : `templates/vault/_meta/taxonomy.yaml`

La catégorie est l'**axe des répertoires** (où se place un document), et le nœud de sujet est l'**axe des sujets** (de quoi parle un document). Les deux sont distincts.
La catégorie n'est pas écrite dans le frontmatter parce qu'elle ferait doublon avec le chemin, mais `nodes:` est une information qu'on ne peut pas déduire du chemin, donc ce n'est pas un doublon. Un document peut appartenir à plusieurs nœuds, et un nœud ne crée pas de répertoire.
Source canonique et règles de l'arbre des nœuds : le `_meta/toc.yaml` du projet ; les règles de format sont dans la section `topic_nodes` de la taxonomy globale.

## Procédure d'intégration d'un projet

Pour enregistrer un nouveau projet dans le vault :

1. Créer le répertoire `vault/projects/{project-name}/`
2. Rédiger `overview.md` (avec le frontmatter obligatoire ; voir document-format.md)
3. Mettre à jour `_index/projects.md` (couche Index — remplacé par une régénération une fois devenu généré)
4. Créer `_meta/taxonomy.yaml` (définit les sujets de domaine du projet)
5. Créer `_meta/toc.yaml` (arbre des nœuds de sujet — un premier nœud suffit. Le point de départ est le moment où les documents commencent à avoir `nodes:`)
6. Créer les répertoires de catégories sous `knowledge-base/` (`domain/`, `architecture/`, `guides/`, `references/`)
7. Créer les répertoires `sessions/` et `tasks/`. Pour un projet à detached profile, inclure `strata/` (Tier P) : le manifest `profile.yaml` est obligatoire (core/docs/fr/environment/data-placement.md §1.5). `decisions/` et `nodes/` sont créés par les générateurs

### Contenu minimal de overview.md

```markdown
---
title: "{nom du projet}"
type: overview
project: {project-name}
tags: [{étiquettes de la pile technique}]
created: {YYYY-MM-DD}
updated: {YYYY-MM-DD}
status: active
---

## Objet
{1-2 phrases sur l'objectif du projet}

## Pile technique
- Langage : {language}
- Framework : {framework}
- BD : {database}

## Correspondance des couches Strata
{Correspondance entre les répertoires de ce projet → couches Strata}
```

## Ce qui n'est jamais inclus

- Code source (les extraits de code sont autorisés à titre d'exception)
- Artefacts de build
- Chemins absolus propres à un environnement
- Secrets, clés, jetons
- YAML de passation brut (seul un résumé est conservé)

Exception : les **chemins relatifs, symboles, endpoints et noms de tables** du dépôt dans le `covers:` du frontmatter sont des pointeurs, pas du code, donc autorisés. Les chemins absolus et le corps du code restent interdits.
