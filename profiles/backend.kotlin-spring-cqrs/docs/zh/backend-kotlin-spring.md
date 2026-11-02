# 后端 Kotlin/Spring Convention

> 正本：strata-kit `profiles/backend.kotlin-spring-cqrs/docs/zh/backend-kotlin-spring.md` — 从 strata `docs/05-conventions/backend-kotlin-spring.md` 迁移而来（订单 2026.10.29-06，2026-10-29）。规则 YAML 在 `core/rules/`。

> Core 边界：`core/docs/zh/architecture/backend-cqrs.md`, `core/rules/layer-rules.yaml`
> 预付原则与三条边界（数据所有权、跨领域写入、跨领域读取）：`core/docs/zh/architecture/prepaid-structure.md`

本文档说明 Kotlin + Spring 项目实现 Core CQRS 层时的惯例。
Kotlin/Spring 不是 Core 的必要前提。

## 层 ↔ 包映射

在 JVM 上，识别层的首要键是**包段**，而不是目录
（`core/rules/layer-rules.yaml` 的 `language_patterns.kotlin.package_identifier`）。

| 层 | 包段 | 示例 |
|---|---|---|
| L1_Component | `..component..` | `com.example.order.component.MoneyUtil` |
| LM1_Inherite | `..inherite..` | `com.example.order.inherite.BaseEntity` |
| L2_DataLayer | `..data.{domain}..` | `com.example.order.data.payment.PaymentQueryService` |
| LM2_Coordinate | `..coordinate.{domain}..` | `com.example.order.coordinate.payment.PaymentQueryCoordinator` |
| L3_Composite | `..composite.{domain}..` | `com.example.order.composite.checkout.CheckoutCommandCompositeService` |
| Route_Controller | `..controller..` | `com.example.order.controller.CheckoutController` |

文件名原样遵循 Core 默认的 PascalCase 模式（`{Domain}QueryService.kt` 等）。L3 的后缀是 `CompositeService`（`{Domain}CommandCompositeService`，需要体现行为时用 `{Domain}{Action}CompositeService` — DEC-2026-10-29-05）。

实际项目可以使用与上述包段不同的包。例如 shop-api 把 L3 放在 `rest/<domain>/services/`，把 LM2 放在 `rest/<domain>/coordinator/`。层不是由包名判定的，而是由项目 `layer-map.yaml` 中的路径映射判定的，所以只要映射正确即可。

## L2 的两段与同段引用

| 段 | Kotlin 元素 | 引用 |
|---|---|---|
| 下段 | `*Repository`（Spring Data JPA 接口）、`*Template`（jOOQ · QueryDSL 的 DSL） | 不了解上段。禁止 Repository ↔ Template |
| 上段 | `*CommandService`（`@Transactional`）、`*QueryService`（`readOnly`） | 通过构造器注入使用下段。禁止服务 ↔ 服务注入 |

- 如果两个服务重复同一种组合，就提升为 LM2 的 `*Coordinator`。标准是它们是否属于同一个领域关注点。
- 单位换算、公式这类不需要注入的计算，拆成 `object` 放在段外（例如 `UnitConversions.convert(...)`）。
- 只在实体模块内部使用的服务和辅助类，用 Kotlin 的 `internal` 隐藏。`internal` 只在同一个 Gradle 源集内可见，因此编译器会阻止服务模块的 L3 绕过它们去调用。接收构造器的 public 类要设为 `internal constructor`。

## 模块边界（Gradle 多模块）

- 领域边界尽可能拆分为 Gradle 模块。如果模块依赖没有在 `build.gradle.kts`
  中声明，import 就会变成编译错误，因此“禁止 L2 之间相互引用”这类规则，
  无需工具就能在编译器层面强制执行。
- 模块依赖默认使用 `implementation`。只有当该类型是模块的公开契约时，
  才使用 `api` — 传递依赖的泄漏会成为绕过层的通道。
- 模块内部的层方向，以 ArchUnit 测试作为正本来验证（见下面的执行结构）。

## Spring 绑定惯例

- **依赖注入只使用构造器注入。** 禁止字段上的 `@Autowired` 和 `lateinit var` 注入。
  构造器注入会在字节码中留下类型引用，这是静态层验证能够工作的前提。
- **禁止基于字符串的 Bean 查找**：`applicationContext.getBean("...")`、滥用 `@Qualifier` 等
  隐藏类型引用的模式会绕过层验证，因此禁止（由 ArchUnit 拦截）。
- **事务边界是 L2 的 CommandService**：`@Transactional` 放在 CommandService 上
  （Core 规则）。QueryService 只读 — 使用 `@Transactional(readOnly = true)` 或省略。
- **不要把 JPA Entity 返回到 L2 之外**：除 LM1 的公共实体定义外，
  Entity 要在 L2 内部转换为 DTO/领域类型后再传给上层。
  如果 Controller 引用了 `..entity..` 或 Entity 类型，就是违规。
- **Controller 要薄**：只做 URI 定义、参数验证（`@Valid`）、认证上下文注入，
  以及 Response DTO 转换。业务分支交给 L3。
- L1_Component 禁止任何 Spring import（Core 规则“禁止外部框架 import”）。

## 执行结构（3 层）

| 层级 | 负责 | 强度 |
|---|---|---|
| Gradle 多模块 | 模块（领域）边界 | 编译器强制 |
| ArchUnit | 层方向 + 领域切片隔离 + 拦截 getBean | CI blocking（正本） |
| Hook | 编辑时的实时反馈 | 启发式（warning） |

ArchUnit 测试在运行时直接读取 `core/rules/layer-rules.yaml`，因此不会把规则
复制到测试代码里。模板与应用方法：`profiles/backend.kotlin-spring-cqrs/enforcement/README.md`

## 标记

使用 KDoc 形式（`core/docs/zh/conventions/strata-markers.md`）：

```kotlin
/** @strata:port L2-PaymentQueryService */
```
