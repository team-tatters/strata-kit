# 后端架构 — 概念模型

> 正本：strata-kit `core/docs/zh/architecture/backend-cqrs.md`。机器可读规则见 `core/rules/layer-rules.yaml`，从一开始就备齐结构的原因见 `core/docs/zh/architecture/prepaid-structure.md`。
> 2026-10-29 修订 — 将与语言无关的概念模型和按语言的投影分开（DEC-2026-10-29-06），反映了同层引用的含义（DEC-2026-09-30-04，strata），并把 L3 后缀统一为 CompositeService（DEC-2026-10-29-05）。

## 摘要

- 本文只规定**在任何语言中都相同**的内容：层的职责、依赖方向、同一级禁止互相引用、命令与查询的分离。目录、包、模块的布局与命名，以及执行工具，由**按语言的投影文档**规定（见最后的表）。
- 层只能自下而上引用：L1 → LM1 → L2 → LM2 → L3 → Route。逻辑层（L2 的服务级、LM2、L3）**不得在同一级的元素之间**互相引用。
- L2 分为两级。下级是数据访问（Repository、DSL Template），上级是服务（Command、Query）。服务使用下级，同一级之间不互相使用。
- 需要复用时，设置 LM2 Coordinator。归并的标准不是“是否被复用”，而是**“是否属于同一领域关注点”**。不需要注入的纯计算，抽出到级之外的纯对象中。
- 投影遵循该阵营中最受支持的框架和惯用法。不通过目录名称来强制层。层是**职责**，以何种物理结构体现，由语言决定。

## 层

| 层 | 职责 | 可引用 | 同一层内的引用 |
|---|---|---|---|
| L1 Component | 与框架无关的纯函数、常量、类型。通用、领域、工具 | 无 | 允许（通用工具） |
| LM1 Inherite | 注入到 L2 的通用基础 — 带审计字段的 Base Entity、DB 与缓存连接配置、通用 Repository 接口、事务基础 | L1 | 允许 |
| L2 DataLayer | 按领域的数据访问。**下级** Repository、DSL Template，**上级** CommandService、QueryService | L1、LM1 | 下级不知道上级。同一级之间禁止 |
| LM2 Coordinate | 将同一领域关注点的 L2 组合归并起来的可复用业务流程 | L2 | 禁止 |
| L3 Composite | 一个用例。CompositeService、Listener（事件）、Task（定时） | LM2、L2 | 禁止 |
| Route Controller | 接收 HTTP、校验、注入认证上下文、转换响应、映射错误 | L3 | 允许（通用中间件） |

### L1 Component

不依赖框架的纯函数、常量和类型。例如：日期工具、校验规则、错误码、分页类型、排序方向。分为通用（所有领域）、领域专用和通用工具。

### LM1 Inherite

L2 继承或被注入的基础。Base Entity（createdAt、updatedAt、createdBy 等审计字段）、DB 与缓存连接配置、通用 Repository 接口、事务管理基础。

### L2 DataLayer — 两级

| 级 | 元素 | 规则 |
|---|---|---|
| 下级 — 数据访问 | `Repository`（实现 ORM 或 ODM 接口）、`Template`（基于 DSL 的复杂查询） | 不引用上级。Repository 与 Template 之间也不互相引用 |
| 上级 — 服务 | `CommandService`（创建、修改、删除，事务）、`QueryService`（只读） | 使用下级。服务之间禁止互相引用 |

- 一个函数只处理一个实体。组合多个实体的工作是 LM2 和 L3 的职责。
- 查询一侧可以连接多张表并直接返回 DTO。读取模型不必经过领域模型。

### LM2 Coordinate

当属于同一领域关注点的 L2 调用组合被多个 L3 使用时设置。归并的标准不是复用次数，而是**领域关注点是否相同** — 不要因为“经常一起被调用”就把不同的关注点放进同一个 Coordinator。例如：`PaymentCoordinator`（支付处理的通用流程）、`ReviewCoordinator`（评审领域的审批链流程）。

### L3 Composite

执行一个用例。

- `{Domain}CommandCompositeService` · `{Domain}QueryCompositeService` — 若需要体现行为，则用 `{Domain}{Action}CompositeService`（例：`EmissionManageCompositeService`）
- `{Domain}Listener` — 基于事件的后台处理
- `{Domain}Task` — 基于定时的后台处理

“创建订单” = `OrderCommandCompositeService.createOrder()`。一个 CompositeService 对应一组用例。

### Route Controller

负责 URI 映射、请求参数与请求体的校验、认证与授权上下文的注入、响应 DTO 的转换，以及将错误映射为 HTTP 状态。**Controller 不得直接调用 L2** — 再简单的 CRUD 也要经过 L3。监听器和定时 Task 也是调用同一个 L3 的入口，所以增加入口适配器时，用例代码保持不变。

## 纯计算

单位换算、公式求值这类不需要注入的计算，不放入任何一级，而是抽出到**不带注入的纯对象**中（Kotlin `object`、Go 包函数、Rust 自由函数、TS 模块函数）。这样，由于同一级禁止引用，就不必复制计算，也不必勉强创建 Coordinator。

## 依赖方向

```
Route_Controller
    ↓ (仅 L3)
L3_Composite
    ↓ (LM2 或 L2)
LM2_Coordinate
    ↓ (仅 L2)
L2_DataLayer   上级 Command·Query → 下级 Repository·Template
    ↓ (L1, LM1)
LM1_Inherite
    ↓ (L1)
L1_Component
```

与箭头相反方向的引用是禁止的。逻辑层在同一级的引用也是禁止的。

## 命令与查询

命令与查询的分离**不是微服务拆分，而是同一进程内的路径分离**。

- 查询路径没有副作用，因此迁移到其他存储（副本、缓存、外部表、视图）或更换存储的成本很低。
- 命令路径的事务边界，是拆分服务时自然的分界线。
- 如果一开始就把两者分开，从单体走向多个部署单元时，层几乎不会改变（prepaid-structure）。

## Variants

两种 variant 的层方向相同，只是 L2 写入一侧的处理不同。项目通过 `layer-map.yaml` 的 `variant` 选择（没有则为 `cqrs`）。

| | CQRS（默认） | ES-CQRS |
|---|---|---|
| 事实来源 | DB 中的当前行 | 事件日志 |
| L2 写入一侧 | CommandService | Aggregate → EventStore (ES Track) |
| L2 读取一侧 | QueryService | QueryService（相同） |
| 额外组成部分 | 无 | Aggregate、EventStore、Projection |
| 适用场景 | 一般 CRUD、简单领域 | 审计追踪、双时间轴、事件驱动的领域 |

### ES-CQRS

ES-CQRS 用 ES Track 取代 L2 的写入一侧。命令按 L3 → Aggregate（发布事件）→ EventStore（存储）→ Projection（更新读取模型）→ L2 QueryService 的顺序流动，查询按 L3 → L2 QueryService 流动。

| 组成部分 | 规则 |
|---|---|
| Aggregate | 发布事件的领域模型。只引用 L1，不直接引用其他 Aggregate（通过 Saga、ProcessManager 通信）。校验不变量后生成事件 |
| EventStore | 只引用 L1、LM1。不直接引用 Aggregate、Projection。默认 PG + JSONB，必要时使用快照 |
| Projection | 连接 ES Track 与各层的唯一桥梁。同步（inline）或异步（outbox） |

| 规则 | 内容 | 范围 |
|---|---|---|
| R1 | 命令入口必须经过 L3 CompositeService | 两者 |
| R2 | Aggregate 不得 import L1 以外的层 | es-cqrs |
| R3 | L2 DataLayer 为只读（没有 CommandService） | es-cqrs |
| R4 | Projection 是 ES → 读取模型的唯一桥梁 | es-cqrs |
| R5 | 禁止 Aggregate 之间直接引用（通过 Saga 通信） | es-cqrs |
| R6 | Rebase 策略属于 Projection 层面（Aggregate 不知道该策略） | es-cqrs |

基础设施的层级分阶段选择：只用 PG 的 inline projection（无额外成本，立即一致）→ PG outbox + 进程内 worker → 消息代理 → 按服务划分的 EventStore + 代理。

## 按语言的投影

把相同的层含义，移植到各语言所支持的结构中。共同原则有三条 — **部署与模块单位优先**（按功能或领域划分模块），层在其内部以**职责（文件、类型、后缀）**体现，边界由**该语言的编译器、包系统和 linter** 来拦截。

| 语言 | 代表技术栈 | 模块单位 | 层的表达 | 边界执行 | 文档 |
|---|---|---|---|---|---|
| Kotlin·Java | Spring Boot · Spring Data JPA · jOOQ | Gradle 模块（entity、service） | 包 + 后缀（CommandService、CompositeService） | ArchUnit（运行时读取此规则 YAML）、Kotlin `internal` | `profiles/backend.kotlin-spring-cqrs/docs/zh/backend-kotlin-spring.md` |
| Go | 标准 `net/http`（1.22 路由）· `pgx` · `sqlc` | 功能包（`internal/<domain>/`） | 包内的职责文件（`command.go`、`query.go`、`store.go`、`http.go`） | 禁止循环 import（编译器）、`internal/`、`depguard`、`go-arch-lint` | `profiles/backend.go-service/docs/zh/backend-go.md` |
| Rust | `axum` · `tokio` · `sqlx` | Cargo 工作区 crate | crate（domain、app、infra、api）与模块、`pub(crate)` | `Cargo.toml` 依赖方向（编译期）、可见性 | `profiles/service.rust/docs/zh/backend-rust-layers.md` |
| TypeScript | NestJS · （Prisma 或 TypeORM） | Nest 模块（按领域） | provider 后缀与模块 `exports` | Nest DI（未导出的 provider 无法注入）、`dependency-cruiser` | `profiles/backend.typescript-nest/docs/zh/backend-nest.md` |

机器可读规则（`core/rules/layer-rules.yaml`）的 `language_patterns` 包含 kotlin、go、rust、typescript 四种投影，L2 通过 `tiers`（lower、upper）声明两级（订单 2026.10.29-07 task-04，交叉验证 2026-10-29）。目前执行工具读取的只有 kotlin 投影（ArchUnit 模板）以及层级别的 `can_reference` 和 `cross_reference`，所以 `tiers` 以及同一领域内同一级禁止引用，仍然只是声明 — 执行将在实测之后，以单独的变更提交。

## 决定之前的扩展（分析阶段）

2026-10-29 的分析中提出的以下三项尚未成为决定。一旦决定，将反映到本文档和投影文档中。

- **模块的公开契约** — 其他模块只看契约（接口、专用类型、事件）。把现在位于消费方的远程调用接口移到提供方，并与传输方式脱钩。
- **以聚合作为写入单位** — 将 L2 写入一侧从“一个实体”改为“一个聚合”，实体级别的写入通过模块可见性隐藏。与上面的 L2 两级一并处理。
- **迁移历史由模块拥有** — 模块拥有其 schema 和历史表，模块之间的 DB 依赖只能通过公开视图。
