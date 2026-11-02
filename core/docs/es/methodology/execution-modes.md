# Modos de ejecución (Execution Modes)

> Canónico: strata-kit `core/docs/es/methodology/execution-modes.md` (migrado el 2026-10-29 desde strata `docs/04-agents/execution-modes.md`, DEC-2026-10-29-11).

> Define los modos de ejecución duales de la metodología Strata.
> Toda sesión debe declarar explícitamente su modo de ejecución al empezar.

## Principios

- **El valor por defecto es Task Mode** — si no se declara, la sesión se considera Task Mode
- **Verbal Mode es una excepción deliberada** — solo se puede usar si se elige explícitamente
- **El cambio de modo es unidireccional** — Verbal → Task está permitido, Task → Verbal está prohibido

> **Correspondencia con los modos de trabajo (2026-10-29, DEC-2026-10-29-15·19)**: los cuatro modos de trabajo de la skill de entrada (paso 4 de using-strata) dividen estos dos modos. Verbal = solo lectura (investigación, preguntas, revisión) + un cambio de sesión única que termina sin archivo de tarea; Task = varias sesiones (trabajo con una orden) + orquestación (varias sesiones o roles en paralelo). Las obligaciones de una sesión (archivo activo, traspaso, orden) las fija el modo de trabajo; los criterios cuantitativos de abajo sirven para juzgar si el trabajo puede terminar como Verbal.
- **Resumir y confirmar antes de cambiar el estado** — para el trabajo difícil de deshacer o que cambia el estado observable (editar archivos, inyectar en una sesión, llamar a una CLI externa, commit/despliegue), se presenta primero un resumen de lo que se hará y se ejecuta solo después de que el usuario confirme

## Definiciones de los modos

### Task Mode (por defecto)

El modo en el que el Builder redacta las especificaciones `_order.yaml` + `task-{nn}.yaml` y el Worker ejecuta a partir de ellas.

**Cuándo se aplica:**
- Planes de ejecución por sprint
- Implementación de funcionalidades en varias sesiones
- Cambios en 3 o más archivos
- Impacto en 2 o más capas
- Establecer un nuevo patrón de arquitectura

**Obligaciones:**
- Redactar `_order.yaml` (la orden de trabajo)
- Redactar cada `task-{nn}.yaml` (la especificación de ejecución del Worker)
- Actualizar TASK_TRACKER.md
- Redactar el documento de traspaso (handoff)
- Devolver las decisiones de arquitectura a la KB

### Verbal Mode (excepción)

El modo en el que el Builder ejecuta directamente, o resuelve el trabajo rápido mediante instrucciones verbales.

**Cuándo se aplica:**
- Ideación, exploración, revisión de diseño
- Edición de un solo archivo
- Hotfix de errores (urgente)
- Edición de documentos, cambios de configuración
- Trabajo que se puede terminar en 10 turnos

**Obligaciones:**
- No hace falta especificación de tarea
- No hace falta actualizar TASK_TRACKER
- El traspaso es opcional (se registra si hay decisiones)
- **Registrar un registro de decisión (CLI decision writer) cuando se toma una decisión no se puede eximir** (regla absoluta independiente del modo — `decisions.yaml` es un índice generado, nunca se edita a mano)

## Criterios de selección de modo (cuantitativos)

```
IF (archivos modificados ≤ 3) AND (capas afectadas ≤ 1) AND (turnos previstos ≤ 10)
   AND (dominios nuevos = 0) AND (fases de exploración ≤ 1):
    → Verbal Mode permitido
ELSE:
    → Task Mode obligatorio
```

| Indicador              | Verbal permitido | Task obligatorio |
| ---------------------- | ---------------- | ---------------- |
| Archivos modificados   | ≤ 3              | 4+               |
| Capas afectadas        | 1                | 2+               |
| Turnos previstos       | ≤ 10             | 11+              |
| Dominios nuevos        | 0                | 1+               |
| Fases de exploración   | ≤ 1              | 2+               |

**Verbal solo se permite cuando todas las condiciones están dentro del rango Verbal. Si una sola se supera, Task es obligatorio.**

## Declaración del modo

Al empezar la sesión, se registra el modo en el archivo de esta sesión `.strata/local/active/{session}.yaml`, y se escribe el id de sesión del harness (Claude Code: `CLAUDE_CODE_SESSION_ID`) en `harness_session_id` — el encabezado de inicio y la restauración tras la compactación encuentran el archivo de esta sesión por ese campo o por el nombre del archivo:

```yaml
harness_session_id: "9496c8b3-…"   # CLAUDE_CODE_SESSION_ID
session:
  date: "2026-04-23"
  mode: "verbal"              # verbal | task
  declared_scope: "Revisión del diseño de debounce y briefing"
  escalation_threshold: 3     # pasar a task mode si se tocan más archivos que este número
  order_ref: null              # ruta de _order.yaml cuando se está en task mode
```

## Cambio de modo (Verbal → Task)

Cuando una sesión empezó como Verbal pero su alcance ha crecido:

1. Detectarlo en el autodiagnóstico de 5 turnos del Builder (comprobar el número de archivos y de capas)
2. Informar al usuario de que "hace falta pasar a Task Mode"
3. Redactar `_order.yaml` — incluir el campo `escalated_from: "verbal"`
4. Registrar el trabajo ya completado en la sección `completed_before_spec` de `_order.yaml`
5. Continuar el trabajo restante a partir de las especificaciones de tarea

```yaml
# _order.yaml (en el momento del cambio)
order:
  id: "2026.04.23-01"
  title: "Sincronización de debounce con MongoDB"
  escalated_from: "verbal"
  completed_before_spec:
    - "Se añadió la operación SET a CacheGenericOperator (completado en la fase verbal)"
  tasks:
    - id: "task-01"
      title: "Implementar DirtyMarkService"
      # ... las tareas posteriores llevan especificación normal
```

## Estrategia de asignación de modelos

Las tareas del Worker indican el **nivel de razonamiento (reasoning tier)** con el que se ejecutan. Se escribe un nivel, no el nombre de un modelo concreto; la correspondencia nivel → modelo corresponde al adaptador de la herramienta (neutral respecto a la herramienta).

### Criterios de asignación por nivel de razonamiento

| Nivel | Criterio de asignación | Coste relativo | Trabajo típico |
|-------|------------------------|----------------|----------------|
| **deep** (razonamiento alto) | Establecer un patrón nuevo, razonamiento entre capas, refactorizaciones complejas | Alto | Diseño de arquitectura + implementación, sistemas nuevos |
| **standard** (estándar) | Seguir un patrón existente, CRUD de una sola capa, pruebas, documentación | Bajo | REST Docs, añadir un QueryService, documentos de KB |
| **light** (ligero) | Búsqueda de documentos, consulta de reglas, resúmenes simples | El más bajo | Búsqueda en KB, resúmenes de traspaso |

> **La correspondencia nivel → modelo es responsabilidad del adaptador de la herramienta, no de Core.** (Ejemplo de adaptador — Claude: `deep→Opus`, `standard→Sonnet`, `light→Haiku`. Esta correspondencia pertenece al contexto del adaptador y no es una regla de Core.)

### Árbol de decisión para elegir modelo

```
¿La tarea sigue un patrón existente?
  ├─ YES → ¿Hay una implementación de referencia clara?
  │         ├─ YES → standard
  │         └─ NO  → deep (hay que interpretar el patrón)
  └─ NO  → ¿Hace falta un juicio de arquitectura nuevo?
            ├─ YES → deep
            └─ NO  → standard (código nuevo simple)
```

### Indicar el nivel en una especificación de tarea

```yaml
execution:
  model_tier: "standard"
  model_reason: "Sigue el patrón existente de REST Docs, no hace falta un juicio nuevo"
```

`model_reason` es obligatorio. El Builder debe indicar el fundamento de la elección del modelo para que la sesión siguiente pueda aplicar el mismo criterio.

## Nivel de razonamiento por defecto de cada agente

| Agente | Nivel por defecto | Modificable |
|--------|-------------------|-------------|
| Builder | deep | No (la orquestación siempre necesita razonamiento de alto nivel) |
| Worker | Fijado por tarea | Sí (deep o standard) |
| Supporter | light/standard | Sí (light para búsqueda, standard para resúmenes) |

> El adaptador de la herramienta hace corresponder un modelo concreto con el nivel (véase la nota "correspondencia nivel → modelo" más arriba). Core solo especifica el nivel.

## Eje de verificación (Verification Tier)

El eje de verificación es ortogonal al modo de ejecución. El modo de ejecución trata de *cómo se trabaja*; el eje de verificación trata de *quién verifica el resultado*.
Los valores del enum son `solo | self_verified | cross_verified`.
Las definiciones, los valores por defecto y el rango en el que `cross_verified` es obligatorio al cambiar una fuente de verdad (SoT) de Core los rige `core/docs/es/methodology/verification-tier.md`, que es la source of truth.
La revisión de Cross-Verified se hace con `skills/strata.review/SKILL.md` (envía una vez un review packet a un reviewer de contexto nuevo).

## Bucle de retroalimentación de la metodología (Methodology Feedback Loop)

Las lagunas de metodología que encuentra un Worker/Reviewer se comunican como `methodology_signals`, y el Builder las registra en el backlog y las promueve.
El flujo y la Promotion Gate los rige la sección «Promotion Gate» de `core/docs/es/methodology/task-spec-schema.md`, que es la source of truth.
Los esquemas de campos de `methodology_signals` y de `methodology-backlog.yaml` los define `core/docs/es/methodology/task-spec-schema.md`.

## Eje de operaciones (Agent Operations)

Sobre el modo de ejecución y el eje de verificación, la disciplina operativa para ejecutar agentes **en número y durante mucho tiempo** se trata como un eje aparte:
multisesión (hub-and-spoke), lote nocturno (budgeted batch), Decision Inbox y la puerta de verificación autoinformada.
→ `core/docs/es/methodology/agent-operations.md` (este documento solo hace referencia; las reglas se definen allí)

## Reglas absolutas (independientes del modo)

> **Esta sección no es la fuente canónica** (DEC-2026-10-29-19). Qué reglas se aplican a un proyecto lo deciden la constitución (los artículos de `core/constitution/constitution.yaml`) y las tarjetas que el proyecto adoptó (`must_cards` en `.strata/kit/registry.yaml`, escrito por el asistente), y la guía generada (AGENTS.md) recoge ese conjunto. La redacción canónica de cada regla es la tarjeta en `core/cards/`.
> Esta sección conserva el texto original del que salieron esas tarjetas y sus fundamentos (incidentes y motivos). Desde la constitución 1.2.0, las reglas 5 y 7 no son artículos sino must adoptables que solo se aplican cuando el proyecto las adopta. Para cambiar una regla se editan las tarjetas y la constitución (con un registro de decisión); esta sección no se edita.

Texto original (2026-09-30, la lista que se aplicaba a todas las sesiones en tiempos de DEC-2026-09-30-02):

1. **Presentar un resumen de lo que se hará y obtener la confirmación del usuario antes de cambiar el estado**
   - Alcance: editar archivos, inyectar archivos de sesión o relays, llamar a CLI externas, commit/despliegue/borrado, trabajos de larga duración y trabajo que afecte a costes, permisos o datos
   - El resumen incluye el propósito, el trabajo que se ejecutará, el alcance del cambio/impacto, el método de verificación y las condiciones de reversión/interrupción
   - La investigación que no cambia el estado, como las consultas simples, las búsquedas y la lectura de archivos, se permite como excepción
   - **semantic vs mechanical**: un cambio semantic que altera el significado, las reglas o los contratos requiere aprobación. Un cambio mechanical que conserva el significado (errata, enlace, formato) es candidato a permiso automático **solo cuando se puede demostrar de forma static**. Si es ambiguo, se trata como si necesitara aprobación. El propio juicio "mechanical" de un LLM no se usa como fundamento del permiso automático.
2. **Registrar de inmediato un registro de decisión cuando se toma una decisión de arquitectura** (CLI decision writer — el índice y la nota DEC del vault se regeneran automáticamente)
3. **Prohibido violar las capas** — con qué fuerza lo bloquea el arnés lo fija el grado de aplicación del proyecto (DEC-2026-10-29-17). Sea cual sea el grado, el agente no escribe violaciones nuevas
4. **Seguir las convenciones de nombres** — un hook avisa
5. **Usar solo Soft Delete** — adoptable (constitución 1.2.0, DEC-2026-10-29-14): se aplica cuando lo adopta un proyecto con almacén de datos
6. **El estado de la sesión, el trabajo en curso y los traspasos se guardan en archivos, no en el contexto de la conversación** — se aplica a las sesiones que cambian el estado; una sesión de solo lectura no tiene estado que guardar (DEC-2026-10-29-15) — cuando una sesión se interrumpe, se registra el estado actual en el `.strata/local/active/{session}.yaml` de esta sesión (el archivo único `active-task.yaml` es la forma anterior, que solo se lee cuando no hay archivo por sesión), y los traspasos y el historial de trabajo se guardan en el vault
7. **Crear un árbol de trabajo (git worktree) solo con el consentimiento del usuario** (DEC-2026-09-17-01) — adoptable (constitución 1.2.0): se aplica cuando está en la lista de adopción por defecto del usuario o el proyecto lo adopta
   - Vale también en modo automático. Quedan cubiertos tanto el aislamiento por árbol de trabajo del adaptador de la herramienta (por ejemplo, la herramienta Agent de Claude Code con `isolation: "worktree"` y `EnterWorktree`) como `git worktree add`
   - Por defecto se trabaja de forma secuencial en una sola rama del checkout que ve el usuario. Aunque haya varios Workers, se ejecutan por orden en el mismo checkout
   - Solo cuando un árbol de trabajo sea realmente necesario para sesiones o Workers en paralelo, se propone la necesidad, el nombre de la rama y el plan de limpieza como un solo elemento, y se crea únicamente si se acepta. Una aceptación vale solo para esa propuesta
   - Un árbol de trabajo creado con consentimiento se limpia al terminar la tarea, dejando la rama, y se informa de la ubicación y de la rama
   - Motivo: dividir el trabajo en árboles de trabajo impide que la revisión y la inspección de lo que escribió el agente funcionen bien, el usuario no puede comprobar directamente los cambios y el historial de trabajo, y se complica el seguimiento de la forma del código
8. **Un despliegue hecho para confirmar una suposición se limita a los entornos que solo un despliegue puede reproducir** (DEC-2026-09-18-01, strata)
   - No se usa un despliegue para confirmar una suposición que se puede confirmar leyendo el código, con los logs, con pruebas unitarias o con una ejecución local. Subir algo a un entorno compartido (dev, stage) solo sirve para confirmar un fenómeno que se reproduce únicamente en ese entorno (infraestructura, enrutamiento, integración con otros servicios, datos reales)
   - Antes de un despliegue, se informa de qué se quiere confirmar, separando los hechos confirmados de las suposiciones, e incluyendo cómo revertir (un commit de revert, la imagen anterior)
   - Un cambio que afecta a otra línea o a otros usuarios, como la autenticación, el enrutamiento o las sesiones, solo se sube después de medirlo con los flujos de usuario de esa línea (por ejemplo, tanto el inicio de sesión 2.0 como el 3.0)
   - Motivo: el 2026-09-18, en stage, se promovió una ruta del gateway solo por una suposición y se rompió el inicio de sesión 2.0, y los despliegues que corregían la suposición y volvían a subir se repitieron varias veces en un día. Un despliegue también tarda en revertirse y bloquea el trabajo de otras personas
9. **Escribir tanto el blocker como la condición unblocked_by para un elemento pendiente (pending) de un traspaso**
   - Está prohibido escribir solo "en espera". Si la sesión siguiente no sabe qué se está esperando, el elemento pendiente solo se arrastra
