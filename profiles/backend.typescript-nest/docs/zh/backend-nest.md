# 后端 TypeScript(NestJS) — 概念模型的投影

> 正本: strata-kit `profiles/backend.typescript-nest/docs/zh/backend-nest.md` (2026-10-29, DEC-2026-10-29-06)
> 概念模型: `core/docs/zh/architecture/backend-cqrs.md`

## 摘要

- NestJS 的模块、DI、provider 结构与 JVM 的形态几乎相同,是概念模型最能原样迁移的阵营。模块单位是 **Nest 模块(按领域)**,层以 **provider 后缀和文件夹** 体现。
- 基准技术栈: NestJS、ORM 用 Prisma(带类型的客户端)或 TypeORM、`class-validator`(请求校验)、测试用 Jest。CQRS 总线(`@nestjs/cqrs`)是可选项 — 概念模型中的命令/查询分离只靠拆分服务就足够,事件处理较多时再选用总线。
- 边界由 Nest DI 拦截: **没有放进模块 `exports` 的 provider,其他模块无法注入。** 文件的 import 边界由 `dependency-cruiser` 拦截。

## 布局

```
src/
  kit/                          L1 — 纯函数、错误码、类型 (不 import Nest)
  platform/                     LM1 — PrismaService(或 DataSource)、事务辅助、配置模块
  order/
    order.module.ts             模块: providers 与 exports(只公开该公开的)
    data/
      order.repository.ts       L2 下层 — 封装 Prisma 调用的 Repository
      order.template.ts         L2 下层 — 复杂查询(raw SQL、连接)
      order-command.service.ts  L2 上层 — 写、事务
      order-query.service.ts    L2 上层 — 只读,返回 DTO
    coordinate/                 LM2 — 同一关注点的 L2 组合 (仅在需要时)
    order-command.composite-service.ts   L3 — 用例
    order.listener.ts           L3 — 事件处理 (@OnEvent)
    order.task.ts               L3 — 调度 (@Cron)
    order.controller.ts         Route — DTO 校验、认证守卫、响应转换,只调用 composite
    dto/                        请求与响应 DTO (class-validator)
  payment/ …
```

| 概念层 | 在 Nest 中 | 名称 |
|---|---|---|
| L1 | `src/kit`、领域文件夹中的纯函数 | `convertUnit()` |
| LM1 | `PlatformModule` | `PrismaService`, `TransactionHost` |
| L2 下层 | `@Injectable()` 的 Repository、Template | `OrderRepository`, `OrderTemplate` |
| L2 上层 | `@Injectable()` 服务 | `OrderCommandService`, `OrderQueryService` |
| LM2 | `@Injectable()` 的 Coordinator | `PaymentCoordinator` |
| L3 | `@Injectable()` 的 CompositeService、Listener、Task | `OrderCommandCompositeService` |
| Route | `@Controller()` | `OrderController` |

## 模块边界

```ts
// order.module.ts
@Module({
  imports: [PlatformModule, PaymentModule],
  providers: [OrderRepository, OrderTemplate, OrderCommandService, OrderQueryService, OrderCommandCompositeService],
  controllers: [OrderController],
  exports: [OrderCommandCompositeService],     // 对其他模块只公开用例
})
export class OrderModule {}
```

- 不要把 L2 服务或 Repository 放进 `exports`。其他领域只能注入本模块的用例(或契约接口) — 跳过 L2 的路径在 DI 阶段就被拦截。
- 如果模块之间需要循环(`forwardRef`),这是设计信号。把其中一方改为事件,或把该关注点提升到 LM2。
- 同层引用禁令(服务 ↔ 服务)发生在同一模块内,DI 无法拦截。通过检查构造函数注入对象来保证(见下文"强制执行")。

## 命令与查询

- 写: `OrderCommandService` 在 `prisma.$transaction(...)`(或 TypeORM 的 `DataSource.transaction`)内执行。事务只放在 L2 上层。
- 读: `OrderQueryService` 把 `select`、连接的结果直接放入响应 DTO。不必经过实体模型。
- Prisma 生成的类型(实体)不得返回到 L2 之外。在 L2 边界处转换为 DTO。

## 强制执行

| 对象 | 工具 |
|---|---|
| 阻止注入其他模块的 L2 | Nest 模块 `exports` (运行时 DI 错误) |
| 文件 import 方向(禁止控制器 → repository,`kit` 不 import 任何东西,禁止领域文件夹之间互相 import) | `dependency-cruiser` 规则(与 `profiles/frontend.next-web/enforcement/` 中的 depcruise 模板方式相同) |
| 禁止注入同层服务 | 构造函数参数类型检查 — eslint 自定义规则或 dependency-cruiser 的文件级规则 |
| 格式、lint、类型 | `biome` 或 `eslint`+`prettier`, `tsc --noEmit` |

## 标记

放在 JSDoc 中(`core/docs/zh/conventions/strata-markers.md`):

```ts
/** @strata:layer L2-QueryService */
@Injectable()
export class OrderQueryService { … }
```
