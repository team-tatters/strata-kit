# Backend TypeScript (NestJS) — Projection of the Conceptual Model

> Canonical: strata-kit `profiles/backend.typescript-nest/docs/en/backend-nest.md` (2026-10-29, DEC-2026-10-29-06)
> Conceptual model: `core/docs/en/architecture/backend-cqrs.md`

## Summary

- NestJS has a module / DI / provider structure almost identical to the JVM shape, so it is the camp where the conceptual model transfers most directly. The module unit is the **Nest module (per domain)**, and the layers show up as **provider suffixes and folders**.
- Reference stack: NestJS, Prisma (typed client) or TypeORM as the ORM, `class-validator` (request validation), Jest for tests. The CQRS bus (`@nestjs/cqrs`) is optional — separating services is enough for the command/query split of the conceptual model, and you choose the bus when there is a lot of event handling.
- Boundaries are enforced by Nest DI: **a provider that is not in the module's `exports` cannot be injected by another module.** File import boundaries are enforced by `dependency-cruiser`.

## Layout

```
src/
  kit/                          L1 — pure functions, error codes, types (no Nest imports)
  platform/                     LM1 — PrismaService (or DataSource), transaction helper, config module
  order/
    order.module.ts             module: providers and exports (only what is made public)
    data/
      order.repository.ts       L2 lower tier — Repository wrapping Prisma calls
      order.template.ts         L2 lower tier — complex queries (raw SQL, joins)
      order-command.service.ts  L2 upper tier — writes, transactions
      order-query.service.ts    L2 upper tier — read-only, returns DTOs
    coordinate/                 LM2 — combines L2 for the same concern (only when needed)
    order-command.composite-service.ts   L3 — use case
    order.listener.ts           L3 — event handling (@OnEvent)
    order.task.ts               L3 — scheduling (@Cron)
    order.controller.ts         Route — DTO validation, auth guard, response conversion, calls only composite
    dto/                        request and response DTOs (class-validator)
  payment/ …
```

| Conceptual layer | In Nest | Name |
|---|---|---|
| L1 | `src/kit`, pure functions in a domain folder | `convertUnit()` |
| LM1 | `PlatformModule` | `PrismaService`, `TransactionHost` |
| L2 lower tier | `@Injectable()` Repository / Template | `OrderRepository`, `OrderTemplate` |
| L2 upper tier | `@Injectable()` services | `OrderCommandService`, `OrderQueryService` |
| LM2 | `@Injectable()` Coordinator | `PaymentCoordinator` |
| L3 | `@Injectable()` CompositeService / Listener / Task | `OrderCommandCompositeService` |
| Route | `@Controller()` | `OrderController` |

## Module Boundaries

```ts
// order.module.ts
@Module({
  imports: [PlatformModule, PaymentModule],
  providers: [OrderRepository, OrderTemplate, OrderCommandService, OrderQueryService, OrderCommandCompositeService],
  controllers: [OrderController],
  exports: [OrderCommandCompositeService],     // only the use case is exposed to other modules
})
export class OrderModule {}
```

- Do not put L2 services or Repositories in `exports`. Other domains inject only this module's use cases (or contract interfaces) — a path that skips L2 is blocked at the DI stage.
- If a cycle between modules (`forwardRef`) becomes necessary, that is a design signal. Turn one side into an event, or raise the concern to LM2.
- The ban on same-tier references (service ↔ service) cannot be blocked by DI because they are in the same module. Keep it with a check on constructor injection targets (see Enforcement below).

## Commands and Queries

- Writes: `OrderCommandService` runs inside `prisma.$transaction(...)` (or TypeORM `DataSource.transaction`). Transactions live only in the L2 upper tier.
- Reads: `OrderQueryService` puts `select` and join results directly into response DTOs. It does not have to pass through the entity model.
- Prisma's generated types (entities) are not returned outside L2. Convert them to DTOs at the L2 boundary.

## Enforcement

| What | Tool |
|---|---|
| Blocking injection of another module's L2 | Nest module `exports` (DI error at runtime) |
| File import direction (controller → repository forbidden, `kit` imports nothing, no imports between domain folders) | `dependency-cruiser` rules (same approach as the depcruise template in `profiles/frontend.next-web/enforcement/`) |
| No injection of same-tier services | check on constructor parameter types — a custom eslint rule or a file-level rule in dependency-cruiser |
| Format, lint, types | `biome` or `eslint`+`prettier`, `tsc --noEmit` |

## Markers

Put them in JSDoc (`core/docs/en/conventions/strata-markers.md`):

```ts
/** @strata:layer L2-QueryService */
@Injectable()
export class OrderQueryService { … }
```
