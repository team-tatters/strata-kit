# Backend TypeScript (NestJS) — Proyección del modelo conceptual

> Canónico: strata-kit `profiles/backend.typescript-nest/docs/es/backend-nest.md` (2026-10-29, DEC-2026-10-29-06)
> Modelo conceptual: `core/docs/es/architecture/backend-cqrs.md`

## Resumen

- NestJS tiene una estructura de módulos, DI y providers casi idéntica a la forma de la JVM, así que es el campo donde el modelo conceptual se traslada de la manera más directa. La unidad de módulo es el **módulo Nest (por dominio)** y las capas aparecen como **sufijos de provider y carpetas**.
- Stack de referencia: NestJS, Prisma (cliente tipado) o TypeORM como ORM, `class-validator` (validación de peticiones), Jest para las pruebas. El bus CQRS (`@nestjs/cqrs`) es opcional — para la separación comando/consulta del modelo conceptual basta con separar servicios, y el bus se elige cuando hay mucho manejo de eventos.
- Los límites los hace cumplir la DI de Nest: **un provider que no está en los `exports` del módulo no puede ser inyectado por otro módulo.** Los límites de import de archivos los hace cumplir `dependency-cruiser`.

## Disposición

```
src/
  kit/                          L1 — funciones puras, códigos de error, tipos (sin imports de Nest)
  platform/                     LM1 — PrismaService (o DataSource), ayudante de transacciones, módulo de configuración
  order/
    order.module.ts             módulo: providers y exports (solo lo que se hace público)
    data/
      order.repository.ts       L2 nivel inferior — Repository que envuelve llamadas a Prisma
      order.template.ts         L2 nivel inferior — consultas complejas (SQL crudo, joins)
      order-command.service.ts  L2 nivel superior — escrituras, transacciones
      order-query.service.ts    L2 nivel superior — solo lectura, devuelve DTO
    coordinate/                 LM2 — combinación de L2 de la misma preocupación (solo cuando hace falta)
    order-command.composite-service.ts   L3 — caso de uso
    order.listener.ts           L3 — manejo de eventos (@OnEvent)
    order.task.ts               L3 — programación (@Cron)
    order.controller.ts         Route — validación de DTO, guard de autenticación, conversión de respuesta, solo llama a composite
    dto/                        DTO de petición y respuesta (class-validator)
  payment/ …
```

| Capa conceptual | En Nest | Nombre |
|---|---|---|
| L1 | `src/kit`, funciones puras en la carpeta del dominio | `convertUnit()` |
| LM1 | `PlatformModule` | `PrismaService`, `TransactionHost` |
| L2 nivel inferior | Repository / Template con `@Injectable()` | `OrderRepository`, `OrderTemplate` |
| L2 nivel superior | servicios con `@Injectable()` | `OrderCommandService`, `OrderQueryService` |
| LM2 | Coordinator con `@Injectable()` | `PaymentCoordinator` |
| L3 | CompositeService / Listener / Task con `@Injectable()` | `OrderCommandCompositeService` |
| Route | `@Controller()` | `OrderController` |

## Límites de módulo

```ts
// order.module.ts
@Module({
  imports: [PlatformModule, PaymentModule],
  providers: [OrderRepository, OrderTemplate, OrderCommandService, OrderQueryService, OrderCommandCompositeService],
  controllers: [OrderController],
  exports: [OrderCommandCompositeService],     // a los demás módulos solo se les expone el caso de uso
})
export class OrderModule {}
```

- No pongas servicios L2 ni Repositories en `exports`. Los demás dominios inyectan solo los casos de uso de este módulo (o interfaces de contrato) — un camino que se salte L2 queda bloqueado en la etapa de DI.
- Si hace falta un ciclo entre módulos (`forwardRef`), es una señal de diseño. Convierte uno de los lados en un evento, o sube la preocupación a LM2.
- La prohibición de referencias en el mismo nivel (servicio ↔ servicio) no la puede bloquear la DI porque están en el mismo módulo. Se hace cumplir con una comprobación de los destinos de inyección por constructor (véase Cumplimiento más abajo).

## Comandos y consultas

- Escritura: `OrderCommandService` se ejecuta dentro de `prisma.$transaction(...)` (o `DataSource.transaction` de TypeORM). Las transacciones viven solo en el nivel superior de L2.
- Lectura: `OrderQueryService` coloca los resultados de `select` y de joins directamente en los DTO de respuesta. No tiene que pasar por el modelo de entidades.
- Los tipos generados por Prisma (entidades) no se devuelven fuera de L2. Se convierten a DTO en el límite de L2.

## Cumplimiento

| Qué | Herramienta |
|---|---|
| Bloquear la inyección del L2 de otro módulo | `exports` del módulo Nest (error de DI en tiempo de ejecución) |
| Dirección de imports de archivos (controlador → repository prohibido, `kit` no importa nada, sin imports entre carpetas de dominio) | reglas de `dependency-cruiser` (mismo enfoque que la plantilla depcruise de `profiles/frontend.next-web/enforcement/`) |
| Sin inyección de servicios del mismo nivel | comprobación de los tipos de los parámetros del constructor — una regla personalizada de eslint o una regla por archivo de dependency-cruiser |
| Formato, lint, tipos | `biome` o `eslint`+`prettier`, `tsc --noEmit` |

## Marcadores

Se ponen en JSDoc (`core/docs/es/conventions/strata-markers.md`):

```ts
/** @strata:layer L2-QueryService */
@Injectable()
export class OrderQueryService { … }
```
