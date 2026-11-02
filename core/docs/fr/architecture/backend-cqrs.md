# Architecture backend — modèle conceptuel

> Source canonique : strata-kit `core/docs/fr/architecture/backend-cqrs.md`. Les règles lisibles par machine sont dans `core/rules/layer-rules.yaml` ; la raison de mettre la structure en place dès le départ est dans `core/docs/fr/architecture/prepaid-structure.md`.
> Révisé le 2026-10-29 — le modèle conceptuel indépendant du langage et les projections par langage ont été séparés (DEC-2026-10-29-06), le sens des références au sein d'une même couche a été intégré (DEC-2026-09-30-04, strata), et le suffixe de L3 a été aligné sur CompositeService (DEC-2026-10-29-05).

## Résumé

- Ce document ne définit que ce qui est **identique dans tous les langages** : le rôle de chaque couche, le sens des dépendances, l'interdiction des références au sein d'un même palier, et la séparation entre commandes et requêtes. L'organisation et les noms des répertoires, paquets et modules, ainsi que les outils d'application, sont définis par les **documents de projection par langage** (tableau en bas).
- Les couches ne se référencent que de bas en haut : L1 → LM1 → L2 → LM2 → L3 → Route. Les couches de logique (le palier service de L2, LM2, L3) ne se référencent pas **entre éléments d'un même palier**.
- L2 a deux paliers. Le palier inférieur est l'accès aux données (Repository, DSL Template) ; le palier supérieur est celui des services (Command, Query). Un service utilise le palier inférieur, et les éléments d'un même palier ne s'utilisent pas entre eux.
- Quand la réutilisation est nécessaire, on ajoute un LM2 Coordinator. Le critère de regroupement n'est pas « est-ce réutilisé » mais **« est-ce la même préoccupation de domaine »**. Un calcul pur qui n'a pas besoin d'injection est extrait vers un objet pur situé hors de tout palier.
- Une projection suit le framework et les idiomes les mieux soutenus dans cet écosystème. Les couches ne sont pas imposées par des noms de répertoire. Une couche est un **rôle**, et c'est le langage qui décide de la structure physique qui l'exprime.

## Couches

| Couche | Rôle | Peut référencer | Référence au sein de la même couche |
|---|---|---|---|
| L1 Component | Fonctions pures, constantes et types indépendants du framework. Communs, de domaine, utilitaires | Aucune | Autorisée (utilitaires communs) |
| LM1 Inherite | Socle commun injecté dans L2 — Base Entity avec champs d'audit, configuration de connexion BD et cache, interfaces Repository communes, socle transactionnel | L1 | Autorisée |
| L2 DataLayer | Accès aux données par domaine. **Palier inférieur** Repository, DSL Template ; **palier supérieur** CommandService, QueryService | L1, LM1 | Le palier inférieur ne connaît pas le supérieur. Interdite entre éléments d'un même palier |
| LM2 Coordinate | Flux métier réutilisable qui regroupe une combinaison d'éléments L2 de la même préoccupation de domaine | L2 | Interdite |
| L3 Composite | Un cas d'usage. CompositeService, Listener (événements), Task (planification) | LM2, L2 | Interdite |
| Route Controller | Reçoit le HTTP, valide, injecte le contexte d'authentification, convertit la réponse, mappe les erreurs | L3 | Autorisée (middleware commun) |

### L1 Component

Fonctions pures, constantes et types qui ne dépendent d'aucun framework. Exemples : utilitaires de dates, règles de validation, codes d'erreur, types de page, sens de tri. Ils se répartissent en communs (tous les domaines), propres à un domaine, et utilitaires généraux.

### LM1 Inherite

Le socle dont L2 hérite ou qui lui est injecté. Base Entity (champs d'audit tels que createdAt, updatedAt, createdBy), configuration de connexion BD et cache, interfaces Repository communes, socle de gestion des transactions.

### L2 DataLayer — deux paliers

| Palier | Éléments | Règle |
|---|---|---|
| Palier inférieur — accès aux données | `Repository` (implémente une interface ORM ou ODM), `Template` (requêtes complexes basées sur un DSL) | Ne référence pas le palier supérieur. Repository et Template ne se référencent pas non plus entre eux |
| Palier supérieur — services | `CommandService` (créer, modifier, supprimer ; transactions), `QueryService` (lecture seule) | Utilise le palier inférieur. Un service ne doit pas en référencer un autre |

- Une fonction ne traite qu'une seule entité. Combiner plusieurs entités relève de LM2 et de L3.
- Le côté requête peut joindre plusieurs tables et renvoyer directement un DTO. Le modèle de lecture n'a pas besoin de passer par le modèle de domaine.

### LM2 Coordinate

À placer quand une combinaison d'appels L2 relevant de la même préoccupation de domaine est utilisée par plusieurs L3. Le critère de regroupement n'est pas le nombre de réutilisations mais **le fait que la préoccupation de domaine soit la même** — on ne met pas des préoccupations différentes dans un même Coordinator simplement parce qu'« elles sont appelées ensemble ». Exemples : `PaymentCoordinator` (flux commun du traitement des paiements), `ReviewCoordinator` (flux de la ligne d'approbation du domaine de revue).

### L3 Composite

Exécute un cas d'usage.

- `{Domain}CommandCompositeService` · `{Domain}QueryCompositeService` — si l'action doit être visible, `{Domain}{Action}CompositeService` (exemple : `EmissionManageCompositeService`)
- `{Domain}Listener` — traitement d'arrière-plan piloté par les événements
- `{Domain}Task` — traitement d'arrière-plan piloté par la planification

« Créer une commande » = `OrderCommandCompositeService.createOrder()`. Un CompositeService correspond à un ensemble de cas d'usage.

### Route Controller

Fait correspondre les URI, valide les paramètres et le corps de la requête, injecte le contexte d'authentification et d'autorisation, convertit en DTO de réponse et mappe les erreurs vers des statuts HTTP. **Un Controller n'appelle pas L2 directement** — même le CRUD le plus simple passe par L3. Les listeners et les Task planifiées sont aussi des points d'entrée qui appellent le même L3 ; ajouter des adaptateurs d'entrée laisse donc le code des cas d'usage inchangé.

## Calcul pur

Un calcul qui n'a pas besoin d'injection, comme la conversion d'unités ou l'évaluation de formules, n'est placé dans aucun palier mais extrait vers un **objet pur sans injection** (Kotlin `object`, fonction de paquet en Go, fonction libre en Rust, fonction de module en TS). Ainsi, l'interdiction des références au sein d'un même palier n'oblige jamais à dupliquer le calcul ni à créer un Coordinator artificiellement.

## Sens des dépendances

```
Route_Controller
    ↓ (L3 uniquement)
L3_Composite
    ↓ (LM2 ou L2)
LM2_Coordinate
    ↓ (L2 uniquement)
L2_DataLayer   palier supérieur Command·Query → palier inférieur Repository·Template
    ↓ (L1, LM1)
LM1_Inherite
    ↓ (L1)
L1_Component
```

Les références à contresens de la flèche sont interdites. Les références au sein d'un même palier entre couches de logique sont également interdites.

## Commandes et requêtes

La séparation entre commandes et requêtes **n'est pas un découpage en microservices mais une séparation des chemins au sein du même processus**.

- Le chemin de requête n'a aucun effet de bord ; le déplacer vers un autre stockage ou en changer (réplique, cache, table externe, vue) coûte donc peu.
- La frontière transactionnelle du chemin de commande devient la ligne de coupure naturelle quand on sépare les services.
- Si les deux sont séparés dès le départ, les couches ne changent presque pas lors du passage d'un monolithe à plusieurs unités de déploiement (prepaid-structure).

## Variants

Les deux variants ont le même sens de couches et ne diffèrent que par le traitement du côté écriture de L2. Un projet en choisit un via `variant` dans `layer-map.yaml` (`cqrs` s'il est absent).

| | CQRS (par défaut) | ES-CQRS |
|---|---|---|
| Source de vérité | Lignes courantes de la BD | Journal d'événements |
| Côté écriture de L2 | CommandService | Aggregate → EventStore (ES Track) |
| Côté lecture de L2 | QueryService | QueryService (identique) |
| Composants supplémentaires | Aucun | Aggregate, EventStore, Projection |
| Convient pour | CRUD ordinaire, domaines simples | Pistes d'audit, double axe temporel, domaines pilotés par les événements |

### ES-CQRS

ES-CQRS remplace le côté écriture de L2 par l'ES Track. Une commande suit L3 → Aggregate (émet des événements) → EventStore (persiste) → Projection (met à jour le modèle de lecture) → L2 QueryService, et une requête suit L3 → L2 QueryService.

| Composant | Règle |
|---|---|
| Aggregate | Le modèle de domaine qui émet les événements. Ne référence que L1 et ne référence pas directement d'autres Aggregate (ils communiquent par Saga ou ProcessManager). Crée les événements après validation des invariants |
| EventStore | Ne référence que L1 et LM1. Ne référence directement ni Aggregate ni Projection. PG + JSONB par défaut, snapshots si nécessaire |
| Projection | Le seul pont entre l'ES Track et les couches. Synchrone (inline) ou asynchrone (outbox) |

| Règle | Contenu | Portée |
|---|---|---|
| R1 | Le point d'entrée des commandes doit passer par un CompositeService de L3 | les deux |
| R2 | Un Aggregate n'importe aucune couche autre que L1 | es-cqrs |
| R3 | L2 DataLayer est en lecture seule (pas de CommandService) | es-cqrs |
| R4 | La Projection est le seul pont de l'ES vers le modèle de lecture | es-cqrs |
| R5 | Pas de référence directe entre Aggregate (communication par Saga) | es-cqrs |
| R6 | La politique de Rebase se situe au niveau de la Projection (l'Aggregate ne connaît pas la politique) | es-cqrs |

Le niveau d'infrastructure se choisit par étapes : projection inline avec PG seul (aucun coût supplémentaire, cohérence immédiate) → PG outbox + worker dans le processus → broker de messages → EventStore par service + broker.

## Projections par langage

Le même sens des couches est transposé dans la structure la mieux soutenue de chaque langage. Trois principes sont communs : **l'unité de déploiement ou de module vient d'abord** (modules par fonctionnalité ou par domaine), les couches s'y expriment comme des **rôles (fichiers, types, suffixes)**, et les frontières sont bloquées par **le compilateur, le système de paquets et le linter de ce langage**.

| Langage | Stack représentative | Unité de module | Expression des couches | Application des frontières | Document |
|---|---|---|---|---|---|
| Kotlin·Java | Spring Boot · Spring Data JPA · jOOQ | Module Gradle (entity, service) | Paquet + suffixe (CommandService, CompositeService) | ArchUnit (lit ce YAML de règles à l'exécution), Kotlin `internal` | `profiles/backend.kotlin-spring-cqrs/docs/fr/backend-kotlin-spring.md` |
| Go | `net/http` standard (routage 1.22) · `pgx` · `sqlc` | Paquet par fonctionnalité (`internal/<domain>/`) | Fichiers par rôle dans le paquet (`command.go`, `query.go`, `store.go`, `http.go`) | Pas de cycles d'import (compilateur), `internal/`, `depguard`, `go-arch-lint` | `profiles/backend.go-service/docs/fr/backend-go.md` |
| Rust | `axum` · `tokio` · `sqlx` | Crate du workspace Cargo | Crates (domain, app, infra, api) et modules, `pub(crate)` | Sens des dépendances dans `Cargo.toml` (à la compilation), visibilité | `profiles/service.rust/docs/fr/backend-rust-layers.md` |
| TypeScript | NestJS · (Prisma ou TypeORM) | Module Nest (par domaine) | Suffixe de provider et `exports` du module | Nest DI (un provider non exporté ne peut pas être injecté), `dependency-cruiser` | `profiles/backend.typescript-nest/docs/fr/backend-nest.md` |

Les `language_patterns` des règles lisibles par machine (`core/rules/layer-rules.yaml`) portent quatre projections — kotlin, go, rust, typescript — et L2 déclare ses deux paliers via `tiers` (lower, upper) (ordre 2026.10.29-07 task-04, vérification croisée 2026-10-29). Aujourd'hui, les outils d'application ne lisent que la projection kotlin (le modèle ArchUnit) ainsi que `can_reference` et `cross_reference` au niveau des couches ; `tiers` et l'interdiction des références au sein d'un même palier dans un même domaine restent donc une déclaration — l'application sera ajoutée dans un changement distinct, après mesure.

## Extensions en attente de décision (phase d'analyse)

Les trois points suivants issus de l'analyse du 2026-10-29 ne sont pas encore des décisions. Une fois décidés, ils seront intégrés à ce document et aux documents de projection.

- **Contrat public d'un module** — les autres modules ne voient que le contrat (interfaces, types dédiés, événements). Déplacer côté fournisseur les interfaces d'appel distant qui se trouvent aujourd'hui côté consommateur, et les détacher du mode de transport.
- **Unité d'écriture = agrégat** — faire passer le côté écriture de L2 d'« une entité » à « un agrégat », et masquer les écritures au niveau de l'entité par la visibilité du module. À traiter avec les deux paliers de L2 ci-dessus.
- **Propriété de l'historique de migration par le module** — un module possède son schéma et ses tables d'historique, et les dépendances de BD entre modules ne passent que par des vues publiques.
