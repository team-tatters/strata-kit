# Backend TypeScript (NestJS) — Projection du modèle conceptuel

> Référence : strata-kit `profiles/backend.typescript-nest/docs/fr/backend-nest.md` (2026-10-29, DEC-2026-10-29-06)
> Modèle conceptuel : `core/docs/fr/architecture/backend-cqrs.md`

## Résumé

- NestJS a une structure de modules, de DI et de providers presque identique à la forme JVM ; c'est le camp où le modèle conceptuel se transpose le plus directement. L'unité de module est le **module Nest (par domaine)**, et les couches apparaissent sous forme de **suffixes de provider et de dossiers**.
- Pile de référence : NestJS, Prisma (client typé) ou TypeORM comme ORM, `class-validator` (validation des requêtes), Jest pour les tests. Le bus CQRS (`@nestjs/cqrs`) est facultatif — pour la séparation commande/requête du modèle conceptuel, séparer les services suffit, et on choisit le bus quand il y a beaucoup de traitement d'événements.
- Les frontières sont imposées par la DI de Nest : **un provider absent des `exports` du module ne peut pas être injecté par un autre module.** Les frontières d'import de fichiers sont imposées par `dependency-cruiser`.

## Disposition

```
src/
  kit/                          L1 — fonctions pures, codes d'erreur, types (aucun import de Nest)
  platform/                     LM1 — PrismaService (ou DataSource), aide de transaction, module de configuration
  order/
    order.module.ts             module : providers et exports (seulement ce qui est rendu public)
    data/
      order.repository.ts       L2 niveau inférieur — Repository enveloppant les appels Prisma
      order.template.ts         L2 niveau inférieur — requêtes complexes (SQL brut, jointures)
      order-command.service.ts  L2 niveau supérieur — écritures, transactions
      order-query.service.ts    L2 niveau supérieur — lecture seule, renvoie des DTO
    coordinate/                 LM2 — combinaison de L2 pour un même sujet (seulement si nécessaire)
    order-command.composite-service.ts   L3 — cas d'usage
    order.listener.ts           L3 — traitement d'événements (@OnEvent)
    order.task.ts               L3 — planification (@Cron)
    order.controller.ts         Route — validation des DTO, garde d'authentification, conversion de la réponse, n'appelle que composite
    dto/                        DTO de requête et de réponse (class-validator)
  payment/ …
```

| Couche conceptuelle | Dans Nest | Nom |
|---|---|---|
| L1 | `src/kit`, fonctions pures dans le dossier du domaine | `convertUnit()` |
| LM1 | `PlatformModule` | `PrismaService`, `TransactionHost` |
| L2 niveau inférieur | Repository / Template avec `@Injectable()` | `OrderRepository`, `OrderTemplate` |
| L2 niveau supérieur | services avec `@Injectable()` | `OrderCommandService`, `OrderQueryService` |
| LM2 | Coordinator avec `@Injectable()` | `PaymentCoordinator` |
| L3 | CompositeService / Listener / Task avec `@Injectable()` | `OrderCommandCompositeService` |
| Route | `@Controller()` | `OrderController` |

## Frontières de module

```ts
// order.module.ts
@Module({
  imports: [PlatformModule, PaymentModule],
  providers: [OrderRepository, OrderTemplate, OrderCommandService, OrderQueryService, OrderCommandCompositeService],
  controllers: [OrderController],
  exports: [OrderCommandCompositeService],     // seul le cas d'usage est exposé aux autres modules
})
export class OrderModule {}
```

- Ne mettez pas de services L2 ni de Repositories dans `exports`. Les autres domaines n'injectent que les cas d'usage de ce module (ou des interfaces de contrat) — un chemin qui saute L2 est bloqué dès l'étape de DI.
- Si un cycle entre modules (`forwardRef`) devient nécessaire, c'est un signal de conception. Transformez un des côtés en événement, ou remontez le sujet en LM2.
- L'interdiction de références au sein d'un même niveau (service ↔ service) ne peut pas être bloquée par la DI, car ils sont dans le même module. On la tient par une vérification des cibles d'injection par constructeur (voir Application des règles ci-dessous).

## Commandes et requêtes

- Écriture : `OrderCommandService` s'exécute dans `prisma.$transaction(...)` (ou `DataSource.transaction` de TypeORM). Les transactions ne vivent que dans le niveau supérieur de L2.
- Lecture : `OrderQueryService` place directement les résultats de `select` et de jointures dans les DTO de réponse. Il n'a pas à passer par le modèle d'entités.
- Les types générés par Prisma (entités) ne sont pas renvoyés hors de L2. On les convertit en DTO à la frontière de L2.

## Application des règles

| Quoi | Outil |
|---|---|
| Bloquer l'injection du L2 d'un autre module | `exports` du module Nest (erreur de DI à l'exécution) |
| Sens des imports de fichiers (contrôleur → repository interdit, `kit` n'importe rien, pas d'import entre dossiers de domaine) | règles `dependency-cruiser` (même approche que le modèle depcruise de `profiles/frontend.next-web/enforcement/`) |
| Pas d'injection de services du même niveau | vérification des types des paramètres du constructeur — une règle eslint personnalisée ou une règle par fichier de dependency-cruiser |
| Format, lint, types | `biome` ou `eslint`+`prettier`, `tsc --noEmit` |

## Marqueurs

On les place dans la JSDoc (`core/docs/fr/conventions/strata-markers.md`) :

```ts
/** @strata:layer L2-QueryService */
@Injectable()
export class OrderQueryService { … }
```
