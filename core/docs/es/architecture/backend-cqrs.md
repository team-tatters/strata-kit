# Arquitectura de backend — modelo conceptual

> Fuente canónica: strata-kit `core/docs/es/architecture/backend-cqrs.md`. Las reglas legibles por máquina están en `core/rules/layer-rules.yaml`; el motivo de tener la estructura desde el principio está en `core/docs/es/architecture/prepaid-structure.md`.
> Revisado el 2026-10-29 — se separaron el modelo conceptual independiente del lenguaje y las proyecciones por lenguaje (DEC-2026-10-29-06), se reflejó el significado de las referencias dentro de la misma capa (DEC-2026-09-30-04, strata) y se alineó el sufijo de L3 con CompositeService (DEC-2026-10-29-05).

## Resumen

- Este documento define solo lo que es **igual en todos los lenguajes**: el papel de cada capa, la dirección de dependencia, la prohibición de referencias dentro del mismo nivel y la separación entre comandos y consultas. La disposición y los nombres de directorios, paquetes y módulos, y las herramientas de aplicación, los definen los **documentos de proyección por lenguaje** (tabla al final).
- Las capas solo se referencian de abajo hacia arriba: L1 → LM1 → L2 → LM2 → L3 → Route. Las capas de lógica (el nivel de servicios de L2, LM2, L3) no se referencian **entre elementos del mismo nivel**.
- L2 tiene dos niveles. El nivel inferior es el acceso a datos (Repository, DSL Template); el nivel superior son los servicios (Command, Query). Un servicio usa el nivel inferior, y los elementos del mismo nivel no se usan entre sí.
- Cuando hace falta reutilizar, se añade un LM2 Coordinator. El criterio para agrupar no es "si se reutiliza" sino **"si es la misma preocupación de dominio"**. El cálculo puro que no necesita inyección se extrae a un objeto puro fuera de cualquier nivel.
- Una proyección sigue el framework y los modismos más respaldados en ese ámbito. Las capas no se imponen mediante nombres de directorio. Una capa es un **rol**, y el lenguaje decide con qué estructura física se expresa.

## Capas

| Capa | Rol | Puede referenciar | Referencia dentro de la misma capa |
|---|---|---|---|
| L1 Component | Funciones puras, constantes y tipos independientes del framework. Comunes, de dominio y utilidades | Ninguna | Permitida (utilidades comunes) |
| LM1 Inherite | Base común inyectada en L2 — Base Entity con campos de auditoría, configuración de conexión a BD y caché, interfaces Repository comunes, base transaccional | L1 | Permitida |
| L2 DataLayer | Acceso a datos por dominio. **Nivel inferior** Repository, DSL Template; **nivel superior** CommandService, QueryService | L1, LM1 | El nivel inferior no conoce al superior. Prohibido entre elementos del mismo nivel |
| LM2 Coordinate | Flujo de negocio reutilizable que agrupa una combinación de elementos L2 de la misma preocupación de dominio | L2 | Prohibida |
| L3 Composite | Un caso de uso. CompositeService, Listener (eventos), Task (programación) | LM2, L2 | Prohibida |
| Route Controller | Recibe HTTP, valida, inyecta el contexto de autenticación, convierte la respuesta, mapea errores | L3 | Permitida (middleware común) |

### L1 Component

Funciones puras, constantes y tipos que no dependen de ningún framework. Ejemplos: utilidades de fechas, reglas de validación, códigos de error, tipos de página, direcciones de ordenación. Se dividen en comunes (todos los dominios), específicos de un dominio y utilidades generales.

### LM1 Inherite

La base que L2 hereda o recibe por inyección. Base Entity (campos de auditoría como createdAt, updatedAt, createdBy), configuración de conexión a BD y caché, interfaces Repository comunes, base de gestión de transacciones.

### L2 DataLayer — dos niveles

| Nivel | Elementos | Regla |
|---|---|---|
| Nivel inferior — acceso a datos | `Repository` (implementa una interfaz ORM u ODM), `Template` (consultas complejas basadas en DSL) | No referencia al nivel superior. Repository y Template tampoco se referencian entre sí |
| Nivel superior — servicios | `CommandService` (crear, modificar, eliminar; transacciones), `QueryService` (solo lectura) | Usa el nivel inferior. Un servicio no debe referenciar a otro servicio |

- Una función trata una sola entidad. Combinar varias entidades es responsabilidad de LM2 y L3.
- El lado de consulta puede unir varias tablas y devolver un DTO directamente. El modelo de lectura no necesita pasar por el modelo de dominio.

### LM2 Coordinate

Se coloca cuando una combinación de llamadas L2 de la misma preocupación de dominio se usa en varios L3. El criterio para agrupar no es el número de reutilizaciones sino **si la preocupación de dominio es la misma** — no se meten preocupaciones distintas en un mismo Coordinator solo porque "se llaman juntas". Ejemplos: `PaymentCoordinator` (flujo común del procesamiento de pagos), `ReviewCoordinator` (flujo de la línea de aprobación del dominio de revisión).

### L3 Composite

Ejecuta un caso de uso.

- `{Domain}CommandCompositeService` · `{Domain}QueryCompositeService` — si hay que hacer visible la acción, `{Domain}{Action}CompositeService` (ejemplo: `EmissionManageCompositeService`)
- `{Domain}Listener` — procesamiento en segundo plano basado en eventos
- `{Domain}Task` — procesamiento en segundo plano basado en programación

"Crear pedido" = `OrderCommandCompositeService.createOrder()`. Un CompositeService corresponde a un conjunto de casos de uso.

### Route Controller

Asigna URIs, valida los parámetros y el cuerpo de la petición, inyecta el contexto de autenticación y autorización, convierte a DTO de respuesta y mapea los errores a estados HTTP. **Un Controller no llama directamente a L2** — incluso el CRUD más simple pasa por L3. Los listeners y las Task programadas también son puntos de entrada que llaman al mismo L3, así que añadir adaptadores de entrada deja intacto el código de los casos de uso.

## Cálculo puro

El cálculo que no necesita inyección, como la conversión de unidades o la evaluación de fórmulas, no se coloca en ningún nivel sino que se extrae a un **objeto puro sin inyección** (Kotlin `object`, función de paquete en Go, función libre en Rust, función de módulo en TS). Así, la prohibición de referencias dentro del mismo nivel nunca obliga a duplicar el cálculo ni a crear un Coordinator de forma forzada.

## Dirección de dependencia

```
Route_Controller
    ↓ (solo L3)
L3_Composite
    ↓ (LM2 o L2)
LM2_Coordinate
    ↓ (solo L2)
L2_DataLayer   nivel superior Command·Query → nivel inferior Repository·Template
    ↓ (L1, LM1)
LM1_Inherite
    ↓ (L1)
L1_Component
```

Las referencias en sentido contrario a la flecha están prohibidas. Las referencias dentro del mismo nivel entre capas de lógica también están prohibidas.

## Comandos y consultas

La separación entre comandos y consultas **no es una división en microservicios sino una separación de rutas dentro del mismo proceso**.

- La ruta de consulta no tiene efectos secundarios, así que moverla a otro almacén o cambiarla (réplica, caché, tabla externa, vista) es barato.
- El límite transaccional de la ruta de comandos se convierte en la línea natural de división al separar servicios.
- Si ambas se separan desde el principio, las capas casi no cambian al pasar de un monolito a varias unidades de despliegue (prepaid-structure).

## Variants

Ambas variants comparten la misma dirección de capas y solo difieren en cómo se trata el lado de escritura de L2. Un proyecto elige una mediante `variant` en `layer-map.yaml` (`cqrs` si no existe).

| | CQRS (por defecto) | ES-CQRS |
|---|---|---|
| Fuente de verdad | Filas actuales de la BD | Registro de eventos |
| Lado de escritura de L2 | CommandService | Aggregate → EventStore (ES Track) |
| Lado de lectura de L2 | QueryService | QueryService (igual) |
| Componentes adicionales | Ninguno | Aggregate, EventStore, Projection |
| Cuándo encaja | CRUD ordinario, dominios simples | Pistas de auditoría, doble eje temporal, dominios basados en eventos |

### ES-CQRS

ES-CQRS sustituye el lado de escritura de L2 por el ES Track. Un comando fluye L3 → Aggregate (emite eventos) → EventStore (persiste) → Projection (actualiza el modelo de lectura) → L2 QueryService, y una consulta fluye L3 → L2 QueryService.

| Componente | Regla |
|---|---|
| Aggregate | El modelo de dominio que emite eventos. Referencia solo a L1 y no referencia directamente a otros Aggregate (se comunican mediante Saga o ProcessManager). Crea eventos tras validar las invariantes |
| EventStore | Referencia solo a L1 y LM1. No referencia directamente a Aggregate ni a Projection. PG + JSONB por defecto, snapshots cuando haga falta |
| Projection | El único puente entre el ES Track y las capas. Síncrono (inline) o asíncrono (outbox) |

| Regla | Contenido | Ámbito |
|---|---|---|
| R1 | El punto de entrada de comandos debe pasar por un CompositeService de L3 | ambas |
| R2 | Un Aggregate no importa ninguna capa que no sea L1 | es-cqrs |
| R3 | L2 DataLayer es de solo lectura (sin CommandService) | es-cqrs |
| R4 | La Projection es el único puente de ES al modelo de lectura | es-cqrs |
| R5 | Prohibida la referencia directa entre Aggregate (se comunican mediante Saga) | es-cqrs |
| R6 | La política de Rebase está en el nivel de la Projection (el Aggregate no conoce la política) | es-cqrs |

El nivel de infraestructura se elige por etapas: projection inline usando solo PG (sin coste adicional, consistencia inmediata) → PG outbox + worker en el proceso → bróker de mensajes → EventStore por servicio + bróker.

## Proyecciones por lenguaje

El mismo significado de las capas se traslada a la estructura mejor respaldada de cada lenguaje. Hay tres principios comunes: la **unidad de despliegue o de módulo va primero** (módulos por funcionalidad o dominio), las capas se expresan dentro de ella como **roles (archivos, tipos, sufijos)**, y los límites los bloquean **el compilador, el sistema de paquetes y el linter de ese lenguaje**.

| Lenguaje | Stack representativo | Unidad de módulo | Expresión de las capas | Aplicación de los límites | Documento |
|---|---|---|---|---|---|
| Kotlin·Java | Spring Boot · Spring Data JPA · jOOQ | Módulo Gradle (entity, service) | Paquete + sufijo (CommandService, CompositeService) | ArchUnit (lee este YAML de reglas en tiempo de ejecución), Kotlin `internal` | `profiles/backend.kotlin-spring-cqrs/docs/es/backend-kotlin-spring.md` |
| Go | `net/http` estándar (enrutamiento 1.22) · `pgx` · `sqlc` | Paquete por funcionalidad (`internal/<domain>/`) | Archivos por rol dentro del paquete (`command.go`, `query.go`, `store.go`, `http.go`) | Sin ciclos de import (compilador), `internal/`, `depguard`, `go-arch-lint` | `profiles/backend.go-service/docs/es/backend-go.md` |
| Rust | `axum` · `tokio` · `sqlx` | Crate del workspace de Cargo | Crates (domain, app, infra, api) y módulos, `pub(crate)` | Dirección de dependencia en `Cargo.toml` (en compilación), visibilidad | `profiles/service.rust/docs/es/backend-rust-layers.md` |
| TypeScript | NestJS · (Prisma o TypeORM) | Módulo Nest (por dominio) | Sufijo de provider y `exports` del módulo | Nest DI (un provider no exportado no se puede inyectar), `dependency-cruiser` | `profiles/backend.typescript-nest/docs/es/backend-nest.md` |

Los `language_patterns` de las reglas legibles por máquina (`core/rules/layer-rules.yaml`) incluyen cuatro proyecciones — kotlin, go, rust, typescript — y L2 declara sus dos niveles mediante `tiers` (lower, upper) (orden 2026.10.29-07 task-04, verificación cruzada 2026-10-29). Lo único que leen hoy las herramientas de aplicación es la proyección kotlin (la plantilla de ArchUnit) y los `can_reference` y `cross_reference` a nivel de capa, por lo que `tiers` y la prohibición de referencias dentro del mismo nivel en un mismo dominio siguen siendo una declaración — la aplicación se añadirá en un cambio aparte, tras la medición.

## Extensiones pendientes de decisión (fase de análisis)

Los tres puntos siguientes del análisis del 2026-10-29 todavía no son decisiones. Cuando se decidan, se reflejarán en este documento y en los documentos de proyección.

- **Contrato público de un módulo** — los demás módulos solo ven el contrato (interfaces, tipos dedicados, eventos). Mover al lado del proveedor las interfaces de llamada remota que hoy están en el lado del consumidor y desacoplarlas del transporte.
- **Unidad de escritura como agregado** — cambiar el lado de escritura de L2 de "una entidad" a "un agregado", y ocultar las escrituras a nivel de entidad mediante la visibilidad del módulo. Se trata junto con los dos niveles de L2 anteriores.
- **Propiedad del historial de migraciones por el módulo** — un módulo posee su esquema y sus tablas de historial, y las dependencias de BD entre módulos pasan solo por vistas públicas.
