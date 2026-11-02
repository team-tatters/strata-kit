# Strata Markers

> Canonical source: strata-kit `core/docs/en/conventions/strata-markers.md` — migrated from strata `docs/05-conventions/strata-markers.md` (order 2026.10.29-06, 2026-10-29). Rule YAML is in `core/rules/`.

> Machine-readable definition: `core/rules/naming-convention.yaml` → `markers` section

Comment-based annotations inserted into source code that declare which layer, port or domain a file belongs to.

> **Enforcement status (as of 2026-07)**: markers are currently **for grep and human reading only**. The hook scripts
> (`check-layer-violation.py`, `validate-naming.py`) do not parse markers yet,
> and excluding `@strata:generated` files from validation is also unimplemented (layers are identified from layer-map/directories).
> Whether to implement a marker parser will be decided under the enforcement delegation
> strategy of `methodology-backlog.yaml` MB-strata-2026-003 — canonical enforcement on the JVM is handled by ArchUnit (`profiles/backend.kotlin-spring-cqrs/enforcement/`).

## Syntax

```
@strata:{tag} {value}
```

Go uses it without `@` (godoc convention):

```
strata:{tag} {value}
```

## Supported tags

| Tag | Purpose | Pattern | Example |
|---|---|---|---|
| `port` | Declares a layer port (service interface) | `{Layer}-{ServiceName}` | `@strata:port L2-InventoryQueryService` |
| `layer` | Declares the layer a file belongs to | `{Layer}` | `@strata:layer L2` |
| `domain` | Declares the business domain a file belongs to | `{domain}` | `@strata:domain inventory` |
| `generated` | Auto-generated file (excluded from layer validation) | (no value) | `@strata:generated` |
| `adapter` | Declares an external library adapter | `{library}` | `@strata:adapter sqlc` |
| `depends` | Declares an explicit dependency port | `{Layer}-{ServiceName}` | `@strata:depends L2-OrderQueryService` |
| `token-exception` | Temporary allowance for a raw token value outside Foundation. **An expiry date is required** — once it passes, the diff check fails (`core/docs/en/architecture/frontend-design-contract.md` §exception policy) | `{reason} until {YYYY-MM-DD}` | `@strata:token-exception temporary colour until the design is final until 2026-10-31` |

## Format by language

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

Go uses the `strata:` form without the `@` prefix.

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

### Swift (documentation comments)

```swift
/// Rules for translating today's state — pure functions only.
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

## Search patterns

```bash
# Find every port of a given layer
grep -r "@strata:port L2" --include="*.kt" --include="*.ts"
grep -r "strata:port L2" --include="*.go"

# Find every file of a given domain
grep -r "strata:domain inventory" --include="*.kt" --include="*.go" --include="*.ts"

# Find generated files
grep -r "strata:generated" --include="*.kt" --include="*.go" --include="*.ts"
```

## Migration from PAL markers

PAL (Port-Adapter Layered) markers were a project-level convention from before strata.
PAL layer numbers do not match the official strata numbers, so migration requires number conversion.

| PAL marker | strata marker | Number conversion |
|---|---|---|
| `@pal-port L1-SomeService` | `@strata:port L2-SomeService` | PAL L1 → strata L2 |
| `@pal-layer l1` | `@strata:layer L2` | PAL L1 → strata L2 |
| `@pal-layer l2` | `@strata:layer L3` | PAL L2 → strata L3+Route |
| `@pal-domain inventories` | `@strata:domain inventories` | (same) |
| `@pal-generated` | `@strata:generated` | (same) |
| `@pal-adapter jooq` | `@strata:adapter jooq` | (same) |
| `@pal-depends L1-Other` | `@strata:depends L2-Other` | PAL L1 → strata L2 |

### Migration procedure

1. Add the marker specification to the strata core (this document)
2. In the target project, replace PAL with strata in bulk (`sed` or the IDE)
3. Apply the layer number mapping (PAL L1 → strata L2, etc.)
4. Replace the existing `PAL-MARKERS.md` with a reference to this document
