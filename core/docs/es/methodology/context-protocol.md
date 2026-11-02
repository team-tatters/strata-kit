# 09 — Context Protocol: Constraint-Aware Context Loading

> Canónico: strata-kit `core/docs/es/methodology/context-protocol.md` (migrado el 2026-10-29 desde strata `docs/09-context-protocol.md`, DEC-2026-10-29-11).

> Partiendo de los principios de las tarjetas del kit (`rec.context.entry-view-budget`, `rec.session.split-at-task-boundary`, `rec.session.state-in-files`) y de `core/docs/es/methodology/session-splitting.md`, este documento define las reglas de carga de contexto consciente de las restricciones.

## 1. Definición del problema

Las vías por las que una restricción de dominio decidida en un ADR (por ejemplo "prohibido hard-delete", "Bitemporal obligatorio") se pierde en la implementación:

1. La prosa del ADR es demasiado larga para leerla entera cada vez
2. Los detalles del ADR se pierden en el compaction
3. Un Worker tiene un contexto independiente — no conoce la discusión del ADR en la sesión del Builder
4. Si la especificación de la tarea omite una restricción de dominio, el Worker no puede detectarla

## 2. Solución: las restricciones entran en la vista de entrada como resumen; el registry completo se lee cuando hace falta

### Niveles de contexto

```
T0 — Universal (siempre cargado, dentro de 12KB — rec.context.entry-view-budget)
  ├── AGENTS.md + CLAUDE.md            (guía generada — resumen de las tarjetas must, resumen de restricciones dentro de 2KB)
  └── active/{session-id}.yaml         (active-task por sesión — DEC-2026-08-19-05)

T1 — Session (al empezar la sesión)
  ├── El último archivo de handoff
  ├── decisions.yaml                   (índice generado, cuando hace falta — la fuente de verdad son los registros de decisions/)
  └── constraint-registry.yaml         (cuando hace falta — por el enlace de la vista de entrada)

T2 — Domain (según el objetivo de la tarea)
  ├── La página de nodo del nodo temático (unión de forma final, política, decisiones, historial de trabajo y deuda — generada, el punto de entrada)
  ├── La Constraint Card completa de ese dominio
  └── La sección Decision Outcome del ADR relacionado

T3 — Implementation (al implementar)
  ├── Los archivos fuente objetivo
  ├── Los archivos de prueba
  └── layer-rules.yaml (la sección de esa capa)
```

### Reglas de constraint-registry.yaml

- **Ubicación**: `.strata/constraint-registry.yaml` (dentro del proyecto)
- **Límite de tamaño**: dentro de 3KB. La guía generada solo lleva un resumen de 2KB y enlaza el archivo completo
- **Cuando supera 3KB**: mover los elementos `severity: should` a un archivo aparte. En el registry solo se mantienen `must`/`must-not`
- **Cuándo se actualiza**: al mismo tiempo que un ADR pasa a accepted y que se crea una Constraint Card
- **Formato**: el mismo índice YAML que `decisions.yaml`

```yaml
constraints:
  - id: CC-NNN-01
    source: ADR-NNN
    severity: must
    scope: {domains: [{domain}], layers: [{layer}]}
    rule: "{regla ejecutable de una línea}"
    status: active
```

### Reglas de decisions.yaml (corregidas el 2026-08-19)

- El `decisions.yaml` que se lee cuando hace falta es un **índice compacto regenerado a partir de los registros (`.strata/decisions/DEC-*.yaml`)**. Está prohibido editarlo a mano.
- Solo la **CLI decision writer** añade decisiones, asigna números y regenera el índice (serializado con flock — seguro con varias sesiones a la vez, DEC-2026-08-19-05. Correspondencia rol → implementación: `python3 -m kb --help`, `core/docs/es/kb-engine.md`).
- Cuando se necesita detalle, se carga el registro completo mediante la ruta `record:` de la entrada del índice — el mismo patrón que el detalle por capas de Registry (1 línea) → Card (~50 líneas) → ADR (~200 líneas) (resumen del índice → registro completo).
- La ubicación física de Tier P sigue el placement profile (`core/docs/es/environment/data-placement.md` §1.5 — embedded=repo, detached=vault `projects/{n}/strata/`).

## 3. Carga de Context por Agent Role

### Builder

| Situación | T0 | T1 | T2 | T3 |
|---|---|---|---|---|
| Crear una tarea | ✓ constraint-registry filtrado | ✓ | Página de nodo → las Cards de ese dominio | - |
| Redactar un ADR | ✓ | ✓ | Página de nodo (comprobar la cadena de decisiones) | - |
| Extraer una Constraint | ✓ | - | - | - |

El Builder lee constraint-registry.yaml, filtra por el dominio/capa de la tarea
e inyecta las constraints correspondientes en `scope.constraints` de la especificación de la tarea.
De la misma manera, encuentra con el resolvedor de cobertura la especificación que posee el alcance del cambio (`covers`) y la inyecta en `scope.docs_to_update`.
La página de nodo es el punto de entrada de estas dos inyecciones — al abrir un nodo se ven en una sola pantalla la especificación vigente, las restricciones activas y las decisiones vigentes.

### Worker

| Situación | T0 | T1 | T2 | T3 |
|---|---|---|---|---|
| Ejecutar una tarea | Solo CLAUDE.md | - | - | ✓ |

**El Worker no lee constraint-registry.yaml directamente.** Tampoco lee directamente las páginas de nodo.

Usa solo lo que el Builder inyectó en `scope.constraints` y `scope.docs_to_update` de la especificación de la tarea.
Esto concuerda con el principio de **autocontención** de la especificación de la tarea.

```yaml
# La especificación de tarea que recibe un Worker
scope:
  layer: "L2_DataLayer"
  constraints:
    - id: "CC-NNN-01"
      rule: "Una restricción que se aplica a este scope"
    - id: "CC-NNN-02"
      rule: "Otra restricción"
```

El Worker convierte este `scope.constraints` en `constraint_compliance` del informe de finalización.

### Supporter

| Situación | T0 | T1 | T2 | T3 |
|---|---|---|---|---|
| Buscar constraints | ✓ búsqueda en el registry | - | Solo los resultados de la búsqueda | - |

A petición del Builder, el Supporter busca las constraints de un dominio/capa concretos.

## 4. Reglas de Context Budget

```
CB-1: T0 (AGENTS.md + CLAUDE.md) dentro de 12KB, dentro de 14KB incluida la guía heredada (wizard verify)
  → el registry de restricciones y el índice de decisiones no son T0; las restricciones entran en la guía generada como un resumen de 2KB
  → si la guía crece demasiado, reducirla primero a un índice (centrado en referencias)
  → la ruta de entrada que lee using-strata (cuerpo de la skill, registry del core, constitución) la informa verify por separado (2026-10-29, sin tope)

CB-2: Una Constraint Card de T2 ocupa como máximo 10KB por dominio
  → si supera 10KB, cargar solo el resumen de una línea del registry en lugar de la Card completa

CB-3: La carga total de .strata/ es de como máximo 30KB (T0+T1+T2 sumados)
  → si se supera, sustituir T2 por las filas correspondientes del registry

CB-4: El ADR completo solo lo carga el Builder (redactar un ADR / extraer una Constraint)
  → los demás roles llegan a la decisión del ADR a través de la Constraint Card
  → esta es la razón de ser de la Constraint Card

CB-5: Una página de nodo ocupa como máximo 8KB por nodo (junto con el presupuesto de Card de CB-2, mantiene el tope de T2)
  → el generador recorta la sección de historial de trabajo a las últimas 5 entradas y la sección de decisiones a la vigente más la anterior, para ajustarse al presupuesto
  → si aun así se supera, se conservan solo las secciones de forma final y política y el resto se sustituye por enlaces
```

## 5. Resiliencia al Compaction

```
Antes del compaction:   el ADR completo + la discusión detallada (presentes en el contexto)
Después del compaction: solo queda un resumen — riesgo de perder el detalle del ADR

Vía de recuperación de la Constraint:
  constraint-registry.yaml (está en un archivo, así que siempre se puede volver a leer)
  → el resumen de una línea muestra de inmediato "qué hay que cumplir"
  → si hace falta detalle, consultar la Constraint Card individual (T2)
  → si hace falta un contexto más profundo, consultar source_adr

Detalle por capas (Layered Detail):
  Registry (1 línea)  →  Página de nodo (~100 líneas)  →  Card (~50 líneas)  →  ADR (~200 líneas)
  resumen en vista de entrada  una vez, al entrar en un dominio   se carga si hace falta   casi nunca se carga
```

La página de nodo no sustituye a la Card ni al ADR. Es un punto de entrada que indica qué Card, qué ADR y qué especificación están vigentes; el contenido está al otro lado de los enlaces.

## 6. Relación con la gestión de contexto existente

| Existente (tarjetas del kit · session-splitting.md) | Este documento (extensión) |
|---|---|
| Diseño de niveles de CLAUDE.md (§2·§4, `wizard verify`) | Se mantiene — el resumen de restricciones va en la guía generada, el registry completo se lee cuando hace falta |
| Protocolo de handoff (`strata.handoff`, session-splitting.md §5) | Se mantiene — se añade al handoff el estado de la extracción de constraints |
| Defensa frente al compaction (execution-modes.md, `kb pre-compact`, SessionStart compact) | Reforzada — el registry es un ancla de recuperación adicional |
| Guía de presupuesto de tokens (session-splitting.md §5.2) | Ampliada — se añaden las reglas CB-1~5 |
| Distinción Memory vs Handoff vs KB (§7, rec.session.state-in-files, rec.kb.session-records-in-vault) | Se mantiene — las Constraint Cards se colocan en la KB |
| (nuevo) Nodo temático | Punto de entrada de T2 — la página de nodo es un producto de la capa Index, no una fuente de verdad (core/docs/es/knowledge-base/vault-structure.md) |

## 7. Memoria, traspaso y KB

La memoria del arnés (en Claude Code, `~/.claude/projects/<proyecto>/memory/`) se lee en cada inicio de sesión a través de su índice, así que lo que se guarda ahí cambia el juicio de la sesión siguiente.

| Qué | Dónde | Por qué |
|---|---|---|
| Estado de avance — el trabajo en curso, lo siguiente, cambios sin confirmar, bloqueos | El archivo activo (`.strata/local/active/`) y el traspaso | Caduca al terminar la sesión; en la memoria, la sesión siguiente lee un estado pasado como un hecho presente |
| Hechos duraderos — preferencias del usuario, instrucciones sobre cómo trabajar, dónde están los recursos externos | La memoria del arnés | Lo que toda sesión debe leer sin pedirlo |
| Decisiones y políticas | Registros de decisión, tarjetas | La fuente de verdad revisada; una retroalimentación de la memoria que se vuelve política pasa aquí |
| Diseño, especificaciones, conocimiento | La KB de la vault | Ligados al código por enlaces y cobertura |

**El estado de avance no va a la memoria.** Al cerrar una sesión, los hechos de estado de avance que escribió en la memoria pasan al traspaso (paso de revisión de memoria de `strata.handoff`, DEC-2026-10-31-16).

**Fecha de verificación.** La cabecera de un hecho de memoria lleva el último día en que se confirmó correcto como `verified: YYYY-MM-DD` (DEC-2026-10-31-14·34). El `modified` del arnés es el día en que cambió; `verified` es el día en que se vio que seguía siendo correcto. El agente lo escribe al escribir o editar un hecho, y la revisión del traspaso lo actualiza para los hechos que la persona confirma como aún correctos.

**Limpieza.** `python3 -m kb hygiene --memory` lista los candidatos a limpieza de la memoria de la carpeta actual con sus motivos: caducado (verified, si no modified, de más de 60 días — configuración de usuario `memory.stale_days`), sin fecha, coincidencia de expresiones de estado, formato desconocido, posibles pares de retroalimentación contradictoria, y un índice que no coincide con los archivos. La herramienta solo lee y nunca imprime el cuerpo. Una coincidencia de expresiones de estado es una coincidencia, no un veredicto: una regla que nombra un estado también coincide. Mover, fusionar y borrar solo se hace con los hechos que la persona aprueba uno a uno. Un borrado mueve el archivo a `_archive/` en el mismo directorio, escribe `retired` y `retired_reason` en su cabecera y quita la línea del índice (DEC-2026-10-31-17). `wizard verify` muestra el tamaño del índice de memoria y avisa por encima de 12 KB sin fallar (DEC-2026-10-31-19). La memoria de Codex queda fuera de alcance por ahora (DEC-2026-10-31-13).
