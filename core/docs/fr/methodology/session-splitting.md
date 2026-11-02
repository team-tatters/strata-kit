# 02 — Guide de découpage des sessions

> Canonique : strata-kit `core/docs/fr/methodology/session-splitting.md` (migré le 2026-10-29 depuis strata `docs/02-session-splitting.md`, DEC-2026-10-29-11).

> Document que le Builder doit consulter avant de rédiger un ordre de travail.
> Le découpage des sessions est la stratégie la plus efficace pour « éviter la perte de contexte ».

## 1. Matrice de décision de découpage

### 1.1 Critères quantitatifs

| Indicateur | Session unique | 2-3 sessions | 4+ sessions |
|---|---|---|---|
| Fichiers modifiés | ≤15 | 16-40 | 40+ |
| Couches affectées | 1-2 | 3 | 4+ |
| Fichiers de référence | ≤10 | 11-25 | 25+ |
| Tours de conversation prévus | ≤20 | 21-40 | 40+ |
| Nouveaux domaines | 1 | 2 | 3+ |
| Étapes d'exploration nécessaires | ≤2 | 3-4 | 5+ |

### 1.2 Critères qualitatifs

**Situations qui exigent un découpage immédiat :**
- « D'abord étudier A, puis décider de la direction B selon le résultat » → session d'exploration + session d'implémentation
- « Refactoriser le code existant tout en ajoutant une nouvelle fonctionnalité » → session de refactorisation + session de fonctionnalité
- « Modifier simultanément le frontend et le backend » → session FE + session BE
- « Écrire d'abord les tests, puis vérifier après l'implémentation » → session TDD (modèle Writer/Reviewer)

**Situations où une session unique suffit :**
- Correction d'un bogue dans un seul fichier
- Ajout d'un CRUD identique à un modèle existant
- Compléter des tests
- Mise à jour de documentation
- Changement de configuration

## 2. Catalogue des modèles de découpage

### 2.1 Découpage séquentiel par couche (Layer-Sequential)

Le modèle le plus courant. Utilisé quand une nouvelle fonctionnalité doit être construite depuis la base.

```
Demande : « Implémentez le nouveau domaine de commandes (Order) »

Session 1: L1 + LM1 (fondations)
├── Définir OrderEntity, l'enum OrderStatus, OrderType
├── Mapping de Document MongoDB
└── Configurer l'héritage de l'Audit Entity commun
    → Passation : entités/types fixés, la suite est L2

Session 2: L2 DataLayer (données)
├── OrderCommandService (create, update, delete)
├── OrderQueryService (findById, findByStatus, search)
├── OrderRepository, OrderTemplate
└── Tests unitaires
    → Passation : L2 terminée, la suite est LM2 ou L3

Session 3: L3 Composite (métier)
├── OrderCompositionService
├── Logique d'intégration du paiement (avec PaymentCoordinator)
├── Logique de décrémentation du stock (avec InventoryCoordinator)
└── Tests d'intégration
    → Passation : L3 terminée, la suite est le Controller

Session 4: Route Controller (API)
├── OrderController (définition des endpoints)
├── Request/Response DTO
├── Configuration de Validation
└── Génération de la documentation de l'API
```

### 2.2 Découpage parallèle par domaine (Domain-Parallel)

Utilisé quand on travaille en même temps sur plusieurs domaines d'une même couche.

```
Demande : « Implémentez L2 pour les domaines User, Order et Product »

Session A: L2 — domaine User (indépendant)
Session B: L2 — domaine Order (indépendant)
Session C: L2 — domaine Product (indépendant)

Prérequis : L1 Component doit être fixé au préalable
Prérequis : il ne doit pas y avoir de références croisées L2 entre domaines (garanti par les règles de Strata)
```

### 2.3 Découpage explorer-implémenter (Explore-Implement)

Utilisé pour un travail dont la direction est incertaine.

```
Demande : « Trouvez les parties lentes et optimisez-les »

Session 1: Exploration (Explore)
├── Analyser le code et identifier les goulots d'étranglement
├── Interpréter les résultats du profilage
├── Dégager 3 stratégies d'optimisation
└── Consigner les résultats de l'exploration dans $STRATA_VAULT/projects/{name}/sessions/ (Tier V)
    → Passation : stratégie d'optimisation fixée, plan d'implémentation détaillé

Session 2-N: Implémentation (Implement)
├── Modifications du code selon la stratégie fixée
├── Tests de performance
└── Consigner les résultats
```

### 2.4 Découpage TDD (Writer/Reviewer)

Le modèle Writer/Reviewer que recommande Anthropic.

> **Relation avec l'axe de vérification :** ce modèle Writer/Reviewer est **un exemple** de mise en œuvre du **Verification Tier**
> (Self-Verified / Cross-Verified) de `core/docs/fr/methodology/verification-tier.md` par le découpage des sessions.
> La définition du Tier appartient à `core/docs/fr/methodology/verification-tier.md`, source de vérité, et n'est pas dupliquée ici.
> - Si le Reviewer relève de la même famille d'outils → **Self-Verified**
> - S'il relève d'une autre famille de modèles → **Cross-Verified** (mise en œuvre : `skills/strata.review/SKILL.md`)

```
Session 1: Écrire les tests (Writer)
├── Écrire des cas de test à partir des exigences
├── Confirmer que tous les tests échouent
└── Faire un commit des fichiers de test

Session 2: Implémenter (Writer)
├── Écrire le code qui fait passer les tests de la Session 1
├── Confirmer que tous les tests passent
└── Faire un commit du code d'implémentation

Session 3 (facultative) : Relecture (Reviewer)
├── Relire le code dans un contexte neuf
├── Vérifier que le code de la Session 2 respecte les règles de couche
└── Suggérer des refactorisations
```

### 2.5 Découpage frontend-backend (Frontend-Backend)

```
Demande : « Implémentez à la fois l'UI et l'API de la fonctionnalité de commandes »

Session BE: Backend
├── Implémenter L2-L3-Controller
├── Fixer le document de spécification de l'API ($STRATA_VAULT/projects/{name}/tasks/.../api-specs/order.yaml, Tier V)
└── Passation : endpoints de l'API + DTO fixés

Session FE: Frontend
├── Référencer la spécification de l'API (Contract) — le prérequis est que **le Contract soit fixé**, et non que BE soit terminé. On peut démarrer plus tôt avec un mock transport
├── Ordre Contract/DataState/Feature adapté à la variante de Frontend
├── Déclarer entry_point (design_first | dev_first | spec_first | change) — l'ordre n'est pas fixé et le contrôle de cohérence est la porte (core/docs/fr/architecture/frontend-design-contract.md)
└── Tests d'intégration de l'API + contrôle de cohérence Impl↔Design (design_sync)
```

La session BE et la session FE peuvent se dérouler en parallèle une fois le Contract fixé. `dev_first`, où FE passe en premier, est aussi autorisé — dans ce cas le Contract est un livrable de la session FE et la session BE le vérifie.

## 3. Format de la spécification de tâche (Task Specification)

Le document que le Builder rédige pour chaque session :

```yaml
# $STRATA_VAULT/projects/{name}/tasks/{date}/{nn}-{title}/task-{id}.yaml
task:
  id: "ORD-L2-001"
  title: "Implémenter Order L2 DataLayer"
  session_type: "implement"      # explore | implement | review | refactor
  estimated_turns: 15
  estimated_files: 8

scope:
  layer: "L2_DataLayer"
  domain: "order"
  directories:
    - "src/data/order/"
    - "test/data/order/"
  
constraints:
  layer_rule: "@core/rules/layer-rules.yaml#L2_DataLayer"
  naming_rule: "@core/rules/naming-convention.yaml#backend.L2"
  can_reference:
    - "L1_Component"
    - "LM1_Inherite"
  cannot_reference:
    - "L2_DataLayer (autres domaines)"
    - "LM2_Coordinate"
    - "L3_Composite"

inputs:
  prior_session: "ORD-L1-001"    # ID de la session précédente (null s'il n'y en a pas)
  entities:
    - "@src/components/order/OrderEntity.ts"
    - "@src/components/order/OrderStatus.ts"
  reference_implementation:
    - "@src/data/user/UserCommandService.ts"  # référence de modèle

deliverables:
  files:
    - path: "src/data/order/OrderCommandService.ts"
      description: "Service transactionnel de CUD"
    - path: "src/data/order/OrderQueryService.ts"
      description: "Service de requêtes en lecture seule"
    - path: "src/data/order/OrderRepository.ts"
      description: "Implémentation du Repository MongoDB"
    - path: "test/data/order/OrderCommandService.test.ts"
      description: "Tests unitaires de CommandService"
    - path: "test/data/order/OrderQueryService.test.ts"
      description: "Tests unitaires de QueryService"

acceptance_criteria:
  - "Tous les tests unitaires passent"
  - "Aucune violation de dépendance entre couches (la vérification du Hook passe)"
  - "Conventions de nommage respectées"
  - "Une méthode ne gère qu'une seule entité"

context_budget:
  max_reference_files: 5
  max_loaded_tokens: 20000       # limite de tokens des fichiers de référence
  compaction_strategy: "file-based"  # les décisions vont dans des fichiers, le contexte reste léger
```

## 4. Protocole de proposition de découpage du Builder

La procédure d'analyse que le Builder effectue en recevant une demande de l'utilisateur :

```
Utilisateur : « Implémente toute la fonctionnalité de gestion des commandes »

Analyse du Builder :
┌─────────────────────────────────────────┐
│ 📋 Analyse de l'étendue du travail       │
│                                          │
│ Couches affectées : L1, L2, LM2, L3, Route (5) │
│ Fichiers modifiés prévus : ~35           │
│ Fichiers de référence prévus : ~15       │
│ Tours de conversation prévus : ~60       │
│                                          │
│ ⚠ Verdict : découpage en sessions nécessaire (4 sessions recommandées) │
│                                          │
│ Proposition :                            │
│ Session 1: entités/types L1 (15 min, ~8 tours)   │
│ Session 2: L2 DataLayer (30 min, ~15 tours)      │
│ Session 3: L3 Composite (30 min, ~15 tours)      │
│ Session 4: Controller + API (20 min, ~12 tours)  │
│                                          │
│ Parallélisable : séparer les sous-domaines de la Session 2 │
│ Chaîne de dépendances : S1 → S2 → S3 → S4        │
└─────────────────────────────────────────┘
```

Le Builder **montre d'abord cette analyse à l'utilisateur et obtient son approbation** avant de générer les ordres de travail.

## 5. Signaux de fin de session

Les moments où le Builder doit mettre fin à la session en cours et faire la passation :

| Signal | Réponse |
|---|---|
| Plus de 15 tours de conversation | Faire la passation après avoir terminé l'unité de travail en cours |
| Une compaction (Compaction) survient | Sauvegarder l'état immédiatement ; si possible, faire la passation après avoir terminé l'unité en cours |
| Il faut réexpliquer « comme je vous l'ai dit auparavant… » | Signe de perte de contexte — préparer la passation immédiatement |
| Début d'un travail qui franchit une frontière de couche | Terminer la couche en cours, puis passer à la session suivante |
| Changement de direction fondé sur les résultats de l'exploration | Documenter les résultats de l'exploration ; l'implémentation se fait dans une nouvelle session |
| L'utilisateur modifie les exigences | Documenter les changements, réanalyser, puis établir un nouveau plan |
| La conversation dépasse la ligne d'alerte (environ 400 000 jetons par défaut) | Terminer l'unité en cours, faire la passation à la prochaine limite de tâche (avec la section faits et hypothèses), nouvelle session ; au plus tard avant le plafond (environ 600 000 par défaut) — 5.1 |
| Les tentatives sur une hypothèse sont bloquées deux fois | Ne pas chercher un troisième contournement ; s'arrêter et rapporter les faits mesurés et les options — 5.1 |

### 5.1 Signaux de redémarrage : la ligne d'alerte de jetons et deux échecs sur une hypothèse

Aucun des deux signaux ne veut dire couper le travail là où il en est. Tous deux veulent dire terminer l'unité en cours et scinder à la prochaine limite de tâche (carte `rec.session.split-at-task-boundary`). La compaction se déclenche quand la fenêtre est presque pleine : plus la fenêtre est grande, plus elle intervient tard, et une conversation bloquée sur une hypothèse brouille le jugement quelle que soit sa longueur. Les deux signaux couvrent ces deux cas.

**La ligne d'alerte de jetons et le plafond.** Quand la conversation dépasse environ 400 000 jetons, terminez l'unité, écrivez la passation à la prochaine limite de tâche et passez à une nouvelle session. Même si la prochaine limite est loin, passez avant environ 600 000 jetons. Les deux valeurs sont des nombres fixes de jetons, pas des proportions de la fenêtre (DEC-2026-10-31-09 ; valeurs DEC-2026-10-31-33). Ce sont des valeurs de départ destinées à clore une session bien avant la compaction quand la fenêtre par défaut est de 1M ; aucune mesure tirée de notre propre travail ne les soutient encore. Elles se changent avec `session.restart_tokens` et `session.restart_limit` dans la configuration utilisateur `~/.strata/config.yaml` ; la ligne `restart signal` de l'en-tête de démarrage montre les valeurs actuelles. Dans Claude Code, la taille actuelle se voit avec la commande `/context` ou dans la ligne d'état. Si l'agent ne peut pas la lire, la personne la lui donne.

**Deux échecs sur une hypothèse.** Quand les tentatives sont bloquées deux fois, ne cherchez pas un troisième contournement : arrêtez-vous et rapportez les faits mesurés et les options. Une hypothèse est une cause supposée : des corrections à des endroits différents sont la même hypothèse si elles reposent sur le même « la cause est X ». Un échec veut dire que le symptôme qu'on voulait vérifier (le même test en échec, la même erreur) est toujours là. Après le rapport, la personne fixe la direction, ou la passation consigne l'hypothèse écartée et une nouvelle session la réexamine.

**La section faits et hypothèses de la passation.** Une session qui se termine sur un signal de redémarrage remplit la section faits et hypothèses de la passation avec les faits confirmés (et ce qui les a confirmés), les suppositions non encore confirmées et les hypothèses écartées (et pourquoi) (DEC-2026-10-31-11). La session suivante lit d'abord cette section et ne reprend pas une hypothèse écartée. Une session qui travaille par le registre partagé écrit les trois mêmes champs dans son entrée de redémarrage (agent-operations 5.3).

### 5.2 Budget de jetons de la conversation et moment de la compaction

| Fenêtre | Compaction automatique par défaut | Avec `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=80` | Face à la ligne d'alerte de 400 000 et au plafond de 600 000 |
|---|---|---|---|
| 200 000 jetons | 200 000 (la limite de la fenêtre) | 160 000 | La compaction arrive d'abord ; dans cette fenêtre, le signal de compaction tient le rôle de la ligne d'alerte |
| 1 000 000 jetons | environ 967 000 | environ 770 000 à 800 000 | La ligne d'alerte et le plafond arrivent avant la compaction |

Le coût fixe, c'est le prompt système du harnais, les définitions d'outils, les consignes, l'en-tête de démarrage et la mémoire. Ce qu'ajoute strata-kit (consignes et en-tête) fait environ 8 à 12 Ko, soit à peu près 3 000 à 5 000 jetons (`wizard verify`) ; le reste dépend du harnais et du nombre de serveurs MCP connectés, à lire avec `/context`.

Les points de compaction par défaut viennent de la documentation de Claude Code (model-config). La fenêtre d'autocompaction (le réglage `autoCompactWindow`, la commande `/autocompact`, la variable d'environnement `CLAUDE_CODE_AUTO_COMPACT_WINDOW`, de 100 000 à 1 000 000) est le niveau de remplissage auquel la compaction se déclenche, et `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE` est un pourcentage de cette fenêtre qui ne peut qu'avancer la compaction. La variable d'environnement ne lit les suffixes comme `500k` qu'à partir de la v2.1.304. Dans une grande fenêtre, la compaction arrive bien après la ligne d'alerte ; clore les sessions est donc le rôle de la ligne d'alerte et du plafond, pas de la compaction. Modifier les réglages de compaction relève de l'utilisateur.

## 6. Fonctionnement de la commande /split-session

La procédure que le Builder effectue quand l'utilisateur exécute `/split-session` :

```
1. Analyser l'étendue de la demande en cours
2. Appliquer la matrice de découpage (voir la section 1)
3. Proposer le plan de découpage à l'utilisateur
4. En cas d'approbation :
   a. Générer task-{id}.yaml pour chaque session
   b. Mettre à jour TASK_TRACKER.md
   c. Indiquer l'ordre des dépendances
   d. Démarrer aussitôt la première session, ou enregistrer seulement le plan global
```
