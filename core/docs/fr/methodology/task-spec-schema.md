# Schéma de spécification de tâche (Task Specification Schema)

> Canonique : strata-kit `core/docs/fr/methodology/task-spec-schema.md` (migré le 2026-10-29 depuis strata `docs/04-agents/task-spec-schema.md`, DEC-2026-10-29-11).

> Définit la structure de la spécification de tâche que le Builder produit et que le Worker consomme.
> Une spécification de tâche est **autonome** : le Worker doit pouvoir terminer le code à partir de la seule spécification.

## Emplacement de stockage

```
$STRATA_VAULT/projects/{project-name}/tasks/
  {yyyy.mm.dd}/
    {nn}-{short-kebab-title}/      # dossier de Work Order
      _order.yaml                   # ordre de travail (créé par le Builder)
      task-{nn}-{title}.yaml        # spécification d'exécution du Worker
```

### Pourquoi cet emplacement

- `$STRATA_VAULT` : n'affecte pas le dépôt du projet (dépôt séparé)
- `tasks/` : séparé des documents KB (knowledge-base/), hors de l'index de recherche
- `{yyyy.mm.dd}/` : suivi selon l'écoulement du temps, charge cognitive minimale
- `{nn}-{title}/` : distingue plusieurs ordres de travail d'une même journée par séquence et titre

### Règles de nommage

| Élément | Format | Exemple |
| ------------- | ------------------------------ | ------------------------------- |
| Dossier de date | `yyyy.mm.dd` | `2026.04.23` |
| Dossier de Work Order | `{nn}-{kebab-title}` | `01-debounce-mongo-sync` |
| Ordre de travail | `_order.yaml` | Toujours fixe (tiret bas = trié en premier) |
| Fichier de tâche | `task-{nn}-{kebab-title}.yaml` | `task-01-redis-dirty-mark.yaml` |

### Règles du numéro de séquence

- Nombre d'entrées existantes dans ce dossier de date + 1
- Les numéros peuvent entrer en collision quand plusieurs machines travaillent en même temps → **le title est le véritable identifiant**
- Une collision de numéros n'affecte que le tri, sans problème fonctionnel

---

## _order.yaml — ordre de travail

Le manifeste que le Builder crée après avoir découpé les tâches.

### Champs obligatoires

```yaml
order:
  id: "2026.04.23-01"                # {date}-{séquence}
  title: "Optimisation de la synchronisation MongoDB par Redis Debounce"
  date: "2026-04-23"
  mode: "task"                        # task | verbal (escalated)
  project: "shop-api"

  goal: |
    Décrire l'objectif et le contexte du travail.
    Pourquoi ce travail est nécessaire et dans quel état il doit se trouver une fois terminé.

  context:
    prior_session: "session-2026-04-22-01"    # référence à la passation précédente
    prior_decisions:                           # décisions existantes qui affectent ce travail
      - "PostProcessJob utilise le polling (@Scheduled fixedDelay=5000)"
    blocker_resolved: "Système PostProcessJob implémenté (4/21)"
    kb_references:                             # documents KB associés
      - "$STRATA_VAULT/projects/shop-api/knowledge-base/03-orders/checkout.md"

  tasks:
    - id: "task-01"
      title: "Ajouter des opérations SET à CacheGenericOperator"
      model_tier: "standard"
      layer: "L2_DataLayer"
      depends_on: []

    - id: "task-02"
      title: "Implémenter DirtyMarkService"
      model_tier: "standard"
      layer: "L3_Composite"
      depends_on: ["task-01"]

    - id: "task-03"
      title: "Basculer DataUpsertListener vers le debounce"
      model_tier: "deep"
      layer: "L3_Composite"
      depends_on: ["task-01", "task-02"]

  acceptance:
    - "Le passage du flux de traitement immédiat existant au flux dirty mark est terminé"
    - "Tous les tests unitaires passent"
    - "0 violation de couche"

  status: "open"                       # drafting | open | in_progress | completed | cancelled
  completed_tasks: []                  # liste des ids de tâches terminées
```

### Champs facultatifs

```yaml
  escalated_from: "verbal"             # lors de la conversion verbal → task
  completed_before_spec:               # éléments terminés en mode verbal avant la conversion
    - "Ajouter des opérations SET à CacheGenericOperator"
  
  estimated_sessions: 1                # nombre de sessions prévu
  priority: "high"                     # high | medium | low
  deadline: "2026-04-25"              # date absolue

  verification_tier: "self_verified"  # solo | self_verified | cross_verified (valeurs enum)
                                      #   Si omis, verbal = solo. En Task Mode, il est recommandé de l'indiquer explicitement.
                                      #   Détails : core/docs/fr/methodology/verification-tier.md
  entry_point: "change"               # design_first | dev_first | spec_first | change — point d'entrée des livrables (Spec, Design, Impl).
                                      #   Ne fixe pas l'ordre. Le contrôle de cohérence est la porte. Détails : core/docs/fr/architecture/frontend-design-contract.md
  design_verified: "self"             # none | self | designer | cross — indépendance de la vérification de cohérence du design (core/docs/fr/methodology/verification-tier.md).
                                      #   none si ce n'est pas un travail d'UI.
  methodology_feedback:               # boucle de retour sur la méthodologie (facultatif)
    enabled: true
    backlog_ref: "$STRATA_VAULT/projects/{name}/backlog/methodology-backlog.yaml"
```

> **Toutefois, pour un travail qui modifie la source de vérité du Core** (layer-rules / naming-convention / task-spec-schema / agent-roles),
> `verification_tier: cross_verified` est **obligatoire** (`core/docs/fr/methodology/verification-tier.md`).
> Dans ce seul cas, verification_tier est traité comme un champ obligatoire et non facultatif.

### Cycle de vie de status

```
drafting → open → in_progress → completed
                              → cancelled
```

| Statut | Signification | Condition de transition |
|------|------|----------|
| `drafting` | Le Builder découpe les tâches | Le Builder commence à écrire _order.yaml |
| `open` | Ordre de travail confirmé, le Worker peut exécuter | Toutes les spécifications de tâche sont rédigées |
| `in_progress` | Certaines tâches sont en cours d'exécution | La première exécution d'un Worker démarre |
| `completed` | Toutes les tâches sont terminées | Tous les acceptance sont satisfaits |
| `cancelled` | Annulé | Décision explicite d'annuler |

Un ordre de travail à l'état `drafting` est soit terminé par le Builder à la session suivante, soit abandonné.

---

## _order.md — nouveau format de l'ordre de travail (2026-08-19, DEC-2026-08-19-03)

Les nouveaux orders sont écrits en `_order.md` : le **frontmatter YAML est l'order lui-même** (le schéma est identique à celui de `_order.yaml` ci-dessus),
et le corps est un markdown minimal pour intégrer l'order au graphe de liens d'Obsidian.

```markdown
---
order:
  id: "2026.08.20-01"
  # ... (schéma de _order.yaml tel quel)
---

# {order title}

- Design: [[design-doc]]
- Decisions: [[DEC-YYYY-MM-DD-NN]]
```

- Seul le frontmatter est analysé par une machine : les scripts qui consomment les orders prennent en charge à la fois `_order.yaml` et `_order.md` (frontmatter).
- Le corps doit conserver des `[[wikilink]]` vers le document de design et les DEC associés (arêtes de la colonne (liens de la passation : orders, kb_updates, decisions_made) — session→order→design+DEC).
- Les `_order.yaml` existants ne sont pas convertis rétroactivement. `task-{nn}.yaml` reste en yaml (la note d'order se charge de l'intégration au graphe).

---

## task-{nn}.yaml — spécification d'exécution du Worker

Le document de tâche autonome que reçoit le Worker.

### Schéma complet

```yaml
task:
  id: "2026.04.23-01/task-01"          # {order-id}/{task-id}
  title: "Ajouter des opérations SET à CacheGenericOperator"
  order_ref: "_order.yaml"             # référence à l'ordre de travail parent

execution:
  model_tier: "standard"               # deep | standard | light (l'adaptateur d'outil associe les noms de modèle)
  model_reason: "Suit le modèle existant de CacheGenericOperator"
  estimated_turns: 8
  estimated_files: 2

scope:
  layer: "L2_DataLayer"
  module: "domain:common-cache"
  nodes: ["common.cache"]                         # nœuds thématiques auxquels appartient cette tâche — le résolveur de couverture les déduit de directories
  can_reference: ["L1_Component"]
  cannot_reference: ["L3_Composite", "Route_Controller"]
  constraints:                                    # contraintes de domaine extraites des ADR
    - id: "CC-NNN-NN"
      rule: "{règle d'une ligne de la contrainte qui s'applique à ce scope}"
  docs_to_update:                                 # spécifications qui possèdent directories·module via covers — injectées par le résolveur de couverture
    - node: "common.cache"
      doc: "[[kb-shop-api-common-cache-spec]]"
      reason: "covers.paths correspond — ajouter des opérations SET modifie la liste d'opérations de la spécification"
  directories:
    - "domain/common-cache/src/main/kotlin/com/example/domain/common_cache/components/"

inputs:
  reference_files:
    - path: "domain/common-cache/.../CacheGenericOperator.kt"
      reason: "Référence du modèle existant — usage de ReactiveRedisOperations"
    - path: "docs/architecture/layer-rules.yaml#L2_DataLayer"
      reason: "Vérifier les règles de couche"

  requirements: |
    Spécification détaillée de ce qu'il faut implémenter.
    - Signatures des méthodes
    - Description du comportement
    - Contraintes

  conventions: |
    Résumé des conventions à appliquer (pour que le Worker n'ait pas à lire de fichiers à part).
    - Marqueurs PAL obligatoires (@pal-port, @pal-layer, @pal-domain, @Comment)
    - Nommage : {Domain}{ServiceType}

  design_ref:                          # Obligatoire pour une tâche qui construit de l'UI. Pointeur vers le livrable de design (core/docs/fr/architecture/frontend-design-contract.md)
    kind: "figma"                      # figma | storybook | claude_design | none
    ref: "file/abc?node-id=12:34"      # fichier, nœud, id de story ou URL du canevas
    version: "2026-04-23"              # version de l'outil ou date de l'instantané — référence du contrôle de cohérence
    reason: null                       # obligatoire si kind: none (ex. "écran d'administration texte seul")

deliverables:
  files:
    - path: "domain/common-cache/.../CacheGenericOperator.kt"
      action: "modify"                  # create | modify | create_or_modify
      description: "Ajouter 4 méthodes d'opérations SET"
    - path: "domain/common-cache/.../CacheGenericOperatorTest.kt"
      action: "create_or_modify"
      description: "Tests unitaires des opérations SET"

acceptance_criteria:
  - "addToSet, popFromSet, getSetSize, getSetMembers implémentés"
  - "Aucun changement des signatures de méthodes existantes"
  - "Les tests unitaires passent"
  - "Aucune violation de couche"

context_budget:
  max_reference_files: 5
  max_loaded_tokens: 20000
  compaction_strategy: "file-based"

status: "pending"                       # pending | in_progress | completed | blocked
completion: null                        # rempli par le Worker à la fin (voir ci-dessous)
```

**`scope.nodes` et `scope.docs_to_update`** : le Builder injecte les spécifications qui possèdent la surface de code modifiée par la tâche (frontmatter `covers`) ainsi que les nœuds thématiques de ces spécifications. Le principe est le même que pour `scope.constraints`. Le Worker n'exécute pas le résolveur ; il lit seulement les valeurs injectées.
- Pour une surface sans spécification propriétaire (une nouvelle fonctionnalité), il faut soit inclure la création de la spécification dans `deliverables.files`, soit écrire `docs_to_update: []` et indiquer dans `inputs.requirements` la raison du vide volontaire. Un tableau vide sans raison déclenche un avertissement de validation.
- La source de vérité du format des valeurs est la section « Champs de nœud et de couverture » de core/docs/fr/knowledge-base/document-format.md.

### Section completion (remplie par le Worker — sauf `triage.review_gate`)

Le Worker remplit `completion.self_report` et la liste des livrables, mais **`triage.review_gate` est rempli
par le réévaluateur indépendant (reviewer/relay)** : la prémisse de la porte de vérification de l'auto-rapport (agent ≠ réévaluateur,
`core/docs/fr/methodology/agent-operations.md` §4) implique que la porte est neutralisée si le Worker la remplit lui-même.

```yaml
completion:
  status: "completed"                   # completed | blocked | partial
  completed_at: "2026-04-23T14:30:00+09:00"
  files_created:
    - "domain/common-cache/.../CacheGenericOperatorTest.kt"
  files_modified:
    - "domain/common-cache/.../CacheGenericOperator.kt"
  tests:
    total: 4
    passed: 4
    failed: 0
  layer_violations: 0
  naming_violations: 0
  constraint_compliance:                # résultat de conformité pour chaque élément de scope.constraints
    - id: "CC-NNN-NN"
      met: true
      note: "{base de la conformité ou point particulier}"
  design_sync: "aligned"                # aligned | stale | waived | none — cohérence Impl↔Design (obligatoire si inputs.design_ref existe)
  design_sync_reason: ""                # obligatoire si waived : raison + until YYYY-MM-DD. Si stale, l'achèvement ne peut pas être déclaré
  doc_change: "updated"                 # updated | none — résultat du traitement de scope.docs_to_update (même clé que le frontmatter de session)
  doc_change_reason: ""                 # obligatoire si none (ex. "refactorisation seule — aucun changement de contrat externe ni de politique")
  docs_updated:                         # si updated, les documents mis à jour (ajouter cette tâche au tampon updated et à sources)
    - "[[kb-shop-api-common-cache-spec]]"
  notes: "Rien de particulier"
  methodology_signals:                  # facultatif — signaux d'amélioration de la méthodologie (une liste ; [] ou omis s'il n'y en a pas)
    - type: "incomplete_spec"           # incomplete_spec | scope_issue | constraint_conflict | rule_gap | drift | design_drift
                                        #   design_drift : valeur hors alias ou désaccord de contrat (axe, état) constaté → candidat à l'amélioration du contrat de tokens/design
      severity: "minor"                 # minor | major | blocking
      scope: "methodology"              # project | methodology
      affected_core:                    # au moins 1 obligatoire si scope: methodology
        - "core/docs/fr/methodology/task-spec-schema.md"
      summary: "La spécification de tâche n'a pas de champ pour la commande de test, ce qui a rendu instable le critère de vérification de l'achèvement"
  triage:                               # facultatif — classification de la sortie d'Agent Operations (pour le Decision Inbox)
    self_report:
      status: "completed"               # completed | blocked | needs_decision | rejected
      risk: "low"                       # high | medium | low | unknown
      decisions_needed: []
    review_gate:                        # porte de vérification de l'auto-rapport (quand une réévaluation est requise)
      required: true
      reviewer: "cross_verified"
      result: "agreed"                  # agreed | reclassified | no_reviewer
      final_status: "completed"         # status confirmé après la réévaluation
      max_review_rounds: 1
```

`methodology_signals` est le canal par lequel le Worker signale les **lacunes de la méthodologie elle-même** découvertes pendant le travail.
Plusieurs lacunes (par ex. incomplete_spec + rule_gap) peuvent apparaître en même temps dans un même completion, c'est donc une **liste**.
Le Builder classe chaque élément individuellement.
Contrairement à un `scope_issue` ordinaire (un blocage de la tâche en cours), il désigne des candidats à l'amélioration des règles, du schéma ou des conventions.
À la passation, le Builder les charge dans le backlog et juge la promotion
(→ voir plus bas la section « Promotion Gate »).

`triage` est la classification appliquée avant que la sortie n'aille au Decision Inbox consulté par les humains. L'agent remplit `self_report`,
et la vérification croisée réévalue cette étiquette via `review_gate` (car un auto-rapport n'est pas fiable). Pour les règles, l'aiguillage selon le risque et le repli
en l'absence de réévaluateur, voir → `core/docs/fr/methodology/agent-operations.md` « Decision Inbox + porte de vérification de l'auto-rapport ».

---

## methodology-backlog.yaml — accumulation des candidats d'amélioration

Un fichier distinct qui accumule les candidats d'amélioration de la méthodologie. Il est séparé de decisions.yaml (l'enregistrement des décisions) :
le backlog contient des *candidats* et suit un autre cycle de vie (revue → adoption/rejet).
Cette section est la source de vérité du **schéma de champs et de l'enum de cycle de vie** du backlog.
Le flux des signaux et le Promotion Gate sont aussi définis par cette section (voir plus bas la section « Promotion Gate », DEC-2026-10-29-12).

```
project backlog:  $STRATA_VAULT/projects/{name}/backlog/methodology-backlog.yaml  # vault (Tier V)
core backlog:     $STRATA_VAULT/projects/strata-kit/backlog/methodology-backlog.yaml  # candidats d'amélioration de Strata Core
```

```yaml
methodology_backlog:
  - id: "MB-shop-api-2026-001"   # le préfixe {project} évite les collisions lors de la promotion centrale
    scope: "methodology"              # project | methodology
    source:
      project: "shop-api"
      type: "worker_rejection"        # worker_rejection | reviewer_finding | repeated_warning
      ref: "tasks/2026.05.31/01-sync/task-02.yaml"
    signal: "incomplete_spec"
    severity: "major"
    affected_core:                    # au moins 1 obligatoire si scope: methodology
      - "core/docs/fr/methodology/task-spec-schema.md"
      - "core/roles/agent-roles.yaml"
    summary: "Le Worker a jugé l'achèvement invérifiable faute de commande de test"
    proposed_action: "Ajouter un champ verification.commands au schéma de tâche"
    status: "open"                    # open → triaged → accepted | rejected → applied
    promoted_to: null                 # à la promotion, "$STRATA_VAULT/projects/strata-kit/backlog/methodology-backlog.yaml#<id>"
```

### Cycle de vie

```
open → triaged → accepted → applied
              → rejected
```

| Statut | Signification |
|------|------|
| `open` | Signal chargé, pas encore examiné |
| `triaged` | Le Builder a vérifié scope, doublons et affected_core |
| `accepted` | Adopté comme cible d'amélioration du Core (promu) |
| `rejected` | Jugé sans besoin d'amélioration (raison consignée) |
| `applied` | Appliqué à Strata Core, modèles/adaptateurs régénérés |

---

### Promotion Gate

Les éléments du backlog suivent un chemin de traitement différent selon `scope`.

- `scope: project` — traités comme candidats d'amélioration des règles, du layer-map, de AGENTS.md, du KB et des décisions de ce projet.
- `scope: methodology` — promus vers le backlog du core (`$STRATA_VAULT/projects/strata-kit/backlog/methodology-backlog.yaml`).

Pour les éléments `scope: methodology`, le Builder fait ce qui suit.

1. Vérifie s'il s'agit d'un doublon.
2. Vérifie que `affected_core` compte au moins 1 élément.
3. Ajoute un élément de promotion au backlog du core.
4. Consigne `promoted_to` dans l'élément du projet d'origine.
5. Tant que ce n'est pas répercuté dans le kit, laisse le status à `triaged` ou `accepted`. Une fois répercuté, inscrit `applied` et `applied_in` (commit·DEC).

Le jugement (`accepted`·`rejected`) revient à la personne. L'ancien backlog central de strata (`strata/methodology-backlog.yaml`) a été transféré vers le backlog du kit (DEC-2026-10-29-12).

## Liste de contrôle d'autonomie

Vérifiée par le Builder après avoir rédigé une spécification de tâche, avant de la remettre au Worker :

```
□ scope.layer est-il une couche unique ?
□ scope.can_reference correspond-il à layer-rules.yaml ?
□ scope.constraints inclut-il les contraintes applicables à ce domaine/cette couche ?
□ scope.nodes existe-t-il, et scope.docs_to_update correspond-il au résultat du résolveur de couverture ?
  (S'il n'y a pas de spécification propriétaire, en crée-t-on une dans deliverables, ou y a-t-il une raison de vide volontaire ?)
□ inputs.reference_files liste-t-il tous les fichiers dont le Worker a besoin ?
□ inputs.requirements est-il compréhensible sans explication orale ?
□ inputs.conventions résume-t-il les conventions de cette couche ?
□ deliverables.files liste-t-il tous les fichiers à créer/modifier ?
□ acceptance_criteria est-il sous une forme vérifiable ? (tests qui passent, 0 violation, etc.)
□ acceptance_criteria inclut-il la vérification de la conformité aux contraintes ?
□ acceptance_criteria inclut-il le traitement de docs_to_update (mise à jour de la spécification, ou doc_change: none + raison) ?
□ context_budget.max_reference_files ≤ 5 ?
```

**Si un seul élément n'est pas satisfait, la tâche n'est pas remise au Worker.**

Vérifiée par le Worker à la réception d'une tâche :

```
□ scope.layer est-il indiqué ?
□ Si scope.docs_to_update est vide, la raison du vide volontaire est-elle indiquée ?
□ Les fichiers de inputs.reference_files existent-ils réellement ?
□ inputs.requirements n'est-il pas vide ?
□ deliverables.files n'est-il pas vide ?
□ Y a-t-il au moins 1 acceptance_criteria ?
```

**Si un élément non satisfait est trouvé, la tâche est immédiatement renvoyée au Builder (signaler un scope_issue).**

---

## Politique de nettoyage des tâches

| Moment | Action |
|------|------|
| Tâche terminée | `status: completed` + remplir la section completion |
| Ordre de travail entièrement terminé | `status: completed` dans `_order.yaml` |
| Fin de sprint | Les dossiers de date terminés sont conservés (non supprimés) |
| Après 90 jours | Les dossiers d'ordres de travail terminés peuvent être archivés |

Les décisions clés d'une tâche terminée ont déjà été reversées dans la passation et la KB,
le fichier de tâche lui-même n'est donc conservé que comme **piste d'audit (audit trail)**.
