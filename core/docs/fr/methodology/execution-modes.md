# Modes d'exécution (Execution Modes)

> Canonique : strata-kit `core/docs/fr/methodology/execution-modes.md` (migré le 2026-10-29 depuis strata `docs/04-agents/execution-modes.md`, DEC-2026-10-29-11).

> Définit les modes d'exécution duaux de la méthodologie Strata.
> Chaque session doit déclarer explicitement son mode d'exécution au démarrage.

## Principes

- **Le mode par défaut est Task Mode** — si rien n'est déclaré, la session est traitée comme Task Mode
- **Verbal Mode est une exception délibérée** — il ne peut être utilisé que s'il est choisi explicitement
- **Le changement de mode est à sens unique** — Verbal → Task est autorisé, Task → Verbal est interdit

> **Correspondance avec les modes de travail (2026-10-29, DEC-2026-10-29-15·19)** : les quatre modes de travail de la skill d'entrée (étape 4 de using-strata) découpent ces deux modes. Verbal = lecture seule (investigation, questions, revue) + un changement en session unique qui se termine sans fichier de tâche ; Task = multisession (travail avec un ordre) + orchestration (plusieurs sessions ou rôles en parallèle). Les obligations d'une session (fichier actif, passation, ordre) sont fixées par le mode de travail ; les critères quantitatifs ci-dessous servent à juger si le travail peut se terminer en Verbal.
- **Résumer et confirmer avant de modifier l'état** — pour un travail difficile à annuler ou qui modifie un état observable (modifier des fichiers, injecter dans une session, appeler une CLI externe, commit/déploiement), on présente d'abord un résumé de ce qui sera fait et on n'exécute qu'après la confirmation de l'utilisateur

## Définitions des modes

### Task Mode (par défaut)

Le mode dans lequel le Builder rédige les spécifications `_order.yaml` + `task-{nn}.yaml` et le Worker exécute à partir de ces spécifications.

**Quand il s'applique :**
- Plans d'exécution par sprint
- Implémentation de fonctionnalités sur plusieurs sessions
- Modification de 3 fichiers ou plus
- Impact sur 2 couches ou plus
- Établissement d'un nouveau pattern d'architecture

**Obligations :**
- Rédiger `_order.yaml` (l'ordre de travail)
- Rédiger chaque `task-{nn}.yaml` (la spécification d'exécution du Worker)
- Mettre à jour TASK_TRACKER.md
- Rédiger le document de passation (handoff)
- Renvoyer les décisions d'architecture vers la KB

### Verbal Mode (exception)

Le mode dans lequel le Builder exécute directement, ou traite rapidement le travail par instructions orales.

**Quand il s'applique :**
- Idéation, exploration, revue de conception
- Modification d'un seul fichier
- Correctif de bug (urgent)
- Modification de documents, changements de configuration
- Travail pouvant être terminé en 10 tours

**Obligations :**
- Aucune spécification de tâche nécessaire
- Aucune mise à jour de TASK_TRACKER nécessaire
- La passation est facultative (à consigner s'il y a des décisions)
- **L'enregistrement d'un enregistrement de décision (CLI decision writer) lorsqu'une décision est prise ne peut pas être levé** (règle absolue quel que soit le mode — `decisions.yaml` est un index généré, ne jamais le modifier à la main)

## Critères de choix du mode (quantitatifs)

```
IF (fichiers modifiés ≤ 3) AND (couches touchées ≤ 1) AND (tours prévus ≤ 10)
   AND (nouveaux domaines = 0) AND (phases d'exploration ≤ 1):
    → Verbal Mode autorisé
ELSE:
    → Task Mode imposé
```

| Indicateur              | Verbal autorisé | Task imposé |
| ----------------------- | --------------- | ----------- |
| Fichiers modifiés       | ≤ 3             | 4+          |
| Couches touchées        | 1               | 2+          |
| Tours prévus            | ≤ 10            | 11+         |
| Nouveaux domaines       | 0               | 1+          |
| Phases d'exploration    | ≤ 1             | 2+          |

**Verbal n'est autorisé que si toutes les conditions sont dans la plage Verbal. Si une seule est dépassée, Task est imposé.**

## Déclaration du mode

Au démarrage de la session, on consigne le mode dans le fichier de cette session `.strata/local/active/{session}.yaml`, et l'on écrit l'identifiant de session du harnais (Claude Code : `CLAUDE_CODE_SESSION_ID`) dans `harness_session_id` — l'en-tête de démarrage et la restauration après compaction trouvent le fichier de cette session par ce champ ou par le nom du fichier :

```yaml
harness_session_id: "9496c8b3-…"   # CLAUDE_CODE_SESSION_ID
session:
  date: "2026-04-23"
  mode: "verbal"              # verbal | task
  declared_scope: "Revue de la conception du debounce et briefing"
  escalation_threshold: 3     # passer en task mode si plus de fichiers que ce nombre sont touchés
  order_ref: null              # chemin de _order.yaml en task mode
```

## Changement de mode (Verbal → Task)

Lorsqu'une session a démarré en Verbal mais que son périmètre a grandi :

1. Le détecter lors de l'auto-diagnostic à 5 tours du Builder (vérifier le nombre de fichiers et de couches)
2. Signaler à l'utilisateur qu'« un passage en Task Mode est nécessaire »
3. Rédiger `_order.yaml` — inclure le champ `escalated_from: "verbal"`
4. Consigner le travail déjà terminé dans la section `completed_before_spec` de `_order.yaml`
5. Poursuivre le travail restant à partir des spécifications de tâche

```yaml
# _order.yaml (au moment du passage)
order:
  id: "2026.04.23-01"
  title: "Synchronisation MongoDB du debounce"
  escalated_from: "verbal"
  completed_before_spec:
    - "Ajout de l'opération SET à CacheGenericOperator (terminé en phase verbal)"
  tasks:
    - id: "task-01"
      title: "Implémenter DirtyMarkService"
      # ... les tâches suivantes ont une spécification normale
```

## Stratégie d'attribution des modèles

Les tâches du Worker indiquent le **niveau de raisonnement (reasoning tier)** auquel elles s'exécutent. On écrit un niveau, pas un nom de modèle précis ; la correspondance niveau → modèle relève de l'adaptateur d'outil (neutre vis-à-vis de l'outil).

### Critères d'attribution par niveau de raisonnement

| Niveau | Critère d'attribution | Coût relatif | Travail typique |
|--------|-----------------------|--------------|-----------------|
| **deep** (raisonnement élevé) | Établir un nouveau pattern, raisonnement inter-couches, refactorisation complexe | Élevé | Conception d'architecture + implémentation, nouveaux systèmes |
| **standard** (standard) | Suivre un pattern existant, CRUD sur une seule couche, tests, documentation | Faible | REST Docs, ajout d'un QueryService, documents de KB |
| **light** (léger) | Recherche de documents, consultation de règles, résumés simples | Le plus bas | Recherche dans la KB, résumés de passation |

> **La correspondance niveau → modèle est de la responsabilité de l'adaptateur d'outil, pas de Core.** (Exemple d'adaptateur — Claude : `deep→Opus`, `standard→Sonnet`, `light→Haiku`. Cette correspondance relève du contexte de l'adaptateur et n'est pas une règle de Core.)

### Arbre de décision pour le choix du modèle

```
La tâche suit-elle un pattern existant ?
  ├─ YES → Existe-t-il une implémentation de référence claire ?
  │         ├─ YES → standard
  │         └─ NO  → deep (le pattern doit être interprété)
  └─ NO  → Faut-il un nouveau jugement d'architecture ?
            ├─ YES → deep
            └─ NO  → standard (simple code nouveau)
```

### Indiquer le niveau dans une spécification de tâche

```yaml
execution:
  model_tier: "standard"
  model_reason: "Suit le pattern REST Docs existant, aucun nouveau jugement nécessaire"
```

`model_reason` est obligatoire. Le Builder doit indiquer la raison du choix du modèle afin que la session suivante puisse appliquer le même critère.

## Niveau de raisonnement par défaut de chaque agent

| Agent | Niveau par défaut | Modifiable |
|-------|-------------------|------------|
| Builder | deep | Non (l'orchestration exige toujours un raisonnement de haut niveau) |
| Worker | Fixé par tâche | Oui (deep ou standard) |
| Supporter | light/standard | Oui (light pour la recherche, standard pour les résumés) |

> L'adaptateur d'outil fait correspondre un modèle précis au niveau (voir la note « correspondance niveau → modèle » ci-dessus). Core ne spécifie que le niveau.

## Axe de vérification (Verification Tier)

L'axe de vérification est orthogonal au mode d'exécution. Le mode d'exécution porte sur *la façon de travailler* ; l'axe de vérification porte sur *qui vérifie le résultat*.
Les valeurs de l'enum sont `solo | self_verified | cross_verified`.
Les définitions, les valeurs par défaut et la plage dans laquelle `cross_verified` est obligatoire lors de la modification d'une source de vérité (SoT) de Core sont régies par `core/docs/fr/methodology/verification-tier.md`, qui est la source of truth.
La revue Cross-Verified se fait avec `skills/strata.review/SKILL.md` (il envoie une fois un review packet à un reviewer de contexte neuf).

## Boucle de rétroaction méthodologique (Methodology Feedback Loop)

Les lacunes méthodologiques repérées par un Worker/Reviewer sont signalées en tant que `methodology_signals`, et le Builder les consigne dans le backlog et les promeut.
Le flux et la Promotion Gate sont régis par la section « Promotion Gate » de `core/docs/fr/methodology/task-spec-schema.md`, qui est la source of truth.
Les schémas de champs de `methodology_signals` et de `methodology-backlog.yaml` sont définis par `core/docs/fr/methodology/task-spec-schema.md`.

## Axe d'exploitation (Agent Operations)

Au-delà du mode d'exécution et de l'axe de vérification, la discipline d'exploitation pour faire tourner des agents **en nombre et longtemps** est traitée comme un axe distinct :
multi-session (hub-and-spoke), traitement par lots nocturne (budgeted batch), Decision Inbox et porte de vérification auto-déclarée.
→ `core/docs/fr/methodology/agent-operations.md` (ce document ne fait que renvoyer ; les règles y sont définies)

## Règles absolues (quel que soit le mode)

> **Cette section n'est pas la source canonique** (DEC-2026-10-29-19). Les règles qui s'appliquent à un projet sont fixées par la constitution (les articles de `core/constitution/constitution.yaml`) et les cartes que le projet a adoptées (`must_cards` dans `.strata/kit/registry.yaml`, écrit par l'assistant), et les consignes générées (AGENTS.md) portent cet ensemble. La formulation canonique de chaque règle est la carte dans `core/cards/`.
> Cette section conserve le texte d'origine dont ces cartes sont issues et ses fondements (incidents et raisons). Depuis la constitution 1.2.0, les règles 5 et 7 ne sont plus des articles mais des must adoptables qui ne s'appliquent que si le projet les adopte. Pour changer une règle, on modifie les cartes et la constitution (avec un enregistrement de décision) ; on ne modifie pas cette section.

Texte d'origine (2026-09-30, la liste appliquée à toutes les sessions à l'époque de DEC-2026-09-30-02) :

1. **Présenter un résumé de ce qui sera fait et obtenir la confirmation de l'utilisateur avant de modifier l'état**
   - Périmètre : modifier des fichiers, injecter des fichiers de session ou des relais, appeler des CLI externes, commit/déploiement/suppression, tâches de longue durée, et tout travail qui touche aux coûts, aux permissions ou aux données
   - Le résumé comprend le but, le travail à exécuter, l'étendue de la modification/de l'impact, la méthode de vérification et les conditions de retour arrière/d'interruption
   - Une investigation qui ne modifie pas l'état, comme une simple consultation, une recherche ou la lecture de fichiers, est autorisée à titre d'exception
   - **semantic vs mechanical** : une modification semantic qui change le sens, les règles ou les contrats exige une approbation. Une modification mechanical qui préserve le sens (faute de frappe, lien, format) est candidate à l'autorisation automatique **uniquement si elle peut être prouvée de façon static**. En cas d'ambiguïté, on la traite comme nécessitant une approbation. Le jugement « mechanical » d'un LLM lui-même n'est pas utilisé comme fondement d'une autorisation automatique.
2. **Enregistrer immédiatement un enregistrement de décision lorsqu'une décision d'architecture est prise** (CLI decision writer — l'index et la note DEC du vault sont régénérés automatiquement)
3. **Pas de violation de couche** — la force avec laquelle le harnais la bloque est fixée par le niveau d'application du projet (DEC-2026-10-29-17). Quel que soit le niveau, l'agent n'écrit aucune nouvelle violation
4. **Respecter les conventions de nommage** — un hook avertit
5. **Utiliser uniquement Soft Delete** — adoptable (constitution 1.2.0, DEC-2026-10-29-14) : s'applique lorsqu'un projet doté d'un stockage de données l'adopte
6. **L'état de la session, le travail en cours et les passations sont conservés dans des fichiers, pas dans le contexte de la conversation** — s'applique aux sessions qui modifient l'état ; une session en lecture seule n'a pas d'état à laisser (DEC-2026-10-29-15) — lorsqu'une session est interrompue, on consigne l'état courant dans le `.strata/local/active/{session}.yaml` de cette session (le fichier unique `active-task.yaml` est l'ancienne forme, lue seulement quand aucun fichier par session n'existe), et l'on conserve les passations et l'historique de travail dans le vault
7. **Ne créer un arbre de travail (git worktree) qu'avec l'accord de l'utilisateur** (DEC-2026-09-17-01) — adoptable (constitution 1.2.0) : s'applique s'il figure dans la liste d'adoption par défaut de l'utilisateur ou si le projet l'adopte
   - Cela vaut aussi en mode automatique. L'isolation par arbre de travail de l'adaptateur d'outil (par exemple l'outil Agent de Claude Code avec `isolation: "worktree"` et `EnterWorktree`) comme `git worktree add` sont tous deux concernés
   - Par défaut, on travaille séquentiellement sur une seule branche dans le checkout que voit l'utilisateur. Même avec plusieurs Workers, on les exécute dans l'ordre dans le même checkout
   - Seulement lorsqu'un arbre de travail est vraiment nécessaire pour des sessions ou des Workers en parallèle, on propose la nécessité, le nom de la branche et le plan de nettoyage comme un seul élément, et on ne le crée que s'il est accepté. Une acceptation ne vaut que pour cette proposition
   - Un arbre de travail créé avec accord est nettoyé à la fin de la tâche en conservant la branche, et l'on indique l'emplacement et la branche
   - Raison : séparer le travail en arbres de travail empêche la revue et l'examen de ce que l'agent a écrit de fonctionner correctement, l'utilisateur ne peut pas vérifier directement les modifications et l'historique de travail, et le suivi de la forme du code devient difficile
8. **Un déploiement effectué pour confirmer une hypothèse est limité aux environnements que seul un déploiement peut reproduire** (DEC-2026-09-18-01, strata)
   - On n'utilise pas un déploiement pour confirmer une hypothèse que la lecture du code, les logs, les tests unitaires ou une exécution locale permettent de confirmer. Mettre quelque chose sur un environnement partagé (dev, stage) ne sert qu'à confirmer un phénomène qui ne se reproduit que dans cet environnement (infrastructure, routage, intégration avec d'autres services, données réelles)
   - Avant un déploiement, on indique ce que l'on veut confirmer, en séparant les faits confirmés des hypothèses, et l'on joint la façon de revenir en arrière (un commit de revert, l'image précédente)
   - Une modification qui touche une autre ligne ou d'autres utilisateurs, comme l'authentification, le routage ou les sessions, n'est mise en ligne qu'après avoir été mesurée avec les parcours utilisateur de cette ligne (par exemple, à la fois la connexion 2.0 et la connexion 3.0)
   - Raison : le 2026-09-18, une route de passerelle a été promue sur stage sur une simple hypothèse et la connexion 2.0 a cessé de fonctionner, et les déploiements qui corrigeaient l'hypothèse puis remontaient en ligne se sont répétés plusieurs fois dans la journée. Un déploiement prend aussi du temps à annuler et bloque le travail des autres
9. **Pour un élément en attente (pending) d'une passation, écrire à la fois le blocker et la condition unblocked_by**
   - Écrire seulement « en attente » est interdit. Si la session suivante ne sait pas ce qui est attendu, l'élément en attente est simplement reporté
