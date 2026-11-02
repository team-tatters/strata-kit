# 02 — Guía de división de sesiones

> Canónico: strata-kit `core/docs/es/methodology/session-splitting.md` (migrado el 2026-10-29 desde strata `docs/02-session-splitting.md`, DEC-2026-10-29-11).

> Documento que el Builder debe consultar antes de escribir una orden de trabajo.
> Dividir sesiones es la estrategia más eficaz para «evitar la pérdida de contexto».

## 1. Matriz de decisión de división

### 1.1 Criterios cuantitativos

| Indicador | Sesión única | 2-3 sesiones | 4+ sesiones |
|---|---|---|---|
| Archivos modificados | ≤15 | 16-40 | 40+ |
| Capas afectadas | 1-2 | 3 | 4+ |
| Archivos de referencia | ≤10 | 11-25 | 25+ |
| Turnos de conversación previstos | ≤20 | 21-40 | 40+ |
| Dominios nuevos | 1 | 2 | 3+ |
| Pasos de exploración necesarios | ≤2 | 3-4 | 5+ |

### 1.2 Criterios cualitativos

**Situaciones que exigen dividir de inmediato:**
- «Primero investiga A y, según el resultado, decide la dirección B» → sesión de exploración + sesión de implementación
- «Refactoriza el código existente y añade también una funcionalidad nueva» → sesión de refactorización + sesión de funcionalidad
- «Cambia a la vez el frontend y el backend» → sesión FE + sesión BE
- «Escribe primero las pruebas y verifica tras implementar» → sesión TDD (patrón Writer/Reviewer)

**Situaciones en las que basta una sesión única:**
- Corrección de un error en un solo archivo
- Añadir un CRUD idéntico a un patrón existente
- Completar pruebas
- Actualizar documentación
- Cambio de configuración

## 2. Catálogo de patrones de división

### 2.1 División secuencial por capas (Layer-Sequential)

El patrón más común. Se usa cuando hay que construir una funcionalidad nueva desde la base.

```
Solicitud: «Implementa el nuevo dominio de pedidos (Order)»

Session 1: L1 + LM1 (base)
├── Definir OrderEntity, el enum OrderStatus, OrderType
├── Mapeo de Document de MongoDB
└── Configurar la herencia de la Audit Entity común
    → Traspaso: entidades/tipos fijados, lo siguiente es L2

Session 2: L2 DataLayer (datos)
├── OrderCommandService (create, update, delete)
├── OrderQueryService (findById, findByStatus, search)
├── OrderRepository, OrderTemplate
└── Pruebas unitarias
    → Traspaso: L2 completa, lo siguiente es LM2 o L3

Session 3: L3 Composite (negocio)
├── OrderCompositionService
├── Lógica de integración de pagos (usando PaymentCoordinator)
├── Lógica de descuento de inventario (usando InventoryCoordinator)
└── Pruebas de integración
    → Traspaso: L3 completa, lo siguiente es el Controller

Session 4: Route Controller (API)
├── OrderController (definición de endpoints)
├── Request/Response DTO
├── Configuración de Validation
└── Generación de documentación de la API
```

### 2.2 División paralela por dominio (Domain-Parallel)

Se usa cuando se trabaja a la vez en varios dominios de la misma capa.

```
Solicitud: «Implementa L2 de los dominios User, Order y Product»

Session A: L2 — dominio User (independiente)
Session B: L2 — dominio Order (independiente)
Session C: L2 — dominio Product (independiente)

Condición previa: L1 Component debe estar fijado de antemano
Condición previa: no debe haber referencias cruzadas de L2 entre dominios (lo garantizan las reglas de Strata)
```

### 2.3 División explorar-implementar (Explore-Implement)

Se usa en trabajos de dirección incierta.

```
Solicitud: «Encuentra las partes lentas y optimízalas»

Session 1: Exploración (Explore)
├── Analizar el código e identificar los cuellos de botella
├── Interpretar los resultados del perfilado
├── Obtener 3 estrategias de optimización
└── Registrar los resultados de la exploración en $STRATA_VAULT/projects/{name}/sessions/ (Tier V)
    → Traspaso: estrategia de optimización fijada, plan de implementación detallado

Session 2-N: Implementación (Implement)
├── Cambios de código según la estrategia fijada
├── Pruebas de rendimiento
└── Registrar los resultados
```

### 2.4 División TDD (Writer/Reviewer)

El patrón Writer/Reviewer que recomienda Anthropic.

> **Relación con el eje de verificación:** este patrón Writer/Reviewer es **un ejemplo** de implementar el **Verification Tier**
> (Self-Verified / Cross-Verified) de `core/docs/es/methodology/verification-tier.md` mediante la división de sesiones.
> La definición del Tier es propiedad de `core/docs/es/methodology/verification-tier.md` como fuente de verdad, y aquí no se duplica.
> - Si el Reviewer es de la misma familia de herramientas → **Self-Verified**
> - Si es de otra familia de modelos → **Cross-Verified** (implementación: `skills/strata.review/SKILL.md`)

```
Session 1: Escribir pruebas (Writer)
├── Escribir casos de prueba a partir de los requisitos
├── Confirmar que todas las pruebas fallan
└── Hacer commit de los archivos de prueba

Session 2: Implementar (Writer)
├── Escribir código que haga pasar las pruebas de Session 1
├── Confirmar que todas las pruebas pasan
└── Hacer commit del código de implementación

Session 3 (opcional): Revisión (Reviewer)
├── Revisar el código en un contexto nuevo
├── Verificar que el código de Session 2 respeta las reglas de capa
└── Sugerir refactorizaciones
```

### 2.5 División frontend-backend (Frontend-Backend)

```
Solicitud: «Implementa tanto la UI como la API de la funcionalidad de pedidos»

Session BE: Backend
├── Implementar L2-L3-Controller
├── Fijar el documento de especificación de la API ($STRATA_VAULT/projects/{name}/tasks/.../api-specs/order.yaml, Tier V)
└── Traspaso: endpoints de la API + DTO fijados

Session FE: Frontend
├── Referenciar la especificación de la API (Contract): la condición previa es que **el Contract esté fijado**, no que BE esté completo. Se puede avanzar antes con un mock transport
├── Orden Contract/DataState/Feature ajustado a la variante de Frontend
├── Declarar entry_point (design_first | dev_first | spec_first | change): el orden no se fija y la comprobación de coherencia es la puerta (core/docs/es/architecture/frontend-design-contract.md)
└── Pruebas de integración de la API + comprobación de coherencia Impl↔Design (design_sync)
```

La sesión BE y la sesión FE pueden ir en paralelo una vez fijado el Contract. También se permite `dev_first`, en que FE va primero: en ese caso el Contract es un entregable de la sesión FE y la sesión BE lo verifica.

## 3. Formato de la especificación de tarea (Task Specification)

El documento que el Builder escribe para cada sesión:

```yaml
# $STRATA_VAULT/projects/{name}/tasks/{date}/{nn}-{title}/task-{id}.yaml
task:
  id: "ORD-L2-001"
  title: "Implementar Order L2 DataLayer"
  session_type: "implement"      # explore | implement | review | refactor
  estimated_turns: 15
  estimated_files: 8

scope:
  layer: "L2_DataLayer"
  domain: "order"
  directories:
    - "src/data/order/"
    - "test/data/order/"
  
constraints:
  layer_rule: "@core/rules/layer-rules.yaml#L2_DataLayer"
  naming_rule: "@core/rules/naming-convention.yaml#backend.L2"
  can_reference:
    - "L1_Component"
    - "LM1_Inherite"
  cannot_reference:
    - "L2_DataLayer (otros dominios)"
    - "LM2_Coordinate"
    - "L3_Composite"

inputs:
  prior_session: "ORD-L1-001"    # ID de la sesión anterior (null si no hay)
  entities:
    - "@src/components/order/OrderEntity.ts"
    - "@src/components/order/OrderStatus.ts"
  reference_implementation:
    - "@src/data/user/UserCommandService.ts"  # referencia de patrón

deliverables:
  files:
    - path: "src/data/order/OrderCommandService.ts"
      description: "Servicio transaccional de CUD"
    - path: "src/data/order/OrderQueryService.ts"
      description: "Servicio de consultas de solo lectura"
    - path: "src/data/order/OrderRepository.ts"
      description: "Implementación del Repository de MongoDB"
    - path: "test/data/order/OrderCommandService.test.ts"
      description: "Pruebas unitarias de CommandService"
    - path: "test/data/order/OrderQueryService.test.ts"
      description: "Pruebas unitarias de QueryService"

acceptance_criteria:
  - "Todas las pruebas unitarias pasan"
  - "Sin violaciones de dependencia entre capas (pasa la verificación del Hook)"
  - "Se respetan las convenciones de nomenclatura"
  - "Un método gestiona una sola entidad"

context_budget:
  max_reference_files: 5
  max_loaded_tokens: 20000       # límite de tokens de los archivos de referencia
  compaction_strategy: "file-based"  # las decisiones van a archivos, el contexto se mantiene ligero
```

## 4. Protocolo de propuesta de división del Builder

El procedimiento de análisis que realiza el Builder al recibir una solicitud del usuario:

```
Usuario: «Implementa toda la funcionalidad de gestión de pedidos»

Análisis del Builder:
┌─────────────────────────────────────────┐
│ 📋 Análisis del alcance del trabajo      │
│                                          │
│ Capas afectadas: L1, L2, LM2, L3, Route (5) │
│ Archivos modificados previstos: ~35      │
│ Archivos de referencia previstos: ~15    │
│ Turnos de conversación previstos: ~60    │
│                                          │
│ ⚠ Veredicto: hay que dividir la sesión (se recomiendan 4 sesiones) │
│                                          │
│ Propuesta:                               │
│ Session 1: entidades/tipos L1 (15 min, ~8 turnos)  │
│ Session 2: L2 DataLayer (30 min, ~15 turnos)       │
│ Session 3: L3 Composite (30 min, ~15 turnos)       │
│ Session 4: Controller + API (20 min, ~12 turnos)   │
│                                          │
│ Paralelizable: separar subdominios en Session 2    │
│ Cadena de dependencias: S1 → S2 → S3 → S4          │
└─────────────────────────────────────────┘
```

El Builder **muestra primero este análisis al usuario y obtiene su aprobación** antes de generar las órdenes de trabajo.

## 5. Señales de fin de sesión

Los momentos en que el Builder debe terminar la sesión actual y hacer el traspaso:

| Señal | Respuesta |
|---|---|
| Más de 15 turnos de conversación | Hacer el traspaso tras terminar la unidad de trabajo actual |
| Se produce una compactación (Compaction) | Guardar el estado de inmediato; si es posible, hacer el traspaso tras terminar la unidad actual |
| Hay que volver a explicar «como le dije antes…» | Señal de pérdida de contexto: preparar el traspaso de inmediato |
| Empieza un trabajo que cruza el límite de una capa | Terminar la capa actual y pasar a la siguiente sesión |
| Cambio de dirección a partir de los resultados de la exploración | Documentar los resultados de la exploración; la implementación va en una sesión nueva |
| El usuario cambia los requisitos | Documentar los cambios, reanalizar y hacer un plan nuevo |
| La conversación supera la línea de aviso (unos 400.000 tokens por defecto) | Terminar la unidad en curso, hacer el traspaso en el siguiente límite de tarea (con la sección de hechos e hipótesis) y abrir una sesión nueva; como muy tarde antes del tope (unos 600.000 por defecto) — 5.1 |
| Los intentos sobre una hipótesis se bloquean dos veces | No buscar un tercer rodeo; detenerse e informar de los hechos medidos y las opciones — 5.1 |

### 5.1 Señales de reinicio: la línea de aviso de tokens y dos fallos con una hipótesis

Ninguna de las dos señales significa cortar el trabajo donde está. Ambas significan terminar la unidad en curso y dividir en el siguiente límite de tarea (tarjeta `rec.session.split-at-task-boundary`). La compactación salta cuando la ventana está casi llena, así que cuanto mayor es la ventana más tarde interviene, y una conversación atascada en una hipótesis nubla el juicio sea cual sea su longitud. Las dos señales cubren estos dos casos.

**La línea de aviso de tokens y el tope.** Cuando la conversación supera unos 400.000 tokens, termina la unidad, escribe el traspaso en el siguiente límite de tarea y pasa a una sesión nueva. Aunque el siguiente límite quede lejos, pasa antes de unos 600.000 tokens. Ambos valores son números fijos de tokens, no proporciones de la ventana (DEC-2026-10-31-09; valores DEC-2026-10-31-33). Son valores iniciales pensados para cerrar una sesión mucho antes de la compactación cuando la ventana por defecto es de 1M; todavía no hay ninguna medición de nuestro propio trabajo detrás. Se cambian con `session.restart_tokens` y `session.restart_limit` en la configuración del usuario `~/.strata/config.yaml`; la línea `restart signal` de la cabecera de inicio muestra los valores actuales. En Claude Code el tamaño actual se ve con el comando `/context` o en la línea de estado. Si el agente no puede leerlo, se lo dice la persona.

**Dos fallos con una hipótesis.** Cuando los intentos se bloquean dos veces, no busques un tercer rodeo: detente e informa de los hechos medidos y las opciones. Una hipótesis es una causa supuesta: correcciones en sitios distintos son la misma hipótesis si descansan en el mismo «la causa es X». Un fallo significa que el síntoma que se quería comprobar (la misma prueba que falla, el mismo error) sigue ahí. Tras el informe, la persona decide la dirección, o el traspaso registra la hipótesis descartada y una sesión nueva lo vuelve a mirar.

**La sección de hechos e hipótesis del traspaso.** Una sesión que termina por una señal de reinicio rellena la sección de hechos e hipótesis del traspaso con los hechos confirmados (y con qué se confirmaron), las suposiciones aún no confirmadas y las hipótesis descartadas (y por qué) (DEC-2026-10-31-11). La sesión siguiente lee primero esta sección y no retoma una hipótesis descartada. Una sesión que trabaja con el registro compartido escribe los mismos tres campos en su entrada de reinicio (agent-operations 5.3).

### 5.2 Presupuesto de tokens de la conversación y momento de la compactación

| Ventana | Compactación automática por defecto | Con `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=80` | Frente a la línea de aviso de 400.000 y el tope de 600.000 |
|---|---|---|---|
| 200.000 tokens | 200.000 (el límite de la ventana) | 160.000 | La compactación llega antes; en esta ventana la señal de compactación hace el papel de la línea de aviso |
| 1.000.000 tokens | unos 967.000 | unos 770.000–800.000 | La línea de aviso y el tope llegan antes que la compactación |

El coste fijo es el prompt de sistema del arnés, las definiciones de herramientas, la guía, la cabecera de inicio y la memoria. Lo que añade strata-kit (guía y cabecera) son unos 8–12 KB, aproximadamente 3.000–5.000 tokens (`wizard verify`); el resto depende del arnés y del número de servidores MCP conectados, así que se lee con `/context`.

Los puntos de compactación por defecto proceden de la documentación de Claude Code (model-config). La ventana de autocompactación (el ajuste `autoCompactWindow`, el comando `/autocompact`, la variable de entorno `CLAUDE_CODE_AUTO_COMPACT_WINDOW`, de 100.000 a 1.000.000) es el nivel de llenado al que salta la compactación, y `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE` es un porcentaje de esa ventana que solo puede adelantar la compactación. La variable de entorno solo lee sufijos como `500k` desde la v2.1.304. En una ventana grande la compactación llega mucho después de la línea de aviso, así que cerrar sesiones es tarea de la línea de aviso y del tope, no de la compactación. Cambiar los ajustes de compactación lo decide el usuario.

## 6. Flujo de funcionamiento del comando /split-session

El procedimiento que realiza el Builder cuando el usuario ejecuta `/split-session`:

```
1. Analizar el alcance de la solicitud actual
2. Aplicar la matriz de división (véase la sección 1)
3. Proponer el plan de división al usuario
4. Si se aprueba:
   a. Generar task-{id}.yaml para cada sesión
   b. Actualizar TASK_TRACKER.md
   c. Indicar el orden de dependencias
   d. Iniciar de inmediato la primera sesión, o guardar solo el plan completo
```
