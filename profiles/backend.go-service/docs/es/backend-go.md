# Backend Go — Proyección del modelo conceptual

> Canónico: strata-kit `profiles/backend.go-service/docs/es/backend-go.md` (2026-10-29, DEC-2026-10-29-06)
> Modelo conceptual: `core/docs/es/architecture/backend-cqrs.md` — el significado de las capas, la dirección de dependencia y la prohibición de referencias en el mismo nivel se definen allí. Este documento solo decide cómo se expresan en Go.

## Resumen

- La unidad de encapsulación en Go es el **paquete**. Por eso las capas no se despliegan en directorios (`internal/component/`, `internal/data/` …): el **paquete de funcionalidad (dominio) va primero** y las capas aparecen dentro de él como **archivos por rol**. Lo que la comunidad de Go evita no es CQRS, sino "un directorio por capa y una interfaz por struct".
- Stack de referencia: `net/http` estándar (enrutamiento por patrones de Go 1.22), `pgx`, `sqlc` (genera funciones de consulta tipadas a partir de SQL), `log/slog`. Un framework (gin, echo) es opcional y la proyección es la misma.
- Las interfaces se definen **en el lado que las usa** y se mantienen pequeñas ("accept interfaces, return structs"). Es el mismo principio de la arquitectura hexagonal según el cual el puerto pertenece al consumidor.
- Los límites los hacen cumplir el compilador (sin imports circulares), el directorio `internal/` y `depguard` (golangci-lint).

## Disposición

```
cmd/api/main.go                 Ensamblado de Route — arranque del servidor, conexión de dependencias (DI escrita a mano)
internal/
  platform/                     LM1 — pool de db, ayudantes de transacción, configuración (pgxpool, slog)
  kit/                          L1 — funciones puras, códigos de error, tipos de página (sin imports de framework)
  order/                        un paquete de funcionalidad = un dominio
    order.go                    L1 (dominio) — tipos de entidad, objetos de valor, cálculo puro
    store.go                    L2 nivel inferior — consulta y persistencia que envuelven los Queries generados por sqlc (rol de Repository/Template)
    command.go                  L2 nivel superior — CommandService: crear, modificar y eliminar dentro de una transacción
    query.go                    L2 nivel superior — QueryService: solo lectura, devuelve DTO directamente
    coordinate.go               LM2 — combinación de L2 de la misma preocupación (solo cuando hace falta)
    usecase.go                  L3 — CompositeService: caso de uso
    http.go                     Route — handler: validación, contexto de autenticación, conversión de respuesta, solo llama a usecase
    queries.sql / db/           entrada y salida generada de sqlc
  payment/ …
```

| Capa conceptual | En Go | Nombre |
|---|---|---|
| L1 | el paquete `internal/kit`, tipos y funciones puras de un paquete de funcionalidad | `PageRequest`, `func Convert(...)` |
| LM1 | `internal/platform` | `NewPool`, `WithTx` |
| L2 nivel inferior | `store.go` — envoltorio de los `Queries` de sqlc | `type store struct{ q *db.Queries }` (minúscula: oculto fuera del paquete) |
| L2 nivel superior | `command.go` · `query.go` | `type CommandService struct`, `type QueryService struct` |
| LM2 | `coordinate.go` o un paquete `internal/<preocupación>` | `type PaymentCoordinator struct` |
| L3 | `usecase.go` | `type CommandCompositeService struct` (el paquete es el dominio, así que `order.CommandCompositeService`) |
| Route | `http.go`, `cmd/api` | `func (h *Handler) CreateOrder(w, r)` |

- Al estar en el mismo paquete, el compilador de Go no puede impedir las referencias entre archivos. **La prohibición de referencias en el mismo nivel se hace cumplir con revisión y linters**: los tipos del nivel superior de L2 no se tienen entre sí como campos, y `store` no conoce los tipos de servicio.
- El nivel inferior (`store`) y el código generado por sqlc usan **tipos en minúscula** para que nada fuera del paquete (otros dominios, handlers) pueda usarlos directamente. Lo único que otros paquetes pueden usar son los tipos de servicio y de caso de uso.
- Evita el tartamudeo en los nombres: `order.CommandService`, no `order.OrderService`.

## Dependencias e interfaces

```go
// internal/order/usecase.go — L3
type CommandCompositeService struct {
    cmd      *CommandService
    payments PaymentAuthorizer          // otros dominios entran como una interfaz pequeña definida por quien la usa
}

type PaymentAuthorizer interface {     // puerto: pertenece al consumidor (order)
    Authorize(ctx context.Context, orderID int64, amount Money) error
}

func (s *CommandCompositeService) PlaceOrder(ctx context.Context, in PlaceOrderInput) (OrderID, error) {
    id, err := s.cmd.Create(ctx, in.toNew())
    if err != nil { return 0, err }
    return id, s.payments.Authorize(ctx, int64(id), in.Total)
}
```

- Los paquetes de dominio nunca se importan entre sí (L3 ↔ L3 está prohibido). Lo necesario entra como una interfaz del lado del consumidor, y `cmd/api/main.go` conecta la implementación.
- No crees una interfaz por struct por adelantado. Las interfaces existen solo en los límites que necesitan sustitución (dobles de prueba, implementaciones alternativas).

## Comandos y consultas

- Escritura: los métodos de `CommandService` se ejecutan dentro de `platform.WithTx(ctx, pool, func(q *db.Queries) error {...})`. Las transacciones viven solo en el nivel superior de L2.
- Lectura: `QueryService` devuelve directamente como DTO las funciones de consulta generadas por sqlc (incluidos los joins). No tiene que pasar por tipos de dominio.

## Cumplimiento

| Qué | Herramienta |
|---|---|
| Sin imports entre paquetes de dominio; `kit` no importa nada | reglas `depguard` de `golangci-lint` (por ruta de paquete) o `go-arch-lint` |
| Bloquear la exposición fuera del paquete | identificadores en minúscula, `internal/` |
| Dependencias circulares | el compilador |
| Formato y comprobaciones estáticas | `gofmt`, `go vet`, `staticcheck` |
| Pruebas | `go test ./...` (store contra un PG real mediante testcontainers) |

## Marcadores

En Go, el marcador va en el comentario godoc sin el `@` (`core/rules/naming-convention.yaml` markers.language_format.go, `core/docs/es/conventions/strata-markers.md`):

```go
// strata:layer L2-QueryService
type QueryService struct{ … }
```
