# Marcadores de Strata

> Fuente canónica: strata-kit `core/docs/es/conventions/strata-markers.md` — migrado desde strata `docs/05-conventions/strata-markers.md` (orden 2026.10.29-06, 2026-10-29). El YAML de reglas está en `core/rules/`.

> Definición legible por máquina: `core/rules/naming-convention.yaml` → sección `markers`

Son anotaciones basadas en comentarios que se insertan en el código fuente y declaran a qué capa, puerto o dominio pertenece un archivo.

> **Estado de aplicación (a 2026-07)**: los marcadores son actualmente **solo para grep y lectura humana**. Los scripts de hook
> (`check-layer-violation.py`, `validate-naming.py`) todavía no analizan los marcadores,
> y la exclusión de la validación de `@strata:generated` tampoco está implementada (la capa se identifica a partir de layer-map/directorios).
> Si se implementa o no un parser de marcadores se decidirá según la estrategia de delegación
> de aplicación de `methodology-backlog.yaml` MB-strata-2026-003 — la aplicación canónica en la JVM la realiza ArchUnit (`profiles/backend.kotlin-spring-cqrs/enforcement/`).

## Sintaxis

```
@strata:{tag} {value}
```

Go lo usa sin `@` (convención de godoc):

```
strata:{tag} {value}
```

## Etiquetas admitidas

| Etiqueta | Uso | Patrón | Ejemplo |
|---|---|---|---|
| `port` | Declara un puerto de capa (interfaz de servicio) | `{Layer}-{ServiceName}` | `@strata:port L2-InventoryQueryService` |
| `layer` | Declara la capa a la que pertenece el archivo | `{Layer}` | `@strata:layer L2` |
| `domain` | Declara el dominio de negocio al que pertenece el archivo | `{domain}` | `@strata:domain inventory` |
| `generated` | Archivo generado automáticamente (excluido de la validación de capas) | (sin valor) | `@strata:generated` |
| `adapter` | Declara un adaptador de biblioteca externa | `{library}` | `@strata:adapter sqlc` |
| `depends` | Declara explícitamente un puerto del que se depende | `{Layer}-{ServiceName}` | `@strata:depends L2-OrderQueryService` |
| `token-exception` | Permiso temporal para un valor de token en bruto fuera de Foundation. **La fecha de caducidad es obligatoria** — cuando pasa, falla la comprobación de diff (`core/docs/es/architecture/frontend-design-contract.md` §política de excepciones) | `{reason} until {YYYY-MM-DD}` | `@strata:token-exception color provisional hasta cerrar el diseño until 2026-10-31` |

## Formato por lenguaje

### Kotlin (KDoc)

```kotlin
/**
 * @strata:port L2-InventoryCommandService
 * @strata:layer L2
 * @strata:domain inventory
 */
class InventoryCommandService(
    private val repository: InventoryRepository
) { ... }
```

### Go (godoc)

Go usa la forma `strata:` sin el prefijo `@`.

```go
// InventoryQueryRepository provides read-only access to inventory views.
//
// strata:port L2-InventoryQueryRepository
// strata:layer L2
// strata:domain inventory
type InventoryQueryRepository interface {
    FindByID(ctx context.Context, id uuid.UUID) (*InventoryView, error)
}
```

### Swift (comentarios de documentación)

```swift
/// Reglas de traducción del estado de hoy — solo funciones puras.
/// @strata:layer Contract
/// @strata:domain today
enum StateEngine { … }
```

### TypeScript (JSDoc)

```typescript
/**
 * @strata:port L2-InventoryQueryService
 * @strata:layer L2
 * @strata:domain inventory
 */
export class InventoryQueryService {
    constructor(private readonly repo: InventoryRepository) {}
}
```

## Patrones de búsqueda

```bash
# Buscar todos los puertos de una capa
grep -r "@strata:port L2" --include="*.kt" --include="*.ts"
grep -r "strata:port L2" --include="*.go"

# Buscar todos los archivos de un dominio
grep -r "strata:domain inventory" --include="*.kt" --include="*.go" --include="*.ts"

# Buscar archivos generados
grep -r "strata:generated" --include="*.kt" --include="*.go" --include="*.ts"
```

## Migración desde los marcadores PAL

Los marcadores PAL (Port-Adapter Layered) eran una convención a nivel de proyecto anterior a strata.
Los números de capa de PAL no coinciden con los números oficiales de strata, por lo que la migración requiere una conversión de números.

| Marcador PAL | Marcador strata | Conversión de número |
|---|---|---|
| `@pal-port L1-SomeService` | `@strata:port L2-SomeService` | PAL L1 → strata L2 |
| `@pal-layer l1` | `@strata:layer L2` | PAL L1 → strata L2 |
| `@pal-layer l2` | `@strata:layer L3` | PAL L2 → strata L3+Route |
| `@pal-domain inventories` | `@strata:domain inventories` | (igual) |
| `@pal-generated` | `@strata:generated` | (igual) |
| `@pal-adapter jooq` | `@strata:adapter jooq` | (igual) |
| `@pal-depends L1-Other` | `@strata:depends L2-Other` | PAL L1 → strata L2 |

### Procedimiento de migración

1. Añadir la especificación de marcadores al núcleo de strata (este documento)
2. En el proyecto de destino, sustituir PAL por strata de forma masiva (`sed` o el IDE)
3. Aplicar el mapeo de números de capa (PAL L1 → strata L2, etc.)
4. Reemplazar el `PAL-MARKERS.md` existente por una referencia a este documento
