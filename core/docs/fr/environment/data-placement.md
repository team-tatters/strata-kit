# Frontière de placement des données (Data Placement)

> Source canonique : strata-kit `core/docs/fr/environment/data-placement.md` (migré le 2026-10-29 depuis strata `docs/06-environment/data-placement.md`, DEC-2026-10-29-11).

> L'unique source de vérité (source of truth) sur **où vivent les artefacts de Strata et qui les suit**.
> Elle rassemble des règles qui étaient dispersées (le tableau de données de cross-model-bridge, CLAUDE.md, task-spec-schema et la distinction local/shared de 01-context).
> Principe central : **« Les sessions sont jetables, les données vivent hors de Core, et l'historique de travail vit hors du dépôt du projet. »**

## 0. Pourquoi c'est nécessaire (le problème résolu)

La conception initiale faisait **suivre par git, dans le dépôt du projet, `.strata/handoffs/` et `.strata/tasks/` afin de les partager entre sessions**. Conséquences :

- **Churn de commits** : les passations et les tâches sont de l'*historique de travail* créé et modifié à chaque session, mais elles étaient commitées dans le dépôt de code pour être partagées, et la fréquence des commits était anormalement élevée.
- **Double stockage** : la passation était écrite dans `.strata/handoffs/*.yaml` (dépôt) puis synchronisée vers `sessions/*.md` du vault, en laissant l'original dans le dépôt ; la même information existait donc à deux endroits.
- **Dérive d'emplacement** : les modèles récents (shared session ledger, task-spec) prennent déjà le vault comme source de vérité, mais les anciens modèles et scripts pointaient encore vers `.strata/`, si bien qu'un même artefact avait deux sources de vérité.

La solution est de **sortir l'historique de travail du dépôt du projet (vers le vault) et de ne laisser dans le dépôt que les consignes propres au projet**. Cela termine la partie restée inachevée de la décision qui avait déjà déplacé le ledger et le relay vers le vault.

## 1. La frontière à 3 Tiers

```text
Tier L · local      {project}/.strata/local/        exclu de git   état d'exécution local à la machine et volatil
Tier P · project    {project}/.strata/              suivi par git  'consignes' propres au projet (avec le code)
Tier V · vault      $STRATA_VAULT/projects/{n}/     git du vault   'historique' de travail et artefacts de collaboration
```

Le critère de classement en une ligne :

> **Si c'est volatil, c'est L ; si ce sont des consignes propres au projet, c'est P ; si c'est de l'historique de travail ou un artefact de collaboration, c'est V.**

| Tier | Emplacement | git | Nature | Fréquence de changement |
|---|---|---|---|---|
| **L · local** | `{project}/.strata/local/` | Exclu (.gitignore) | Propre à la machine, se casse sur les autres machines, régénérable | Élevée (sans importance car non suivi) |
| **P · project SoT** | `{project}/.strata/` (racine) | Suivi | L'architecture et les contraintes de ce projet. Doit être relu dans une PR avec le code | Faible (seulement quand l'architecture change) |
| **V · vault/shared** | `$STRATA_VAULT/projects/{n}/` | git du vault (séparé) | Historique et artefacts partagés entre sessions et entre personnes. Indépendant des commits du dépôt | Élevée (pas de churn car hors du dépôt) |

## 1.5 Placement Profile (embedded | detached)

L'**emplacement physique** du Tier P est l'un des deux, selon la politique de dépôt du projet.
Le sens du Tier (consignes propres au projet) et l'obligation de relecture sont les mêmes ; seul l'emplacement diffère. (DEC-2026-08-19-01)

| Profile | Où se trouve la source de vérité du Tier P | Trace dans le dépôt | Critère d'application |
|---|---|---|---|
| **embedded** (par défaut) | `{project}/.strata/` — suivi par git | Une ligne d'ignore pour `.strata/local/` | Dépôts personnels ou maîtrisés — le Tier P peut être relu dans une PR avec le code |
| **detached** | `$STRATA_VAULT/projects/{n}/strata/` — git du vault | Seulement `.strata/local/` exclu de git (zéro commit) | Dépôts d'équipe, etc., où commiter `.strata` viole la convention |

La **source de vérité du profile est un fichier manifest** — un pointeur gardé uniquement sur la machine locale ne serait pas restauré sur un nouveau PC (prend en compte la revue croisée du 2026-08-19) :

| Profile | Emplacement du manifest | Support de conservation |
|---|---|---|
| embedded | `{project}/.strata/profile.yaml` (suivi par git) | Le dépôt du projet — **un nouveau projet sans aucune décision peut aussi être identifié** |
| detached | `$STRATA_VAULT/projects/{n}/strata/profile.yaml` | Le vault — **un nouveau PC restaure le profile par un simple pull du vault** |

```yaml
# profile.yaml — placement profile manifest
profile: detached        # embedded | detached (le manifest côté dépôt n'autorise que embedded)
project: "{project-name}"
```

`.strata/local/vault-link.yaml` (Tier L, exclu de git) est un **cache local facultatif** — ce n'est pas la SoT et tout fonctionne sans lui.

- **Règles du resolver du Tier P** (communes à tout consommateur qui lit le Tier P — correspondance d'implémentation : `python3 -m kb --help`, `core/docs/fr/kb-engine.md`) :
  ① `.strata/profile.yaml` du dépôt (déclaration embedded) → embedded
  ② `.strata/decisions.yaml` ou `.strata/decisions/` existe dans le dépôt (détection legacy) → embedded
  ③ `.strata/local/vault-link.yaml` (cache local) → detached
  ④ `$STRATA_VAULT/projects/{basename du répertoire}/strata/profile.yaml` → detached (bootstrap d'un nouveau PC)
  ⑤ Si rien n'existe, le projet n'utilise pas Strata
- L'arbre du Tier P detached : `strata/{profile.yaml, decisions/, decisions.yaml, constraint-registry.yaml, layer-map.yaml}`
- S'il faut ne toucher absolument pas au dépôt, enregistrez `.strata/` dans le **gitignore global** (`~/.config/git/ignore`) plutôt que dans le `.gitignore` du dépôt d'équipe.
- Avec detached, reprendre une session d'un PC à l'autre **se fait en un seul pull du vault** (hook de synchronisation : DEC-2026-08-19-02).
- Une décision qui doit être partagée avec l'équipe est promue dans `docs/` du dépôt, en plus de sa conservation dans le vault (même schéma que la règle de promotion des contrats d'API du §2).

## 2. Placement par artefact (le tableau canonique)

| Artefact | Tier | Chemin | Remarques |
|---|---|---|---|
| active-task (par session) | L | `.strata/local/active/{session-id}.yaml` | L'état courant quand une session est interrompue (règle absolue). Un fichier par session pour que des sessions concurrentes ne s'écrasent pas (DEC-2026-08-19-05) |
| session-plan.yaml | L | `.strata/local/session-plan.yaml` | |
| session-log.txt | L | `.strata/local/session-log.txt` | Écrit par le hook SessionEnd |
| last-compaction.yaml | L | `.strata/local/last-compaction.yaml` | Instantané de PreCompact |
| agent-sessions.yaml (correspondance des sessions) | L | `.strata/local/agent-sessions.yaml` | claude_id ↔ codex_id, propre à la machine |
| **profile manifest** | **P** | `.strata/profile.yaml` (embedded) / `strata/profile.yaml` du vault (detached) | Source de vérité du placement profile (§1.5) |
| **enregistrement de décision** | **P** | `.strata/decisions/DEC-{date}-{NN}-{slug}.yaml` | La **source de vérité** de la décision — une décision = un fichier. La numérotation et l'enregistrement passent par le CLI decision writer (sûr avec des sessions concurrentes, DEC-2026-08-19-05) |
| **decisions.yaml (index)** | **P** | `.strata/decisions.yaml` | Un **index T0 régénéré à partir des enregistrements**. Ne jamais l'éditer à la main |
| **constraint-registry.yaml** | **P** | `.strata/constraint-registry.yaml` | Registre des contraintes de contexte |
| **layer-map.yaml** | **P** | `.strata/layer-map.yaml` | Correspondance utilisée pour détecter les violations de couches |
| cowork DB | L | `.strata/cowork/cowork.sqlite*` | État volatil de CoWorking (WAL compris). Ce qui est promu en persistant va dans tasks (V) et dans les enregistrements de décision (P) |
| ~~shared/~~ | — | `.strata/shared/` | **deprecated** — l'historique de travail doit être entièrement migré vers le Tier V. Interdit d'en créer de nouveaux |
| **handoffs (passations)** | **V** | `$STRATA_VAULT/projects/{n}/sessions/` | Même emplacement que le shared session ledger. **Écrites directement dans le vault** |
| **shared session ledger** | **V** | `$STRATA_VAULT/projects/{n}/sessions/` | Source of truth du contexte |
| **tasks (spécifications de tâche)** | **V** | `$STRATA_VAULT/projects/{n}/tasks/{date}/{nn}-{title}/` | `_order.yaml` + `task-{nn}.yaml` |
| **enregistrements de relay** | **V** | `$STRATA_VAULT/projects/{n}/relays/` | Échange de request/feedback |
| **Hub delivery state** | **L** | `.strata/local/` ou la DB Hub locale | hub_id, curseur de l'inbox, état pull/ack. Propre à la machine et à la session |
| **Hub audit projection** | **V** | `$STRATA_VAULT/projects/{n}/sessions/` ou `relays/` | Résumé des packets/reviews/decisions qu'une personne doit reprendre |
| **methodology-backlog (project)** | **V** | `$STRATA_VAULT/projects/{n}/backlog/methodology-backlog.yaml` | File d'exploitation = nature d'historique de travail |
| **exploration-report / draft api-specs** | **V** | `$STRATA_VAULT/projects/{n}/sessions/` (ou à côté de tasks) | Artefacts intermédiaires transmis d'une session à l'autre (les API accepted sont promues — voir la note ci-dessous) |
| **miroir des notes DEC** (miroir ADR pour les humains) | V | `$STRATA_VAULT/projects/{n}/decisions/DEC-{date}-{NN}.md` + `_generated-index.md` | Un **miroir pour la lecture humaine et les backlinks**, généré à partir des enregistrements. La source de vérité est le Tier P. **Moment de génération** : **juste après** que `add`, `regen-index` ou `migrate` du CLI decision writer ont écrit les enregistrements et l'index, **dans la même exécution**, le DEC projection generator est appelé et **régénère entièrement** la part de ce projet (idempotent, supprime les notes sans source de vérité). Le commit est assuré par le canal de fin de session (handoff/ledger close → commit+push du vault) ; pour un effet immédiat, `--sync` (DEC-2026-08-21-01) |

| **arbre des nœuds thématiques (toc.yaml)** | **V** | `$STRATA_VAULT/projects/{n}/_meta/toc.yaml` | La **source de vérité** de la table des matières lisible par les humains. C'est de la consigne par nature, mais tous ses consommateurs (le générateur de pages de nœud, l'index du KB, le resolver de couverture) sont côté vault et un projet detached n'a aucun endroit où la mettre dans le dépôt ; c'est donc V. Ce n'est pas un changement qui doit être relu avec le code |
| **pages de nœud** | V | `$STRATA_VAULT/projects/{n}/nodes/{node-id}.md` | Une **vue de jointure** (couche Index, ne jamais éditer à la main) générée à partir de toc.yaml et du frontmatter à quatre faces (spécification, contrainte, décision, session). **Moment de génération** : la construction de l'index du KB et le canal de fin de session (handoff/ledger close) régénèrent entièrement la part de ce projet dans la même exécution (idempotent, supprime les pages sans source de vérité). On ne le laisse pas à une exécution manuelle séparée — leçon du miroir des notes DEC |

> **Une page de nœud n'est pas une source de vérité** — les sources de vérité des quatre faces sont respectivement la spécification (V), la Constraint Card (V) et le registry (P), l'enregistrement de décision (P) et la session (V) ; la page de nœud les rassemble en lecture seule. La face « dette » n'est elle aussi qu'un indicateur ; sa source de vérité est le fait même que le document de session n'a pas de déclaration `doc_change`.
>
> **La source de vérité des décisions est le Tier P** — l'emplacement physique suit le profile (embedded = `.strata/` du dépôt, detached = `projects/{n}/strata/` du vault, §1.5). `projects/{n}/decisions/` du vault contient des **notes DEC** générées à partir des enregistrements (pour la lecture humaine et les backlinks, ne jamais éditer à la main) et n'est pas une SoT lisible par machine.
>
> **Rôle et limites du miroir des notes DEC** (DEC-2026-08-21-01) : pour un projet embedded, la source de vérité des enregistrements **n'est pas lisible depuis une autre machine tant que le dépôt du projet n'a pas été commité et poussé**. Le miroir est un complément inter-environnements qui comble ce vide par le canal du vault ; il ne remplace pas la source de vérité. Donc ① le miroir doit être généré dans **la même exécution** que celle qui écrit l'enregistrement (le laisser à une exécution manuelle séparée le laisse vide — le cas réel de zéro miroir sur un projet backend le 2026-08-21), et ② les portes de fin de session (le handoff generator et `validate`/`close` du CLI du ledger) **avertissent des enregistrements non commités** dans `.strata/decisions*` du dépôt (elles ne bloquent pas). Un projet detached n'est pas visé par la porte, car les enregistrements eux-mêmes sont dans le vault et le canal de fin de session les commite ensemble.
>
> **Règle de promotion des contrats d'API** : les `draft api-specs` sont du Tier V (intermédiaires de passation entre sessions), mais un **accepted API contract** (le moment où il devient la base du code, des clients et de la documentation) n'est pas de l'historique de travail mais un project artifact → **à promouvoir vers le Tier P ou vers `docs/openapi` du dépôt**.
>
> **Attention à la visibilité du backlog** : le `methodology-backlog` du projet est lui-même une file d'exploitation et donc du Tier V, mais **si un élément accepted modifie le Tier P (`decisions`/`constraint-registry`/`layer-map`), ce changement du Tier P doit apparaître dans la même PR** (visibilité à la revue de code — même si le backlog passe dans le vault, *la traduction de la décision dans le code* se relit dans le dépôt).

## 3. Règles .gitignore (projet)

Le Tier L est exclu et seul le Tier P est suivi. Le Tier V est de toute façon hors du dépôt du projet, donc sans importance.

```gitignore
# Strata — exclure le Tier L (local, cowork), ne suivre que le Tier P (consignes)  [embedded profile]
.strata/local/
.strata/cowork/
.strata/**/*.tmp

# Le Tier P est suivi explicitement (pas exclu) :
#   .strata/decisions/  .strata/decisions.yaml
#   .strata/constraint-registry.yaml
#   .strata/layer-map.yaml
```

Pour le **detached profile**, le principe est de ne pas toucher au `.gitignore` du dépôt — enregistrez `.strata/` dans le gitignore global (`~/.config/git/ignore`) pour garder la trace dans le dépôt à zéro (§1.5).

> ⚠️ C'est **inversé** par rapport à l'ancienne règle (suivre `handoffs/` et `tasks/`). Avant, c'était « suivre pour partager » ; désormais le partage est assuré par le **vault (Tier V)** et le dépôt ne les suit pas.

## 4. Pourquoi cette frontière (justification)

- **Ce qui dépend de la machine (L) se casse si on le met dans git.** Les identifiants de session et les chemins locaux n'ont aucun sens sur une autre machine (comme le principe local/shared de la carte `rec.session.state-in-files`).
- **Les consignes (P) partagent le sort du code.** Les décisions d'architecture et les contraintes doivent être vues avec ce code lors de sa relecture ou de son retour arrière ; par défaut elles sont donc dans le même dépôt et la même PR (embedded). Mais si la convention du dépôt d'équipe n'autorise pas à commiter `.strata`, on déplace **seulement l'emplacement** vers le vault (detached, §1.5) — la nature des consignes et l'obligation de relecture restent les mêmes. Leur faible fréquence de changement ne crée pas de churn.
- **L'historique (V) a son propre canal de partage.** Les passations, le ledger et les relays sont de l'historique qui relie les sessions et les personnes. Ce partage est assuré uniquement par le **vault (sa propre synchronisation git/Obsidian)** ; il n'y a donc aucune raison de les mettre dans le dépôt de code. Le dépôt de code n'est commité que lorsque le code ou les consignes changent.

## 5. Relation avec les autres documents

- **Synchronisation du vault** : les passations sont écrites directement dans le vault (l'ancien flux de double stockage « original du dépôt → conversion vers le vault » est supprimé). Qui écrit chaque artefact généré du vault est fixé par DEC-2026-10-29-04 — les notes DEC sont intégrées à l'exécution du CLI decision writer (tableau du §2), les pages de nœud sont générées par le librarian (`kb views-publish`) et les métadonnées d'index le sont sur chaque machine.
- **task-spec-schema.md** (`core/docs/fr/methodology/task-spec-schema.md`) : les tâches et le backlog sont du Tier V. Ce tableau est la source de vérité des chemins.
