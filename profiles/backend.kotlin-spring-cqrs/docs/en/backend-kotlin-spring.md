# Backend Kotlin/Spring Convention

> Canonical source: strata-kit `profiles/backend.kotlin-spring-cqrs/docs/en/backend-kotlin-spring.md` — migrated from strata `docs/05-conventions/backend-kotlin-spring.md` (order 2026.10.29-06, 2026-10-29). Rule YAML is in `core/rules/`.

> Core boundaries: `core/docs/en/architecture/backend-cqrs.md`, `core/rules/layer-rules.yaml`
> The prepaid principle and the three boundaries (data ownership, cross-domain writes, cross-domain reads): `core/docs/en/architecture/prepaid-structure.md`

This document describes the conventions for a Kotlin + Spring project to implement the Core CQRS layers.
Kotlin/Spring is not a required premise of Core.

## Layer ↔ package mapping

On the JVM, the primary key for identifying a layer is the **package segment**, not the directory
(`language_patterns.kotlin.package_identifier` in `core/rules/layer-rules.yaml`).

| Layer | Package segment | Example |
|---|---|---|
| L1_Component | `..component..` | `com.example.order.component.MoneyUtil` |
| LM1_Inherite | `..inherite..` | `com.example.order.inherite.BaseEntity` |
| L2_DataLayer | `..data.{domain}..` | `com.example.order.data.payment.PaymentQueryService` |
| LM2_Coordinate | `..coordinate.{domain}..` | `com.example.order.coordinate.payment.PaymentQueryCoordinator` |
| L3_Composite | `..composite.{domain}..` | `com.example.order.composite.checkout.CheckoutCommandCompositeService` |
| Route_Controller | `..controller..` | `com.example.order.controller.CheckoutController` |

File names follow the Core default PascalCase pattern (`{Domain}QueryService.kt` and so on) as is. The L3 suffix is `CompositeService` (`{Domain}CommandCompositeService`, or `{Domain}{Action}CompositeService` when the behavior must show — DEC-2026-10-29-05).

A real project may use packages different from the segments above. For example, shop-api puts L3 in `rest/<domain>/services/` and LM2 in `rest/<domain>/coordinator/`. A layer is determined not by the package name but by the path mapping in the project's `layer-map.yaml`, so it is enough for the mapping to be correct.

## Two tiers of L2 and same-tier references

| Tier | Kotlin element | References |
|---|---|---|
| Lower tier | `*Repository` (Spring Data JPA interface), `*Template` (jOOQ · QueryDSL DSL) | Does not know the upper tier. Repository ↔ Template is forbidden |
| Upper tier | `*CommandService` (`@Transactional`), `*QueryService` (`readOnly`) | Uses the lower tier through constructor injection. Service ↔ service injection is forbidden |

- If two services repeat the same combination, lift it into an LM2 `*Coordinator`. The criterion is whether it is the same domain concern.
- Calculations that need no injection, such as unit conversion or formulas, are pulled out into an `object` and kept outside the tiers (for example `UnitConversions.convert(...)`).
- Services and helpers used only inside an entity module are hidden with Kotlin `internal`. `internal` is visible only within the same Gradle source set, so the compiler prevents the L3 of a service module from bypassing and calling them. A public class that takes a constructor is given an `internal constructor`.

## Module boundaries (Gradle multi-module)

- Where possible, separate domain boundaries into Gradle modules. If a module dependency is not
  declared in `build.gradle.kts`, an import becomes a compile error, so rules like "no cross-reference between L2s"
  are enforced at the compiler level without any tool.
- Module dependencies default to `implementation`. Use `api` only when that type is the
  module's public contract — leaking transitive dependencies becomes a path for bypassing layers.
- The layer direction inside a module is verified canonically by ArchUnit tests (see the enforcement structure below).

## Spring binding conventions

- **Use constructor injection only for dependency injection.** Field `@Autowired` and `lateinit var` injection are forbidden.
  Constructor injection leaves the type reference in the bytecode, which is the premise for static layer verification to work.
- **No string-based bean lookup**: patterns that hide type references, such as
  `applicationContext.getBean("...")` or abuse of `@Qualifier`, bypass layer verification and are forbidden (ArchUnit blocks them).
- **The transaction boundary is the L2 CommandService**: put `@Transactional` on the CommandService
  (Core rule). The QueryService is read-only — `@Transactional(readOnly = true)` or omitted.
- **Do not return a JPA Entity outside L2**: except for the common entity definitions in LM1,
  an Entity is converted to a DTO/domain type inside L2 before being passed upward.
  It is a violation if a Controller references `..entity..` or an Entity type.
- **Keep the Controller thin**: only URI definition, parameter validation (`@Valid`), authentication context injection,
  and Response DTO conversion. Business branching goes to L3.
- L1_Component forbids Spring imports altogether (Core rule "no external framework imports").

## Enforcement structure (3 tiers)

| Tier | Owner | Strength |
|---|---|---|
| Gradle multi-module | Module (domain) boundaries | Compiler-enforced |
| ArchUnit | Layer direction + domain slice isolation + getBean blocking | CI blocking (canonical) |
| Hook | Real-time feedback while editing | Heuristic (warning) |

ArchUnit tests read `core/rules/layer-rules.yaml` directly at runtime, so rules are not
duplicated in test code. Template and how to apply it: `profiles/backend.kotlin-spring-cqrs/enforcement/README.md`

## Markers

Use the KDoc form (`core/docs/en/conventions/strata-markers.md`):

```kotlin
/** @strata:port L2-PaymentQueryService */
```
