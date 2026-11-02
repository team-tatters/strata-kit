# Agent Operations (axe d'exploitation des agents)

> Référence : strata-kit `core/docs/fr/methodology/agent-operations.md` (migré le 2026-10-29 depuis strata `docs/04-agents/agent-operations.md`, DEC-2026-10-29-11).

> Le **troisième axe orthogonal** de Strata. Execution Mode (comment on travaille) → Verification Tier (qui vérifie) → **Agent Operations (quand, combien et comment on digère)**.
> La définition de Verification Tier a sa source of truth dans `core/docs/fr/methodology/verification-tier.md`.
> Couvre : les plages d'exploitation (batch de nuit), le budget (budget envelope), la structure multi-session, et la façon dont une personne digère la production en forte croissance (Decision Inbox + porte (gate) de validation des auto-déclarations).
> État : `draft` (conception convenue. Le packet du §1 et le CLI du ledger (`kb ledger`) du §5 sont implémentés. La vérification des résultats et la gate du Decision Inbox des §2–4 ne disposent d'aucun outil automatisé : l'agent-ops.py de l'ancien strata n'est plus utilisé depuis 2026-06 (DEC-2026-10-29-12). L'agent runner réel n'est pas implémenté)

## 0. Pourquoi c'est nécessaire

Execution Mode et Verification Tier traitent de « comment bien faire une tâche ».
Agent Operations traite du problème au-dessus : **la discipline d'exploitation qui évite que les personnes deviennent un goulot d'étranglement ou soient submergées quand on fait tourner de nombreux agents longtemps**.

Prémisse centrale (elle traverse tout cet axe) :

> Le but n'est pas de faire tourner beaucoup d'agents. Le but est de **limiter fortement l'unité de livraison, les rôles, les productions et la surface que la personne doit regarder**.
> Tout dispositif qui augmente la production (multi-session, batch de nuit) submerge la personne s'il n'existe pas de dispositif qui digère cette production (Decision Inbox, porte de validation).

Principes en bref :

1. Un relais envoie un **packet structuré**, pas la conversation entière.
2. La multi-session est exploitée **autour d'un Coordinator (hub-and-spoke)**, pas comme une conversation N:N.
3. Le travail de nuit est limité à un **budgeted batch**, pas à l'autonomie.
4. La personne ne regarde que le **Decision Inbox**, pas le raw output.
5. Les étiquettes que voit la personne ne sont pas des auto-déclarations, mais des **étiquettes rejugées par vérification croisée**.

Ce document est la source of truth des primitives méthodologiques de la famille runtime : **Relay Packet, Decision Inbox, review_gate, Shared Session Ledger**.
Les adapters/runtimes comme le hub Quilt ne redéfinissent pas ces primitives ; ils les consomment comme surfaces de routing, projection et execution.

---

## 1. Couches du Relay Packet (moins de tokens + moins d'erreurs)

L'envoi de la conversation entière est interdit. L'objectif n'est pas de réduire le nombre de tokens, mais d'**augmenter la densité d'information par token**.
(Procédure de revue croisée : `skills/strata.review/SKILL.md` ; l'envoi passe par le hub Quilt, `hub_send`)

```text
Level 0 : la question seule
Level 1 : question + conclusion actuelle + points en débat            ← par défaut
Level 2 : Level 1 + fichiers/lignes de preuve + résumé du diff  ← par défaut
Level 3 : texte intégral des extraits nécessaires
Level 4 : transcript complet (à titre exceptionnel seulement)
```

Par défaut, c'est Level 1–2. Si l'on jette la conversation en prose telle quelle, ce que l'autre côté doit juger devient flou.
Forme de packet recommandée :

```yaml
intent: "review"
decision_so_far: "La référence de Verification Tier a été séparée dans verification-tier.md"
open_questions:
  - "Le flux de Promotion Gate et la frontière du schéma de backlog concordent-ils ?"
evidence:
  - file: "core/docs/fr/methodology/verification-tier.md"
  - file: "core/docs/fr/methodology/task-spec-schema.md"
constraints:
  - "Ne pas mettre de noms d'outils dans les documents Core"
request:
  - "Ne signaler que 1 à 2 lacunes"
```

- **Joindre l'ancre** : lors de plusieurs allers-retours, pour que l'autre côté n'oublie pas l'accord et ne dérive pas, on joint à chaque fois `decision_so_far` (résumé fixe).
- **Bloquer les packets maigres** : si `evidence`/`request` sont vides, on avertit avant l'envoi — si un packet vide est envoyé, on risque de paraître Cross-Verified alors qu'aucune vérification n'a été faite. (Cas réel : un Reviewer ayant reçu un packet vide a correctement répondu « examen impossible »)

## 2. Multi-session (Model-A n · Model-B n)

C'est possible, mais les laisser dialoguer entre elles en N:N mène à l'explosion des tokens, à des revues en double et à une responsabilité floue.
Par défaut, c'est **hub-and-spoke**.

```text
Coordinator
  ├─ ModelA-Review-1
  ├─ ModelA-Research-1
  ├─ ModelB-CodeReview-1
  ├─ ModelB-Impl-1
  └─ ModelB-Contrarian-1
```

Les sessions ne parlent pas directement entre elles. Toutes déposent leur production dans la relay queue et le **Coordinator la rassemble**.

Structure interdite :
```text
Model A1 ↔ Model B1 ↔ Model A2 ↔ Model B2 ...   (le fan-out est facile, le fan-in est difficile)
```

Séparation des rôles :

| Rôle | Responsabilité | Limite d'autorité |
|------|------|----------|
| Primary | Mène le travail | — |
| Reviewer | Cherche les défauts | Ne tranche pas, signale seulement |
| Contrarian | Cherche les arguments contraires | Lié à adversarial verify |
| Summarizer | Compresse les productions | Interdiction de modifier le contenu |
| Archivist | Range decision/backlog | **Seulement jusqu'à `open→triaged`. `accepted/rejected` revient à la personne** |

> **Point clé** : le fan-out (multi-session) est facile et le fan-in (synthèse) est difficile. Sans point de convergence (Coordinator ou personne), on aggrave soi-même le problème du §4.

Règle de l'arbre de travail (git worktree) (DEC-2026-09-17-01) : même pour des Workers ou des sessions en parallèle, l'arbre de travail n'est créé **que si l'utilisateur a accepté cette proposition**. Le mode automatique est identique. Par défaut, l'exécution est séquentielle sur une seule branche du checkout que regarde l'utilisateur ; si un arbre de travail est vraiment nécessaire, on propose en un seul point la nécessité, le nom de la branche et le plan de nettoyage, puis on attend la réponse. À la fin, on garde la branche, on nettoie l'arbre de travail et on le signale. La règle de référence est `core/docs/fr/methodology/execution-modes.md` § Règle absolue 7.

### 2.1 Schéma des productions d'exécution

Il n'existe pas encore de runner qui exécute la multi-session elle-même. La production de plan que recevra le Coordinator suit le schéma ci-dessous, et la revue vérifie l'**interdiction des liens N:N**, l'enum des rôles et la limite d'autorité de l'Archivist (il n'existe pour l'instant aucun outil de vérification automatique).

```yaml
multi_session:
  coordinator: "human"        # human | agent
  sessions:
    - id: "review-1"
      role: "reviewer"        # primary | reviewer | contrarian | summarizer | archivist
      tool: "codex"           # adapter label, pas un enum de Core
      packet_ref: "$STRATA_VAULT/projects/{n}/relays/..."
      allowed_transitions: [] # archivist n'autorise que ["open->triaged"]
```

Interdit :
- `direct_peer_links` : lien où les sessions se parlent directement. S'il est trouvé, il est rejeté.
- Une transition où l'Archivist tranche jusqu'à `accepted/rejected/applied`.

## 3. Protocole du batch de nuit (22:00–08:00)

Ce n'est pas du travail autonome mais un **budgeted batch**. Pour ne pas rompre le principe « la décision revient à la personne », on sépare : **nuit = générer, jour = juger**.

### Avant 22 h — la personne prépare
```text
1. Choisir 3 à 5 work packets à traiter cette nuit
2. Indiquer dans chaque packet le périmètre/les interdits/le budget/la condition d'achèvement
3. Limiter le périmètre d'écriture autorisé (write_scope)
4. Définir les conditions d'arrêt
```

### Règles de l'agent de nuit
```text
- Aucune nouvelle décision d'architecture
- Aucun travail ayant un impact sur la production
- Aucun commit/déploiement/suppression (ou approbation séparée)
- Si c'est ambigu, s'arrêter et le laisser sous forme de question
- Chaque agent ne remet qu'un résumé final d'une page
- Toutes les productions attendent en needs_decision (aucune adoption avant cross_verified)
```

### budget envelope + limites strictes
```yaml
agent_budget:
  max_turns: 8
  max_files_read: 12
  max_output_lines: 80
  write_scope: ["assigned/paths/only"]
  stop_if:
    - "architecture decision required"
    - "test cannot run"
    - "scope expands beyond assigned files"
```

> **Priorité des garde-fous** : les limites strictes (`max_turns`/`max_files`/`write_scope`) sont la **première** ligne. L'arrêt sur jugement propre (`stop_if: si c'est ambigu`) est la **seconde** — car un agent qui ne reconnaît pas l'ambiguïté ne s'arrête pas. La première doit toujours fonctionner.

### 08 h — ce que regarde la personne
```text
- Éléments nécessitant une décision / fichiers réellement modifiés / résultats des tests / risques / productions à jeter / candidats pour la prochaine instruction
```

Les tokens/le temps se gèrent non pas par des chiffres exacts mais par un **budget envelope par session + un rythme horaire** (pour ne pas épuiser la limite à l'aube et créer un vide).

### 3.1 Schéma des productions du batch

Un batch de nuit se fixe d'abord par un **batch spec**, pas par un runner. Avant de démarrer, on vérifie l'existence des packets et les
champs du hard budget (il n'existe pour l'instant aucun outil de vérification automatique). Quel que soit l'outil d'exécution, on ne démarre pas de batch de nuit sans ce spec.

```yaml
night_batch:
  window: "22:00-08:00"
  packets:
    - id: "nb-001"
      packet_ref: "$STRATA_VAULT/projects/{n}/relays/..."
      owner: "primary"
  budget:
    max_turns: 8
    max_files_read: 12
    max_output_lines: 80
    write_scope:
      - "assigned/paths/only"
    stop_if:
      - "architecture decision required"
      - "test cannot run"
```

Toute production de nuit est traitée comme `review_gate.required: true` à la gate du §4.

## 4. Decision Inbox + porte de validation des auto-déclarations (le cœur de cet axe)

Le goulot d'étranglement de la personne n'est pas « lire » mais « **juger** ». On transforme la sortie des agents non pas en information mais en **unité jugeable**.
La surface que regarde la personne est **un seul Decision Inbox**. Le raw output est seulement stocké.

### 4.1 Format de sortie imposé (self-report)
```yaml
result:
  status: completed | blocked | needs_decision | rejected
  one_line: "ce qui a été fait"
  changed_files: []
  evidence: []          # pointer obligatoire (explication longue sans decision interdite)
  tests: []
  risks:
    - severity: high | medium | low
      summary: ""
      action_needed: ""
  decisions_needed: []
  discardable_notes_ref: "..."   # le raw output est seulement stocké ici
```

### 4.2 Porte de validation des auto-déclarations (Self-Report Validation Gate)

**Problème** : le `status`/`risks` ci-dessus est classé par l'agent **lui-même**. S'il sous-estime son propre risque (high→low), dès que la personne ne regarde que l'Inbox, un élément mal classé est enfoui et passe.
**Base mesurée** : l'auto-déclaration n'est pas fiable — le modèle n'inscrit pas comme un fait une affirmation personnelle sans preuve, et quand on lui donne preuve + code, il vérifie puis accepte.

**Solution** : **avant** l'entrée dans le Decision Inbox, le relais (vérification croisée) rejuge **uniquement les étiquettes de triage**.

```text
Cible de la vérification :
  Réexaminer tout le raw output ❌          (cela anéantirait l'économie de tokens du §1)
  Rejuger status / risk / decisions_needed / evidence pointer ✅
```

Flux :
```text
Agent self-report
  → Relay reclassifies (étiquettes seulement)
  → agree    → entre dans le Decision Inbox
  → disagree → promu en "needs_human_decision" (vers la personne)
```

Prévention des boucles infinies :
```yaml
review_gate:
  required: true
  reviewer: cross_verified
  max_review_rounds: 1            # interdit qu'un Reviewer rappelle un Reviewer
  disagreement_policy: human_decision   # désaccord = promu directement dans l'Inbox
```

### 4.3 Branchement selon le risque (on ne rejuge pas tout)

Tout rejuger coûte cher. On sépare selon le risque.

**Re-jugement obligatoire :**
```text
- status: completed alors que des fichiers ont changé
- risk: high ou unknown
- decisions_needed présent
- lié à architecture / schema / migration / deletion / security
- productions du batch de nuit (toutes)
- changements de methodology_backlog / decisions
```

**Échantillonnage (ou omission) :**
```text
- low risk / résumés de documents / résultats d'exploration / travaux où seuls des tests ont été exécutés
```

### 4.4 Repli en l'absence de rejugeur (valeur par défaut sûre)

`reviewer: cross_verified` suppose un rejugeur d'une autre famille de modèles.
**S'il n'y a pas de rejugeur** (p. ex. aucune session cross en marche la nuit), la vérification n'a pas pu être faite, donc
l'élément est automatiquement classé **`needs_human_decision`** — faute d'avoir pu vérifier, on ne le laisse pas passer et on le remonte à la personne.

### 4.5 Ce que fait la personne chaque jour (Agent Output Triage)
```text
1. Ce qu'on approuve  2. Ce qu'on rejette  3. Ce sur quoi on pose une question de plus  4. Ce qu'on jette
```
Règles : le raw output est seulement stocké, la personne ne voit que le digest, le digest doit avoir des evidence pointers, pas de texte long sans decision.

### 4.6 Exemple de schéma (extension de task completion)
```yaml
triage:
  self_report:
    status: completed
    risk: low
    decisions_needed: []
  review_gate:
    required: true
    reviewer: cross_verified
    result: reclassified            # agreed | reclassified | no_reviewer
    final_status: needs_decision
    reason: "classé low, mais comprend un changement de schema"
    max_review_rounds: 1
```

### 4.7 Règles de jugement de la gate

Il n'existe pour l'instant aucun outil de vérification automatique (l'agent-ops.py de l'ancien strata n'est plus utilisé depuis 2026-06, DEC-2026-10-29-12). Les règles de jugement ci-dessous sont appliquées par la personne ou le Builder lorsqu'ils préparent la review et le Decision Inbox.

Jugement de la gate :
- `completed` + fichiers modifiés, `risk: high|unknown`, `decisions_needed`, signaux architecture/schema/migration/security/decision, et productions du batch de nuit ont `review_gate.required: true`.
- S'il n'y a pas de reviewer, `result: no_reviewer`, `final_status: needs_decision`.
- `max_review_rounds` vaut toujours 1.
- S'il y a des `changed_files`, un `evidence` pointer est obligatoire.
Un item du Decision Inbox n'est exposé que sous une seule action parmi `approve | reject | question | discard`. Le raw output est
stocké dans `discardable_notes_ref` et l'Inbox ne contient qu'un pointer.

---

## 5. Shared Session Ledger (registre de session partagé)

> La **source unique de vérité (source of truth)** permettant à trois acteurs (**user / primary / reviewer**) de partager un même flux de demande et de collaborer.
> Les adapters propres à chaque outil associent les rôles `primary`/`reviewer` à de vraies sessions d'outil. Le schéma de Core n'a pas de noms d'outils comme enum.
> Ce n'est pas la mémoire de la session du reviewer mais ce fichier qui détient le contexte — c'est l'application au relais du premier principe de Strata (« la session est consommable, le document est persistant »).

### 5.1 Pourquoi un ledger (la solution de niveau supérieur pour la gestion de la session du reviewer)

Quand un relais tourne longtemps, « comment maintenir la session du reviewer » devient un problème. Mais **si l'unité de vérité est le ledger partagé plutôt que la session du reviewer**, ce problème disparaît :

- La session du reviewer **peut être volatile** — le contexte reste dans le ledger, pas dans la mémoire du reviewer.
- Le `decision_so_far` / `evidence` / `open_questions` du prochain relay packet sont **générés depuis le ledger**, et non depuis la mémoire du reviewer (packet du §1).
- Quel que soit l'outil avec lequel il commence, l'utilisateur lit le même ledger et poursuit (indépendamment de l'outil et du point de départ).

> **Cependant, la règle de réinitialisation du reviewer (autour du §1) n'est pas abandonnée.** Le ledger résout le problème du *maintien du contexte*, mais
> la **contamination** où le reviewer mêle à son propre jugement **d'anciens accords absents du packet** est une question distincte. La réinitialisation est conservée, rétrogradée de « pour maintenir le contexte » à
> **« hygiène de prévention de la contamination »** (le but est différent, donc elle ne disparaît pas même s'il existe un ledger).

### 5.2 Emplacement · format

```text
Emplacement : $STRATA_VAULT/projects/{project}/sessions/session-{date}-{slug}.md
      (hors de Core, persistant, partagé, adapté à l'indexation. .strata/local est un état local à la machine, donc inadapté)
Format : fichier Markdown + entrées en bloc YAML par actor (lisible par l'humain et indexable par la machine)
frontmatter obligatoire : session_id · project · status · actors · topic · created · next_session · nodes
      (nodes = les nœuds thématiques auxquels appartient cette session — la gate de couverture du §5.7 les déduit des fichiers modifiés et les compare)
actor: user | primary | reviewer | coordinator | archivist
tool: optional adapter label    (ex. claude | codex — pas un enum de Core)
```

### 5.3 Schéma d'entrée

Chaque entrée est un en-tête `## [actor] {ISO8601 timestamp}` + un bloc YAML. Append-only, dans l'ordre chronologique.

```markdown
## [user] 2026-06-01T12:34:00+09:00
​```yaml
intent: "define shared ledger"
request: "Faire partager à Claude/Codex/User le même flux de demande"
decision: null            # décision de l'utilisateur / jugement d'arrêt (s'il y en a)
​```

## [primary] 2026-06-01T12:40:00+09:00
​```yaml
tool: "claude"                         # optional adapter label
from_user: "proposition de shared ledger"     # quel problème a été reçu
action: "analysé avec un cadre de niveau supérieur"        # comment il a été traité
to_reviewer:                        # résumé du packet envoyé au reviewer (null s'il n'y en a pas)
  intent: "review"
  decision_so_far: "ledger is source of truth"
  questions: []
outcome: "accepter | réfuter | suspendre"         # traitement de la réponse du reviewer (s'il y en a une)
​```

## [reviewer] 2026-06-01T12:45:00+09:00
​```yaml
tool: "codex"                          # optional adapter label
reviewed: "ledger proposal"          # ce qui a été examiné
verdict: "agree | agree_with_caveat | disagree"
risks:
  - "single writer required"
returned: "l'opinion clé renvoyée"
​```

## [primary] 2026-06-01T15:10:00+09:00
​```yaml
action: "signal de redémarrage — ligne d'alerte dépassée | deux échecs sur une hypothèse"
confirmed: ["fait confirmé (et ce qui l'a confirmé)"]
assumed: ["supposition non encore confirmée"]
discarded: ["hypothèse écartée (et pourquoi)"]
​```

## next_session
​```yaml
next: "session-2026-06-01-qwer.md"   # imposé au close (null interdit — évite la rupture de chaîne)
reason: "raison du passage au flux suivant"
​```
```

L'entrée `[primary] 2026-06-01T15:10` ci-dessus est une entrée de redémarrage. Quand un signal de redémarrage (session-splitting 5.1) porte le travail vers une nouvelle session, elle porte les trois mêmes champs que la section faits et hypothèses de la passation (confirmed, assumed, discarded).

### 5.4 Writer unique + verrou de fichier (B3 — empêcher la contamination par écriture concurrente)

Pour ne pas reproduire dans le ledger la contamination du fichier de session que nous venons de mesurer (deux processus faisant un append sur un même fichier en même temps) :

- Les processus d'agent propres à chaque outil **n'écrivent pas directement le fichier du ledger.** Ils n'écrivent que par le CLI d'entrée unique (`python3 "$STRATA_KIT/kb" ledger`).
- **CLI unique ≠ concurrence unique** : le CLI doit contenir en interne un **verrou de fichier (flock)**. Même si plusieurs adapters appellent `append` presque simultanément, les appels sont sérialisés.
- Le ledger est un **fichier distinct** des fichiers de session TUI vivants (`~/.claude/...`, `~/.codex/...`) — il est sans rapport avec l'occupation du TUI, donc il n'est pas visé par le garde lsof.

### 5.5 Déclencheurs d'append (B1 — qui le laisse, et quand)

Les entrées ne sont pas laissées automatiquement mais sur des **déclencheurs explicites** :

```text
- Avant/après un relais : entrée primary (to_reviewer) à l'envoi du packet, entrée reviewer (verdict) à la récupération de la réponse
- Décision de l'utilisateur : entrée user (decision) quand le user juge d'adopter/rejeter/arrêter
- Fin du travail : écrire le pointeur next_session au close (§5.6)
```

### 5.6 Chaînage des sessions (B2 — next_session imposé)

À la fermeture d'un ledger, `next_session.next` **doit** être renseigné. On ne ferme pas avec `null` —
si la chaîne est rompue, le prochain acteur ne peut pas poursuivre le flux (même schéma que le « un pending doit avoir un blocker » de la passation (handoff)).
S'il n'y a pas de travail à poursuivre, on indique `next: "none"` + `reason` pour laisser trace qu'il s'agit d'une *fin intentionnelle*.

### 5.7 Gate de couverture (en fin de session — le code a changé mais pas la forme ?)

Quand une session se ferme, la gate de fin de session (le handoff generator et le validate/close du CLI du ledger) vérifie ce qui suit **au même endroit** que l'avertissement sur les enregistrements de decision non commités :

```text
Entrée : la liste des fichiers de code modifiés par cette session (task completion.files_modified/created, sinon le diff du dépôt)
① Pour chaque fichier modifié, trouver la spécification qui possède cette surface via covers (résolveur de couverture)
② Rassembler les nodes des spécifications propriétaires et les comparer aux nodes du frontmatter du ledger et de la passation — en cas d'oubli, avertir pour qu'on les complète
③ Si une spécification propriétaire n'a pas été mise à jour dans cette session (updated antérieur au début de la session) et que
   le frontmatter n'a pas doc_change: none + doc_change_reason → avertissement + consigné comme dette de ce nœud
④ S'il existe des fichiers modifiés sans spécification propriétaire → avertissement « surface sans propriétaire » (il faut créer une spécification ou étendre covers)
```

- **C'est un avertissement, pas un blocage.** Il est du même niveau que l'avertissement sur les enregistrements non commités. Mais s'il est ignoré, il reste sur la face « dette » de la page du nœud, où la personne suivante le voit.
- `doc_change: none` suit le même principe que `next: "none"` du §5.6 — valeur vide interdite, un none explicite + motif.
- La référence de la dette n'est pas la page mais le fait même que « la session n'a pas de déclaration doc_change ». Il n'y a que deux façons de rembourser la dette : mettre à jour la spécification (mettre à jour updated·sources), ou consigner rétroactivement le motif doc_change dans le document de cette session.
- Format des valeurs : section « Champs de nœud et de couverture » de `core/docs/fr/knowledge-base/document-format.md`. C'est un signal distinct de la politique de revue (90 jours).

`nodes` fait partie des champs obligatoires du frontmatter du ledger (§5.2). La valeur est déduite par le résolveur en ②, et seules les sessions sans changement de code la font choisir directement par une personne.

---

## 6. Relation avec les autres axes

```text
②multi-session (fan-out) ┐
③batch de nuit (générer)  ├→ ④Decision Inbox + porte de validation (fan-in) ← sans elle, ①②③ submergent la personne
①relais (densité↑)       ┘
⑤ledger ← la source de vérité partagée où chaque acte de ①~④ est consigné (indépendamment de l'outil et du point de départ)
```

- **Execution Mode** : se contente de référencer Agent Operations. (La détermination/transition de mode est dans `core/docs/fr/methodology/execution-modes.md`)
- **Verification Tier** : le `reviewer: cross_verified` de la porte de validation utilise tel quel le Cross-Verified Tier de `core/docs/fr/methodology/verification-tier.md`.
- **Methodology Feedback Loop** : la frontière `open→triaged` de l'Archivist suit la Promotion Gate de `core/docs/fr/methodology/task-spec-schema.md` et le backlog lifecycle. Le jugement (accepted) revient à la personne.
- **Revue croisée** : le packet du §1 est produit par `skills/strata.review/SKILL.md` et envoyé à un reviewer de contexte neuf (Quilt `hub_send`). L'ancien outil de relais Claude↔Codex (strata bridge) est une implémentation passée et n'est plus utilisé.

## 7. Priorité d'adoption

```text
①structurer le relay packet   → possible tout de suite (gain net, risque faible)
④Decision Inbox + gate        → clé maîtresse (le garde-fou de ②③, à concevoir en premier)
⑤Shared Session Ledger        → avant de faire tourner le relais sur plusieurs allers-retours (writer unique + verrou en prérequis)
②multi-session / ③batch de nuit → après la conception de ④⑤ (si on le fait avant, la personne devient goulot / est submergée)
```

Les pièces existent déjà : la revue croisée (strata.review, filtre de vérification croisée) + le backlog lifecycle (file de jugement) + Verification Tier (porte de confiance). Le fan-in guardrail (vérification automatique des productions) n'existe pas encore : l'ancien agent-ops.py n'est plus utilisé. Ce n'est pas de l'invention mais de l'**assemblage**.

## 8. Points en suspens

- Mesurer le coût réel en tokens du re-jugement de `review_gate` (pour vérifier l'hypothèse de la gate mince).
- Savoir si le Coordinator sera un agent ou si la personne le cumule (selon l'échelle de la multi-session).
- Le runner multi-session et le runner de batch de nuit ne sont pas implémentés. L'implémentation actuelle va seulement jusqu'à la validation des productions de plan/batch/self-report/Inbox et à la normalisation de la gate.
- Où conserver `discardable_notes_ref` (raw output) — possibilité de réutiliser relays/ du vault.
- `kb ledger` (anciennement session-ledger.py) est implémenté (append/read/close/validate + flock). Le reste de l'affinage est dans la file de vérification croisée.
- La gate de couverture du §5.7 est implémentée — branchée au handoff generator (vérification avant génération + prefill des nœuds déduits) et au validate/close du CLI du ledger (avertissement), et les pages de nœud sont régénérées après close·handoff. Le champ obligatoire `nodes` du ledger est en période d'introduction, donc de **niveau avertissement** (la promotion en erreur viendra après la rétroactivité). La rétroactivité des documents existants (nodes/covers) et le toc.yaml par projet ne sont pas commencés (methodology-backlog MB-strata-2026-007).
- Comment relier les déclencheurs de réinitialisation du reviewer (topic_change / max_rounds 3–5 / decision_accepted / packet_drift / high_risk) aux entrées du ledger.
