# Convention de backend Kotlin/Spring

> Fuente canónica: strata-kit `profiles/backend.kotlin-spring-cqrs/docs/es/backend-kotlin-spring.md` — migrado desde strata `docs/05-conventions/backend-kotlin-spring.md` (orden 2026.10.29-06, 2026-10-29). El YAML de reglas está en `core/rules/`.

> Fronteras de Core: `core/docs/es/architecture/backend-cqrs.md`, `core/rules/layer-rules.yaml`
> El principio de prepago y las tres fronteras (propiedad de los datos, escritura entre dominios, lectura entre dominios): `core/docs/es/architecture/prepaid-structure.md`

Este documento describe las convenciones con las que un proyecto Kotlin + Spring implementa las capas CQRS de Core.
Kotlin/Spring no es un requisito previo de Core.

## Mapeo capa ↔ paquete

En la JVM, la clave principal para identificar una capa es el **segmento de paquete**, no el directorio
(`language_patterns.kotlin.package_identifier` de `core/rules/layer-rules.yaml`).

| Capa | Segmento de paquete | Ejemplo |
|---|---|---|
| L1_Component | `..component..` | `com.example.order.component.MoneyUtil` |
| LM1_Inherite | `..inherite..` | `com.example.order.inherite.BaseEntity` |
| L2_DataLayer | `..data.{domain}..` | `com.example.order.data.payment.PaymentQueryService` |
| LM2_Coordinate | `..coordinate.{domain}..` | `com.example.order.coordinate.payment.PaymentQueryCoordinator` |
| L3_Composite | `..composite.{domain}..` | `com.example.order.composite.checkout.CheckoutCommandCompositeService` |
| Route_Controller | `..controller..` | `com.example.order.controller.CheckoutController` |

Los nombres de archivo siguen tal cual el patrón PascalCase por defecto de Core (`{Domain}QueryService.kt`, etc.). El sufijo de L3 es `CompositeService` (`{Domain}CommandCompositeService`, o `{Domain}{Action}CompositeService` cuando debe verse el comportamiento — DEC-2026-10-29-05).

Un proyecto real puede usar paquetes distintos de los segmentos anteriores. Por ejemplo, shop-api coloca L3 en `rest/<domain>/services/` y LM2 en `rest/<domain>/coordinator/`. La capa no se determina por el nombre del paquete sino por el mapeo de rutas del `layer-map.yaml` del proyecto, así que basta con que el mapeo sea correcto.

## Los dos escalones de L2 y la referencia dentro del mismo escalón

| Escalón | Elemento de Kotlin | Referencias |
|---|---|---|
| Escalón inferior | `*Repository` (interfaz de Spring Data JPA), `*Template` (DSL de jOOQ · QueryDSL) | No conoce el escalón superior. Repository ↔ Template está prohibido |
| Escalón superior | `*CommandService` (`@Transactional`), `*QueryService` (`readOnly`) | Usa el escalón inferior mediante inyección por constructor. La inyección servicio ↔ servicio está prohibida |

- Si dos servicios repiten la misma combinación, se sube a un `*Coordinator` de LM2. El criterio es si pertenecen a la misma preocupación del dominio.
- Los cálculos que no necesitan inyección, como la conversión de unidades o las fórmulas, se sacan a un `object` y quedan fuera de los escalones (por ejemplo, `UnitConversions.convert(...)`).
- Los servicios y helpers que solo se usan dentro de un módulo de entidades se ocultan con `internal` de Kotlin. `internal` solo es visible dentro del mismo source set de Gradle, de modo que el compilador impide que el L3 de un módulo de servicio los llame saltándose la estructura. Una clase public que recibe un constructor se declara con `internal constructor`.

## Fronteras de módulo (Gradle multimódulo)

- Siempre que sea posible, las fronteras de dominio se separan en módulos de Gradle. Si la dependencia entre módulos no está
  declarada en `build.gradle.kts`, el import se convierte en un error de compilación, así que reglas como «prohibida la referencia mutua entre L2»
  se imponen a nivel de compilador sin ninguna herramienta.
- Las dependencias entre módulos usan `implementation` por defecto. `api` solo se usa cuando ese tipo es
  el contrato público del módulo — la fuga de dependencias transitivas se convierte en una vía para saltarse las capas.
- La dirección de las capas dentro de un módulo la verifican de forma canónica los tests de ArchUnit (véase la estructura de aplicación más abajo).

## Convenciones de enlace con Spring

- **Para la inyección de dependencias se usa solo la inyección por constructor.** Está prohibida la inyección con `@Autowired` en campos y con `lateinit var`.
  La inyección por constructor deja la referencia de tipo en el bytecode, que es la premisa para que funcione la verificación estática de capas.
- **Prohibida la búsqueda de beans por cadena**: patrones que ocultan la referencia de tipo, como
  `applicationContext.getBean("...")` o el abuso de `@Qualifier`, se saltan la verificación de capas y están prohibidos (ArchUnit los bloquea).
- **La frontera de transacción es el CommandService de L2**: `@Transactional` se coloca en el CommandService
  (regla de Core). El QueryService es de solo lectura — `@Transactional(readOnly = true)` u omitido.
- **No se devuelve una Entity de JPA fuera de L2**: salvo la definición de entidades comunes de LM1,
  la Entity se convierte dentro de L2 a un DTO o tipo de dominio antes de pasarla hacia arriba.
  Es una infracción que un Controller referencie `..entity..` o un tipo Entity.
- **Controller delgado**: solo definición de URI, validación de parámetros (`@Valid`), inyección del contexto de autenticación
  y conversión a Response DTO. Las bifurcaciones de negocio van a L3.
- L1_Component prohíbe el propio import de Spring (regla de Core «prohibido importar frameworks externos»).

## Estructura de aplicación (3 niveles)

| Nivel | Responsable | Fuerza |
|---|---|---|
| Gradle multimódulo | Fronteras de módulo (dominio) | Impuesto por el compilador |
| ArchUnit | Dirección de capas + aislamiento de slices de dominio + bloqueo de getBean | CI blocking (canónico) |
| Hook | Retroalimentación en tiempo real al editar | Heurística (warning) |

Los tests de ArchUnit leen directamente `core/rules/layer-rules.yaml` en tiempo de ejecución, por lo que las reglas no
se duplican en el código de test. Plantilla y modo de aplicación: `profiles/backend.kotlin-spring-cqrs/enforcement/README.md`

## Marcadores

Se usa el formato KDoc (`core/docs/es/conventions/strata-markers.md`):

```kotlin
/** @strata:port L2-PaymentQueryService */
```
