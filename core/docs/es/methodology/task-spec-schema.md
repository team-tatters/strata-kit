# Esquema de especificación de tareas (Task Specification Schema)

> Canónico: strata-kit `core/docs/es/methodology/task-spec-schema.md` (migrado el 2026-10-29 desde strata `docs/04-agents/task-spec-schema.md`, DEC-2026-10-29-11).

> Define la estructura de la especificación de tarea que el Builder produce y el Worker consume.
> Una especificación de tarea es **autocontenida**: el Worker debe poder terminar el código solo con la especificación.

## Ubicación de almacenamiento

```
$STRATA_VAULT/projects/{project-name}/tasks/
  {yyyy.mm.dd}/
    {nn}-{short-kebab-title}/      # carpeta de Work Order
      _order.yaml                   # orden de trabajo (la crea el Builder)
      task-{nn}-{title}.yaml        # especificación de ejecución del Worker
```

### Por qué esta ubicación

- `$STRATA_VAULT`: no afecta al repositorio del proyecto (repositorio aparte)
- `tasks/`: separado de los documentos KB (knowledge-base/), no es objetivo del índice de búsqueda
- `{yyyy.mm.dd}/`: seguimiento según el paso del tiempo, carga cognitiva mínima
- `{nn}-{title}/`: distingue varias órdenes de trabajo del mismo día por secuencia más título

### Reglas de nomenclatura

| Elemento | Formato | Ejemplo |
| ------------- | ------------------------------ | ------------------------------- |
| Carpeta de fecha | `yyyy.mm.dd` | `2026.04.23` |
| Carpeta de Work Order | `{nn}-{kebab-title}` | `01-debounce-mongo-sync` |
| Orden de trabajo | `_order.yaml` | Siempre fijo (guion bajo = queda al principio) |
| Archivo de tarea | `task-{nn}-{kebab-title}.yaml` | `task-01-redis-dirty-mark.yaml` |

### Reglas del número de secuencia

- Número de entradas existentes en esa carpeta de fecha + 1
- Los números pueden colisionar si varias máquinas trabajan a la vez → **el title es el identificador real**
- Una colisión de números solo afecta al orden, sin problema funcional

---

## _order.yaml — orden de trabajo

El manifiesto que el Builder crea tras dividir las tareas.

### Campos obligatorios

```yaml
order:
  id: "2026.04.23-01"                # {fecha}-{secuencia}
  title: "Optimización de la sincronización con MongoDB mediante Redis Debounce"
  date: "2026-04-23"
  mode: "task"                        # task | verbal (escalated)
  project: "shop-api"

  goal: |
    Describe el propósito y el contexto del trabajo.
    Por qué hace falta este trabajo y en qué estado debe quedar al terminar.

  context:
    prior_session: "session-2026-04-22-01"    # referencia al traspaso anterior
    prior_decisions:                           # decisiones existentes que afectan a este trabajo
      - "PostProcessJob usa polling (@Scheduled fixedDelay=5000)"
    blocker_resolved: "Sistema PostProcessJob implementado (4/21)"
    kb_references:                             # documentos KB relacionados
      - "$STRATA_VAULT/projects/shop-api/knowledge-base/03-orders/checkout.md"

  tasks:
    - id: "task-01"
      title: "Añadir operaciones SET a CacheGenericOperator"
      model_tier: "standard"
      layer: "L2_DataLayer"
      depends_on: []

    - id: "task-02"
      title: "Implementar DirtyMarkService"
      model_tier: "standard"
      layer: "L3_Composite"
      depends_on: ["task-01"]

    - id: "task-03"
      title: "Pasar DataUpsertListener a debounce"
      model_tier: "deep"
      layer: "L3_Composite"
      depends_on: ["task-01", "task-02"]

  acceptance:
    - "Completado el cambio del flujo de procesamiento inmediato existente al flujo dirty mark"
    - "Todas las pruebas unitarias pasan"
    - "0 violaciones de capa"

  status: "open"                       # drafting | open | in_progress | completed | cancelled
  completed_tasks: []                  # lista de ids de tareas completadas
```

### Campos opcionales

```yaml
  escalated_from: "verbal"             # al convertir verbal → task
  completed_before_spec:               # elementos completados de forma verbal antes de la conversión
    - "Añadir operaciones SET a CacheGenericOperator"
  
  estimated_sessions: 1                # número de sesiones previsto
  priority: "high"                     # high | medium | low
  deadline: "2026-04-25"              # fecha absoluta

  verification_tier: "self_verified"  # solo | self_verified | cross_verified (valores enum)
                                      #   Si se omite, verbal = solo. En Task Mode se recomienda indicarlo explícitamente.
                                      #   Detalles: core/docs/es/methodology/verification-tier.md
  entry_point: "change"               # design_first | dev_first | spec_first | change — punto de entrada de los entregables (Spec, Design, Impl).
                                      #   No fija el orden. La comprobación de coherencia es la puerta. Detalles: core/docs/es/architecture/frontend-design-contract.md
  design_verified: "self"             # none | self | designer | cross — independencia de la verificación de coherencia del diseño (core/docs/es/methodology/verification-tier.md).
                                      #   none si no es trabajo de UI.
  methodology_feedback:               # bucle de retroalimentación de metodología (opcional)
    enabled: true
    backlog_ref: "$STRATA_VAULT/projects/{name}/backlog/methodology-backlog.yaml"
```

> **Sin embargo, en el trabajo que cambia la fuente de verdad del Core** (layer-rules / naming-convention / task-spec-schema / agent-roles)
> `verification_tier: cross_verified` es **obligatorio** (`core/docs/es/methodology/verification-tier.md`).
> Solo en este caso verification_tier se trata como campo obligatorio y no como opcional.

### Ciclo de vida de status

```
drafting → open → in_progress → completed
                              → cancelled
```

| Estado | Significado | Condición de transición |
|------|------|----------|
| `drafting` | El Builder está dividiendo las tareas | El Builder empieza a escribir _order.yaml |
| `open` | Orden de trabajo confirmada, el Worker puede ejecutar | Todas las especificaciones de tarea están escritas |
| `in_progress` | Algunas tareas se están ejecutando | Empieza la primera ejecución de un Worker |
| `completed` | Todas las tareas completas | Se cumplen todos los acceptance |
| `cancelled` | Cancelada | Decisión explícita de cancelar |

Una orden de trabajo en estado `drafting` la completa el Builder en la siguiente sesión o la descarta.

---

## _order.md — nuevo formato de la orden de trabajo (2026-08-19, DEC-2026-08-19-03)

Las órdenes nuevas se escriben como `_order.md`: el **frontmatter YAML es la orden en sí** (el esquema es idéntico al de `_order.yaml` de arriba),
y el cuerpo es markdown mínimo para incorporar la orden al grafo de enlaces de Obsidian.

```markdown
---
order:
  id: "2026.08.20-01"
  # ... (esquema de _order.yaml tal cual)
---

# {order title}

- Design: [[design-doc]]
- Decisions: [[DEC-YYYY-MM-DD-NN]]
```

- Solo el frontmatter lo analiza una máquina: los scripts que consumen órdenes admiten tanto `_order.yaml` como `_order.md` (frontmatter).
- El cuerpo debe conservar los `[[wikilink]]` al documento de diseño y a los DEC relacionados (aristas de la espina (enlaces del traspaso: orders, kb_updates, decisions_made): session→order→design+DEC).
- Los `_order.yaml` existentes no se convierten con carácter retroactivo. `task-{nn}.yaml` sigue en yaml (la nota de la orden se encarga de entrar en el grafo).

---

## task-{nn}.yaml — especificación de ejecución del Worker

El documento de tarea autocontenido que recibe el Worker.

### Esquema completo

```yaml
task:
  id: "2026.04.23-01/task-01"          # {order-id}/{task-id}
  title: "Añadir operaciones SET a CacheGenericOperator"
  order_ref: "_order.yaml"             # referencia a la orden de trabajo superior

execution:
  model_tier: "standard"               # deep | standard | light (el adaptador de la herramienta asigna los nombres de modelo)
  model_reason: "Sigue el patrón existente de CacheGenericOperator"
  estimated_turns: 8
  estimated_files: 2

scope:
  layer: "L2_DataLayer"
  module: "domain:common-cache"
  nodes: ["common.cache"]                         # nodos temáticos a los que pertenece esta tarea: el resolvedor de cobertura los deriva de directories
  can_reference: ["L1_Component"]
  cannot_reference: ["L3_Composite", "Route_Controller"]
  constraints:                                    # restricciones de dominio extraídas de ADR
    - id: "CC-NNN-NN"
      rule: "{regla de una línea de la restricción que se aplica a este scope}"
  docs_to_update:                                 # especificaciones que poseen directories·module mediante covers: las inyecta el resolvedor de cobertura
    - node: "common.cache"
      doc: "[[kb-shop-api-common-cache-spec]]"
      reason: "covers.paths coincide: añadir operaciones SET cambia la lista de operaciones de la especificación"
  directories:
    - "domain/common-cache/src/main/kotlin/com/example/domain/common_cache/components/"

inputs:
  reference_files:
    - path: "domain/common-cache/.../CacheGenericOperator.kt"
      reason: "Referencia del patrón existente: cómo se usa ReactiveRedisOperations"
    - path: "docs/architecture/layer-rules.yaml#L2_DataLayer"
      reason: "Comprobar las reglas de capa"

  requirements: |
    Especificación detallada de lo que hay que implementar.
    - Firmas de los métodos
    - Descripción del comportamiento
    - Restricciones

  conventions: |
    Resumen de las convenciones a aplicar (para que el Worker no tenga que leer archivos aparte).
    - Marcadores PAL obligatorios (@pal-port, @pal-layer, @pal-domain, @Comment)
    - Nomenclatura: {Domain}{ServiceType}

  design_ref:                          # Obligatorio en una tarea que construye UI. Puntero al entregable de diseño (core/docs/es/architecture/frontend-design-contract.md)
    kind: "figma"                      # figma | storybook | claude_design | none
    ref: "file/abc?node-id=12:34"      # archivo, nodo, id de story o URL del lienzo
    version: "2026-04-23"              # versión de la herramienta o fecha de la instantánea: punto de referencia de la comprobación de coherencia
    reason: null                       # obligatorio si kind: none (p. ej. "pantalla de administración solo de texto")

deliverables:
  files:
    - path: "domain/common-cache/.../CacheGenericOperator.kt"
      action: "modify"                  # create | modify | create_or_modify
      description: "Añadir 4 métodos de operaciones SET"
    - path: "domain/common-cache/.../CacheGenericOperatorTest.kt"
      action: "create_or_modify"
      description: "Pruebas unitarias de las operaciones SET"

acceptance_criteria:
  - "Implementados addToSet, popFromSet, getSetSize, getSetMembers"
  - "Sin cambios en las firmas de los métodos existentes"
  - "Las pruebas unitarias pasan"
  - "Sin violaciones de capa"

context_budget:
  max_reference_files: 5
  max_loaded_tokens: 20000
  compaction_strategy: "file-based"

status: "pending"                       # pending | in_progress | completed | blocked
completion: null                        # lo rellena el Worker al completar (véase abajo)
```

**`scope.nodes` y `scope.docs_to_update`**: el Builder inyecta las especificaciones que poseen la superficie de código que cambia la tarea (frontmatter `covers`) y los nodos temáticos de esas especificaciones. El principio es el mismo que el de `scope.constraints`. El Worker no ejecuta el resolvedor; solo lee los valores inyectados.
- Para una superficie sin especificación propietaria (una funcionalidad nueva), hay que incluir la creación de la especificación en `deliverables.files`, o escribir `docs_to_update: []` e indicar en `inputs.requirements` el motivo del vacío intencionado. Un array vacío sin motivo provoca una advertencia de validación.
- La fuente de verdad del formato de los valores es la sección «Campos de nodo y de cobertura» de core/docs/es/knowledge-base/document-format.md.

### Sección completion (la rellena el Worker, salvo `triage.review_gate`)

El Worker rellena `completion.self_report` y la lista de entregables, pero **`triage.review_gate` lo rellena
el reevaluador independiente (reviewer/relay)**: la premisa de la puerta de verificación del autoinforme (agente ≠ reevaluador,
`core/docs/es/methodology/agent-operations.md` §4) implica que, si lo rellena el propio Worker, la puerta queda neutralizada.

```yaml
completion:
  status: "completed"                   # completed | blocked | partial
  completed_at: "2026-04-23T14:30:00+09:00"
  files_created:
    - "domain/common-cache/.../CacheGenericOperatorTest.kt"
  files_modified:
    - "domain/common-cache/.../CacheGenericOperator.kt"
  tests:
    total: 4
    passed: 4
    failed: 0
  layer_violations: 0
  naming_violations: 0
  constraint_compliance:                # resultado de cumplimiento de cada elemento de scope.constraints
    - id: "CC-NNN-NN"
      met: true
      note: "{base del cumplimiento o algo inusual}"
  design_sync: "aligned"                # aligned | stale | waived | none — coherencia Impl↔Design (obligatorio si existe inputs.design_ref)
  design_sync_reason: ""                # obligatorio si waived: motivo + until YYYY-MM-DD. Si es stale, no se puede declarar la finalización
  doc_change: "updated"                 # updated | none — resultado de tratar scope.docs_to_update (misma clave que el frontmatter de sesión)
  doc_change_reason: ""                 # obligatorio si none (p. ej. "solo refactorización: sin cambio de contrato externo ni de política")
  docs_updated:                         # si updated, los documentos actualizados (añadir esta tarea al sello updated y a sources)
    - "[[kb-shop-api-common-cache-spec]]"
  notes: "Nada inusual"
  methodology_signals:                  # opcional — señales de mejora de la metodología (una lista; [] u omitida si no hay)
    - type: "incomplete_spec"           # incomplete_spec | scope_issue | constraint_conflict | rule_gap | drift | design_drift
                                        #   design_drift: se halló un valor fuera del alias o una discrepancia de contrato (eje, estado) → candidato para mejorar el contrato de tokens/diseño
      severity: "minor"                 # minor | major | blocking
      scope: "methodology"              # project | methodology
      affected_core:                    # al menos 1 obligatorio si scope: methodology
        - "core/docs/es/methodology/task-spec-schema.md"
      summary: "La especificación de tarea no tiene un campo de comando de prueba, por lo que el criterio de verificación de la finalización era inestable"
  triage:                               # opcional — clasificación de la salida de Agent Operations (para el Decision Inbox)
    self_report:
      status: "completed"               # completed | blocked | needs_decision | rejected
      risk: "low"                       # high | medium | low | unknown
      decisions_needed: []
    review_gate:                        # puerta de verificación del autoinforme (cuando se exige reevaluación)
      required: true
      reviewer: "cross_verified"
      result: "agreed"                  # agreed | reclassified | no_reviewer
      final_status: "completed"         # status confirmado tras la reevaluación
      max_review_rounds: 1
```

`methodology_signals` es el canal por el que el Worker informa de **lagunas de la propia metodología** halladas durante el trabajo.
Pueden aparecer varias lagunas (p. ej. incomplete_spec + rule_gap) a la vez en un mismo completion, por lo que es una **lista**.
El Builder clasifica cada elemento por separado.
A diferencia de un `scope_issue` corriente (un bloqueo de la tarea actual), señala candidatos de mejora de reglas, esquema o convenciones.
En el traspaso, el Builder los carga en el backlog y juzga la promoción
(→ véase abajo la sección «Promotion Gate»).

`triage` es la clasificación que se aplica antes de que la salida vaya al Decision Inbox que ven las personas. El agente rellena `self_report`,
y la verificación cruzada reevalúa esa etiqueta mediante `review_gate` (porque no se puede confiar en un autoinforme). Para las reglas, la ramificación según el riesgo y el recurso
cuando no hay reevaluador, véase → `core/docs/es/methodology/agent-operations.md` «Decision Inbox + puerta de verificación del autoinforme».

---

## methodology-backlog.yaml — acumulación de candidatos de mejora

Un archivo aparte que acumula candidatos de mejora de la metodología. Se mantiene separado de decisions.yaml (el registro de decisiones):
el backlog contiene *candidatos* y tiene otro ciclo de vida (revisión → adopción/rechazo).
Esta sección es la fuente de verdad del **esquema de campos y del enum de ciclo de vida** del backlog.
El flujo de señales y el Promotion Gate también los define esta sección (véase abajo la sección «Promotion Gate», DEC-2026-10-29-12).

```
project backlog:  $STRATA_VAULT/projects/{name}/backlog/methodology-backlog.yaml  # vault (Tier V)
core backlog:     $STRATA_VAULT/projects/strata-kit/backlog/methodology-backlog.yaml  # candidatos de mejora de Strata Core
```

```yaml
methodology_backlog:
  - id: "MB-shop-api-2026-001"   # el prefijo {project} evita colisiones en la promoción central
    scope: "methodology"              # project | methodology
    source:
      project: "shop-api"
      type: "worker_rejection"        # worker_rejection | reviewer_finding | repeated_warning
      ref: "tasks/2026.05.31/01-sync/task-02.yaml"
    signal: "incomplete_spec"
    severity: "major"
    affected_core:                    # al menos 1 obligatorio si scope: methodology
      - "core/docs/es/methodology/task-spec-schema.md"
      - "core/roles/agent-roles.yaml"
    summary: "El Worker juzgó imposible verificar la finalización porque faltaba el comando de prueba"
    proposed_action: "Añadir un campo verification.commands al esquema de tarea"
    status: "open"                    # open → triaged → accepted | rejected → applied
    promoted_to: null                 # al promover, "$STRATA_VAULT/projects/strata-kit/backlog/methodology-backlog.yaml#<id>"
```

### Ciclo de vida

```
open → triaged → accepted → applied
              → rejected
```

| Estado | Significado |
|------|------|
| `open` | Señal cargada, aún sin revisar |
| `triaged` | El Builder ha comprobado scope, duplicados y affected_core |
| `accepted` | Adoptado como objetivo de mejora del Core (promovido) |
| `rejected` | Se juzgó que no necesita mejora (motivo registrado) |
| `applied` | Aplicado a Strata Core, plantillas/adaptadores regenerados |

---

### Promotion Gate

Los elementos del backlog toman un camino de tratamiento distinto según `scope`.

- `scope: project` — se tratan como candidatos de mejora de las reglas, el layer-map, AGENTS.md, el KB y las decisiones de ese proyecto.
- `scope: methodology` — se promueven al backlog del core (`$STRATA_VAULT/projects/strata-kit/backlog/methodology-backlog.yaml`).

Para los elementos con `scope: methodology`, el Builder hace lo siguiente.

1. Comprueba si está duplicado.
2. Comprueba que `affected_core` tenga al menos 1 elemento.
3. Añade un elemento de promoción al backlog del core.
4. Registra `promoted_to` en el elemento del proyecto de origen.
5. Hasta que se refleje en el kit, deja el status en `triaged` o `accepted`. Una vez reflejado, anota `applied` y `applied_in` (commit·DEC).

El dictamen (`accepted`·`rejected`) lo da la persona. El antiguo backlog central de strata (`strata/methodology-backlog.yaml`) se trasladó al backlog del kit (DEC-2026-10-29-12).

## Lista de comprobación de autocontención

La revisa el Builder tras escribir una especificación de tarea, antes de entregarla al Worker:

```
□ ¿scope.layer es una sola capa?
□ ¿scope.can_reference coincide con layer-rules.yaml?
□ ¿scope.constraints incluye las restricciones aplicables a ese dominio/capa?
□ ¿Existe scope.nodes, y scope.docs_to_update coincide con el resultado del resolvedor de cobertura?
  (Si no hay especificación propietaria, ¿se crea una en deliverables o hay un motivo de vacío intencionado?)
□ ¿inputs.reference_files enumera todos los archivos que necesita el Worker?
□ ¿Se entiende inputs.requirements sin explicación verbal?
□ ¿inputs.conventions resume las convenciones de esa capa?
□ ¿deliverables.files enumera todos los archivos que hay que crear/modificar?
□ ¿acceptance_criteria tiene una forma verificable? (pruebas que pasan, 0 violaciones, etc.)
□ ¿acceptance_criteria incluye la verificación del cumplimiento de las restricciones?
□ ¿acceptance_criteria incluye el tratamiento de docs_to_update (actualización de la especificación, o doc_change: none + motivo)?
□ ¿context_budget.max_reference_files ≤ 5?
```

**Si falta aunque sea un elemento, no se entrega al Worker.**

La revisa el Worker al recibir una tarea:

```
□ ¿Está indicado scope.layer?
□ Si scope.docs_to_update está vacío, ¿está indicado el motivo del vacío intencionado?
□ ¿Existen realmente los archivos de inputs.reference_files?
□ ¿inputs.requirements no está vacío?
□ ¿deliverables.files no está vacío?
□ ¿Hay al menos 1 acceptance_criteria?
```

**Si encuentra un elemento sin cumplir, lo devuelve de inmediato al Builder (informa de un scope_issue).**

---

## Política de limpieza de tareas

| Momento | Acción |
|------|------|
| Tarea completa | `status: completed` + rellenar la sección completion |
| Orden de trabajo completa | `status: completed` en `_order.yaml` |
| Fin del sprint | Se conservan las carpetas de fecha completadas (no se borran) |
| Pasados 90 días | Las carpetas de órdenes de trabajo completadas pueden archivarse |

Las decisiones clave de una tarea completada ya han pasado al traspaso y a la KB,
así que el archivo de la tarea se conserva solo como **pista de auditoría (audit trail)**.
