# Knowledge Base — Formato de documento

> Canónico: strata-kit `core/docs/es/knowledge-base/document-format.md` (migrado el 2026-10-29 desde strata `docs/07-knowledge-base/document-format.md`, DEC-2026-10-29-11).

## Resumen

Todo archivo `.md` del vault debe incluir frontmatter YAML.
Se usa un formato que puedan analizar tanto Obsidian como el servidor MCP (Phase 3).

## Esquema del frontmatter

```yaml
---
# === Campos obligatorios ===
title: "Título del documento"
id: "{prefijo}-{project}-{slug}"  # ID estable — no cambia al mover ni renombrar (esquema de prefijos: sección de ID estable de core/docs/es/knowledge-base/vault-structure.md)
type: overview | decision | session | pattern | reference | glossary
      | concept | specification | flow | guide | runbook | constraint | epic | moc | node
created: YYYY-MM-DD

# === Obligatorios según condición ===
project: {project-name}       # Para documentos de un proyecto concreto (en los documentos transversales, vault en el lugar de project del id)
status: draft | active | review-needed | superseded | archived
sources: ["[[sesión/tarea de origen]]"]  # Obligatorio al actualizar un documento de la capa Knowledge (KB, pattern) — enlace al Archive que lo respalda (DEC-2026-08-19-03)
nodes: ["{node-id}"]          # Pertenencia a un nodo temático — obligatorio en decision, session, specification, concept, constraint (sección "Campos de nodo y cobertura")

# === Campos opcionales ===
tags: [namespace/value, ...]  # Se recomiendan etiquetas con espacio de nombres
updated: YYYY-MM-DD           # Fecha de la última modificación
updated_by: {git user}@{machine}  # Último actualizador — el hook de escritura lo estampa con la identidad de git y el alias de la máquina (DEC-2026-09-09-05)
page_order: 1                 # Orden del documento dentro de la categoría (para el índice del KB)
author: builder | worker | manual  # Quién lo escribió
machine: {alias}              # Máquina que lo escribió: el alias de esta máquina (STRATA_ENV) en env-config.yaml — vault-git rechaza un registro de sesión que nombre otra máquina
superseded_by: "[[documento nuevo]]"   # Cuando status es superseded (lado reemplazado → lado que reemplaza)
supersedes: ["[[decisión anterior]]"]   # decision — las decisiones anteriores que esta reemplaza (sentido contrario a superseded_by)
covers: {paths, symbols, endpoints, tables}  # specification, concept — la superficie de código de la que este documento es canónico
doc_change: none              # session, task — declara que se cambió el código pero no se actualizó la forma construida (doc_change_reason obligatorio)
aliases: ["nombre de archivo anterior"]         # Conserva el identificador original al mover o renombrar
related: ["[[documento relacionado 1]]"]     # Wikilink de Obsidian — relación de mención (la relación de propiedad es covers)
---
```

## Campos obligatorios por type

| type | Campos obligatorios adicionales | Descripción |
|---|---|---|
| `overview` | `project` | Resumen de un proyecto o de una categoría |
| `decision` | `project`, `status`, `nodes` | ADR. Incluye el contexto y la justificación de la decisión. `supersedes` opcional |
| `session` | `project`, `machine`, `nodes` | Traspaso de sesión / ledger. **Solo se indexan los metadatos y la parte de resumen** (Archive — 2026.08.19-06). `doc_change` opcional |
| `pattern` | — | Patrón reutilizable transversal a los proyectos |
| `reference` | — | Referencia resumida de un documento externo, estándar o especificación |
| `glossary` | — | Definiciones de términos del dominio o técnicos |
| `concept` | `nodes` | Concepto de dominio, regla de negocio o explicación de un principio. `covers` opcional |
| `specification` | `status`, `nodes` | Especificación funcional, requisitos, restricciones, criterios de aceptación. La forma final de un nodo. `covers` recomendado |
| `flow` | — | Proceso de negocio, flujo de datos, secuencia |
| `guide` | — | Guía de procedimiento, documento How-to |
| `runbook` | `status` | Procedimiento de operación / respuesta a incidentes |
| `constraint` | `source_adr`, `severity`, `scope`, `rule`, `verification`, `status`, `nodes` | Una única restricción ejecutable extraída de un ADR |
| `epic` | `constraints`, `domains`, `layers`, `personas`, `status` | Unidad funcional del PRD. El enlace a constraint es obligatorio |
| `planning` | `project`, `status`, `nodes`, `source`, `implementation` | Texto original de planificación importado de una herramienta externa (PRD, política, Epic/Story). El texto original es inmutable, más una sección `## Revisión de implementación`. `implementation.status` clasifica el resultado de la revisión. status es el estado de la planificación (lifecycle_override) |
| `moc` | — | Tabla de contenidos (Map of Content). `_index/`, cada `_index.md` e índices estáticos generados. **Solo generado** |
| `node` | `project`, `node` | Página de nodo temático. Une la forma final, las políticas, las decisiones, la planificación, el historial de trabajo y la deuda. **Solo generado** |

`moc` y `node` pertenecen a la capa Index. No se escriben a mano; se regeneran a partir de las fuentes canónicas (frontmatter, registros, toc.yaml).

## Campos de nodo y cobertura

Un nodo temático (node) es la unidad del índice que leen las personas. Un nodo es la clave que reúne en una sola pantalla la forma final (especificación), las políticas (restricciones), las decisiones y el historial de trabajo. La fuente canónica del árbol de nodos es el `_meta/toc.yaml` del proyecto, y un documento se enlaza a los nodos y al código con los cuatro campos siguientes. **Esta sección es la fuente canónica de los formatos de valor.** La taxonomy solo decide si un campo es obligatorio.

### `nodes` — los nodos temáticos a los que pertenece este documento

```yaml
nodes: ["orders.checkout-v2.coupon"]   # ids de nodo definidos en toc.yaml; se permiten varios
```

- Un id de nodo vive en un **espacio de nombres distinto** del id del documento (`{prefijo}-{project}-{slug}`). Es una ruta unida por puntos (.) desde el ancestro hacia abajo, y cada segmento es kebab-case.
- Obligatorio en decision, session, specification, concept y constraint. Las especificaciones de tarea usan el mismo campo (véase `core/docs/es/methodology/task-spec-schema.md`).
- Los nodos de sesiones y tareas los deriva el resolvedor de cobertura (archivo cambiado → la especificación que posee ese archivo → el nodo de esa especificación). Una persona los elige solo en las sesiones sin cambios de código.
- Se permite un array vacío, pero la validación avisa. Si no tener nodo es intencionado, se deja el motivo en el cuerpo.

### `covers` — la superficie de código de la que este documento es canónico

```yaml
covers:
  paths: ["service/order-api/src/main/kotlin/com/example/order/refund/"]   # ruta relativa al repositorio, coincidencia por subcadena
  symbols: ["RefundCalculationService"]                              # nombre de clase o función
  endpoints: ["POST /v1/orders/{id}/refunds"]                    # METHOD + prefijo de ruta
  tables: ["refund_items"]                                      # nombre de tabla
```

- Se usa solo en specification y concept. Las sesiones, decisiones y restricciones no tienen `covers`. Solo apuntan a un nodo mediante `nodes`.
- No se usan rutas a nivel de archivo. Se usan solo identificadores estables ante movimientos, como el prefijo de un módulo, paquete, controlador o ruta. La regla de coincidencia es la misma que la de las rutas del layer-map (subcadena, de arriba abajo).
- Una superficie la posee exactamente un documento. Si se solapan, la validación avisa. Un documento de concepto de nivel superior se enlaza con `up`.
- `covers` es una relación de **propiedad**, no una mención. Las menciones van en `related`. Si esta distinción se desdibuja, cinco documentos acabarán poseyendo un mismo archivo y la puerta de cobertura (gate) se volverá ruido y se ignorará.
- Un puntero a una ruta de código no entra en conflicto con el principio de no guardar código fuente en el vault. Solo se registran rutas relativas al repositorio, no código (`core/docs/es/knowledge-base/vault-structure.md`, "Lo que nunca se incluye").

### `doc_change` — cuando se cambió el código pero no se actualizó la forma construida

```yaml
doc_change: none
doc_change_reason: "Solo refactorización — sin cambios en contratos externos ni políticas"
```

- Se usa en session y task. Si cambió una ruta de `covers`, no se actualizó el documento que posee esa superficie y falta este campo, la puerta (gate) de fin de sesión lo registra como **deuda** de ese nodo y avisa.
- Un valor vacío está prohibido. Si es `none`, hay que adjuntar un motivo. Es el mismo principio por el que el ledger exige un motivo para `next: "none"`.

### `supersedes` — las decisiones anteriores que reemplaza esta decisión

```yaml
supersedes: ["[[DEC-2026-08-13-05]]"]
```

- Se usa en decision. **El estado del lado reemplazado no se almacena, se deriva** (DEC-2026-09-30-03): una decisión que aparece en el `supersedes` de algún registro obtiene automáticamente `status: superseded` y `superseded_by` en el índice y en la nota DEC. El archivo de registro del lado reemplazado no se edita.
- Para añadir más tarde una relación de reemplazo a una decisión ya registrada, se usa `python3 "$STRATA_KIT/kb" decision supersede --id nueva --target antigua`; para retirar una decisión sin una decisión que la reemplace, se usa `python3 "$STRATA_KIT/kb" decision withdraw --id X --reason ...`. Escribir solo "reemplazada" o "retirada" en el cuerpo no se reconoce como un estado.
- Los documentos del KB (distintos de decision) siguen llevando `status: superseded` y `superseded_by` escritos a mano en el lado reemplazado.
- `superseded_by` es el campo existente para el sentido contrario (lado reemplazado → lado que reemplaza). Los dos son los dos extremos del mismo hecho.
- La faceta "decisiones" de una página de nodo muestra el final de esta cadena como la decisión vigente y el resto como historial.

## Ciclo de vida del documento

```
draft → active → review-needed → superseded → archived
                      ↓                ↓
                   active           archived
```

| Estado | Significado | Transiciones posibles |
|------|------|-----------|
| `draft` | En redacción, sin revisar | active, archived |
| `active` | Documento vigente y válido | review-needed, superseded, archived |
| `review-needed` | Necesita actualización (se marca automáticamente tras 90 días) | active, superseded, archived |
| `superseded` | Reemplazado por un documento nuevo. El campo `superseded_by` es obligatorio. Si la decisión que lo reemplaza declara `supersedes`, el par queda sujeto a validación de simetría | archived |
| `archived` | Ya no es válido. Se reduce su peso en la búsqueda | — |

**Excepción por type**: `constraint` usa su propio ciclo de vida —
`active → superseded → retired` (taxonomy.yaml `lifecycle_override`).
Una restricción se crea como active en el momento en que se acepta su ADR, sin estado draft, y su baja se marca como `retired`.

## Reglas del cuerpo

### Reglas generales

- Formato Markdown (CommonMark + extensiones de Obsidian)
- Los títulos empiezan en `##` (se evita `#` para no duplicar el title del frontmatter)
- Un documento se centra en un solo tema (principio MECE)
- Longitud máxima: resumen/patrón/concepto 500 líneas, ADR 200 líneas, resumen de sesión 100 líneas, especificación 1000 líneas, índices y páginas de nodo 300 líneas
- La fuente canónica de los títulos de las secciones del cuerpo es `document_types.{type}.body_sections` de la taxonomy. Los bloques de estructura de abajo son una representación de ella, y el generador construye los títulos a partir de la taxonomy

### Reglas de legibilidad (obligatorias)

- **Términos autocontenidos**: un documento debe poder entenderse leyendo solo ese documento. No se usan tal cual términos cuyo significado no se entiende sin contexto técnico externo — jerga técnica en inglés, conceptos internos de la implementación o palabras compuestas inventadas por quien escribe. Si de verdad hacen falta, se **explican en una línea la primera vez que aparecen**. (Ejemplo: en lugar de palabras como "materialize", "resolve", "single-flight", "degraded", **se describe la acción**, por ejemplo "se construye de antemano en la primera petición" o "se consulta y se ensambla".)
- **Coherencia entre el cuerpo y el cierre**: los elementos de "pendiente / por confirmar / respuestas a solicitudes" del final del documento se extraen solo de lo que el cuerpo definió y desarrolló realmente. No se introduce por primera vez un concepto nuevo en la sección de cierre. El lector debe poder encontrar, uno a uno, con qué parte del cuerpo se conecta cada elemento pendiente.
- **Criterio de decisión**: "¿Puede un compañero del mismo equipo que ve este documento por primera vez entender, sin buscar fuera, todos los términos y todos los elementos pendientes solo con el cuerpo?" Si no, se redacta con más detalle o se añade el fundamento al cuerpo.

### Reglas para documentos leídos por personas (obligatorias — DEC-2026-09-10-01)

El lector es una persona. No se escribe en una forma cómoda de analizar para un agente. Estas reglas se aplican por igual a los documentos del KB, los traspasos de sesión, los registros de decisión y los informes por chat.

- **Usar solo ordenaciones que una persona pueda asimilar.** No se escriben párrafos ni tablas cuyo sentido no se entienda con una lectura. No se enumeran símbolos de código, rutas o IDs de decisión en lugar de una explicación. Una tabla contiene un hecho por celda, y no se pone una tabla dentro de otra.
- **Prohibido duplicar y ser prolijo; escribir en un solo contexto.** No se repite el mismo hecho en varias secciones. Se mantiene un solo hilo para que el punto de vista no cambie al cambiar de sección.
- **Primero el resumen, después los fundamentos.** Cuando la exposición se alarga, se pone al principio un resumen de la conclusión, y las ubicaciones en el código, los valores medidos y las citas van en una sección de fundamentos posterior. El lector debe poder decidir solo con el resumen.
- **No usar etiquetas de orden en forma de código.** No se clasifican tareas, orden de documentos ni elementos con códigos que combinan una letra y un número, como `A1·A2·B3`. El orden y los elementos se escriben con frases cortas cuyo significado se vea. (No "A3 poda del hub", sino "eliminar las pantallas que el hub ya no usa".) La etiqueta original se añade entre paréntesis solo al citar un documento existente que ya la lleva.

### Estructura del cuerpo de Decision (ADR)

```markdown
## 맥락
{el trasfondo que hizo necesaria la decisión}

## 결정
{la dirección elegida y el motivo}

## 대안
{direcciones consideradas pero no elegidas, y por qué}

## 결과
{los efectos de esta decisión, las contrapartidas}
```

Una decisión que declara `supersedes` deja una línea en `## Consecuencias` que dice qué reemplaza y por qué. Cuando una página de nodo muestra la cadena de decisiones, esa línea sirve de explicación.

### Estructura del cuerpo del resumen de Session

```markdown
## 완료
- {elemento completado}

## 진행 중
- {elemento sin terminar y su estado actual}

## 결정 사항
- {decisión tomada en esta sesión}

## 주의 사항
- {aviso/problema que la próxima sesión necesita saber}
```

- Las cuatro secciones anteriores son la estructura de la **parte de resumen** del traspaso. El formato de las entradas de actor del ledger y del bloque `next_session` es canónico en `core/docs/es/methodology/agent-operations.md` §5.3, y convive con esta estructura.
- Si se cambió el código pero no se actualizó la forma final, se declaran `doc_change: none` y un motivo en el frontmatter, y se escribe el mismo motivo en `## Advertencias`.

### Estructura del cuerpo de Pattern

```markdown
## 문제
{el problema que resuelve este patrón}

## 해결
{descripción del patrón}

## 적용 예시
{fragmento de código o ejemplo de estructura}

## 적용 프로젝트
- [[project-a]] — {cómo se aplicó}
```

### Estructura del cuerpo de Constraint Card

Una única restricción ejecutable extraída de un ADR. Se mantiene concisa, en un máximo de 50 líneas.

```yaml
---
title: "{título de la restricción — una línea nominal}"
type: constraint
created: YYYY-MM-DD
status: active
source_adr: "[[NNN-adr-slug|ADR-NNN]]"
severity: must-not        # must | must-not | should
scope:
  domains: [{dominio}]     # dominios de negocio a los que se aplica esta restricción
  layers: [{capa}]      # capas de Strata a las que se aplica esta restricción
rule: "{regla ejecutable de una línea — una oración con MUST/MUST NOT}"
verification: code-review  # code-review | unit-test | integration-test | static-analysis
tags: [constraint, severity/{level}, layer/{layer}, domain/{domain}]
aliases: [CC-NNN-NN]       # ID único (número del ADR-número de orden)
---
```

```markdown
## 근거
{de qué sección del ADR se derivó y por qué hace falta esta restricción, en 1-3 líneas}

## 위반 시 영향
{qué problemas aparecen si se rompe esta restricción, en 1-3 líneas}

## 검증 방법
{formas concretas de comprobarlo, como revisión de código, pruebas, análisis estático}
```

**Reglas de redacción de Constraint Card:**
- Se extraen en la misma sesión en que un ADR pasa a accepted (obligación del Builder)
- 1 ADR → N Cards (normalmente 3-10)
- La severity se decide por la redacción del texto del ADR: "debe/obligatorio/MUST" → must, "prohibido/NEVER" → must-not, "recomendado/SHOULD" → should
- scope es el alcance de dominios y capas a los que se aplica esta restricción
- Se registra a la vez un resumen de una línea en constraint-registry.yaml

### Estructura del cuerpo de Epic

Unidad funcional del PRD. Se enlaza con las restricciones de los ADR mediante el campo constraints.

```yaml
---
title: "{título de la unidad funcional}"
type: epic
project: {project-name}
created: YYYY-MM-DD
status: draft
constraints:                # ★ Obligatorio — las Constraint Cards que este Epic debe cumplir
  - "[[CC-NNN-01]]"
  - "[[CC-NNN-02]]"
domains: [{dominio}]
layers: [{capas afectadas}]
personas: [{personas destinatarias}]  # IDs de persona definidos en el proyecto
tags: [epic, domain/{domain}]
---
```

```markdown
## Objetivos
{el problema del usuario que resuelve este Epic, en 1-3 líneas}

## Criterios de aceptación
- {condición de finalización verificable}

## Resumen de restricciones
{un resumen de cómo se aplica a este Epic cada Constraint Card del campo constraints}
```

**Reglas de redacción de Epic:**
- El campo constraints es obligatorio. Un array vacío es una señal para la revisión (hay que distinguir un vacío intencionado de una omisión)
- Al dividir en tareas, el Builder reparte los constraints del Epic en el scope.constraints de cada tarea

### Estructura del cuerpo de Planning

Texto original de planificación importado de una herramienta externa de planificación (Notion y similares). La mayoría de estos documentos ya pasaron la fase de solicitud o ya reflejan decisiones, por lo que se tratan como **planificación**, no como "solicitud" (DEC-2026-09-09-01).
El texto original es as-intended, y la especificación de Knowledge es as-built. No se mezclan en un mismo documento: las secciones originales no se editan; solo se actualiza la sección `## Revisión de implementación` del final del documento.

```yaml
---
title: "{título original}"
id: plan-{project}-{id de origen}          # no cambia al reimportar
type: planning
project: {project-name}
status: realized                      # estado de la planificación — requested | planned | in-progress | realized | on-hold | archived
nodes: ["orders.payments-v2"]           # se registra tras la aprobación del Inbox (el importador solo propone candidatos)
source: "notion:{32hex}"              # identificador de origen (obligatorio)
source_name: notion-orders-intake        # subdirectorio bajo planning/
source_path: "{ruta relativa de la exportación de origen}"  # seguimiento de la edición
up: "[[plan-{project}-{id superior}]]"    # cuando hay un documento superior, como con Epic/Story
topic: "Categoría: … · Agrupación de tareas: … · Sprint: …"   # una línea de propiedades del origen — objeto de búsqueda del planificador de relleno de nodos
owner: "{nombre}"                     # opcional — dueño del plan; a él se le pregunta un juicio de plan incompleto (si no, al usuario, DEC-2026-10-31-35)
implementation:                       # ★ Obligatorio — clasificación del resultado de la revisión de implementación
  status: unreviewed                  # unreviewed | implemented | partial | diverged | not-implemented | superseded
  reviewed: YYYY-MM-DD                # se omite si es unreviewed
  spec: "[[kb-…]]"                    # el documento destilado de la forma final (si existe)
created: YYYY-MM-DD
---
```

```markdown
# {título original}
{texto original — no se edita}

## 구현 검토

| Elemento | Plan | Implementación | Diferencia | Evidencia |
|---|---|---|---|---|
| {elemento de política} | {lo que dice el plan} | {lo que hace el código} | {ninguna · distinta · no implementada} | {ruta de código · símbolo · enlace a la especificación} |
```

**Reglas de redacción de Planning:**
- `## Revisión de implementación` se escribe por elemento (oración de política, casilla de verificación, Story). El resumen de una línea del documento lo lleva `implementation.status`; si es diverged o partial, la tabla debe tener una fila de diferencia.
- Si la revisión lleva a actualizar una especificación, se añade este documento a los `sources:` de esa especificación y se apunta de vuelta con `implementation.spec`.
- `status` (estado de la planificación) e `implementation.status` (revisión de implementación) son ejes distintos. Un plan marcado como "desplegado" puede diferir del código: eso es diverged.
- La faceta "planificación" de una página de nodo une solo este type y lo muestra con insignias (sin revisar, implementado, parcialmente implementado, difiere del plan, no implementado, reemplazado). El número de unreviewed y los documentos diverged o partial se cuentan como deuda.
- Cuando el plan y el código no coinciden, no te quedes en una fila de diferencia de `## Revisión de implementación`: deja una solicitud de juicio (`python3 -m kb divergence add`; las filas de nueva comprobación de la puerta con `kb coverage-gate --divergence-inbox`). Solo una persona juzga, con uno de cuatro valores: coherente (sin divergencia), documento desfasado (poner el plan o la especificación al día con el código), plan incompleto (pedir al `owner` que complete el plan), defecto de implementación (una tarea de error). Registrar el juicio (`kb divergence judge`) pone `implementation.reviewed` en ese día, así los mismos cambios no vuelven a pedir comprobación; `implementation.status` se actualiza según el juicio (DEC-2026-10-31-35).

### Paquetes de planificación (strata.planning)

Cuando se depura una fuente de planificación externa, usa un paquete en lugar de un único documento original (DEC-2026-11-01-04·05). Una carpeta `planning/<bundle>/` que tiene una carpeta `audit/` es un paquete. Los documentos de planificación fuera de un paquete (el formato anterior) siguen siendo originales.

| Lugar | Contiene | Se inyecta · comparte |
|---|---|---|
| `source/` (o `category: source`) | la fuente original, nunca editada | no — respaldo |
| `audit/facts*.md` | lista de hechos `# \| source location \| type \| content \| role \| axes \| subtopic` | no — respaldo |
| `audit/coverage*.md` | tabla de correspondencias `# \| source location \| destination \| note` — siete destinos | no — respaldo |
| `audit/defects*.md`, `audit/isolated*.md` | defectos (`# \| kind \| content \| handling`), reglas aisladas | no — respaldo |
| `*.md` directamente en el paquete | documentos depurados: `planning_doc: prd \| tech-spec \| terms \| tree` | sí |

- Los documentos depurados no llevan código ni arquitectura (tablas, columnas, esquemas; clases, módulos, nombres de servicios; rutas de API, códigos HTTP; frameworks, bibliotecas, proveedores). Esos hechos van al destino `code` de la tabla de correspondencias.
- Las tablas se leen por posición de columna, así que los encabezados pueden estar en cualquier idioma. Los destinos se escriben en inglés (`isolated:` `defect:` `code` `background` `duplicate:#n` `out of scope:`) o en coreano (`격리:` `결함:` `코드` `배경` `중복:#n` `범위 밖:`); cualquier otro valor se lee como `<refined document> R<n>`.
- La búsqueda de conocimiento solo encuentra documentos depurados. `python3 -m kb planning check <bundle>` comprueba la tabla de correspondencias y los documentos depurados; `python3 -m kb planning boundary [--list]` imprime el límite de inyección.

## Espacios de nombres de etiquetas

Se recomienda que todas las etiquetas usen el formato `namespace/value`. Espacios de nombres definidos en taxonomy.yaml:

| Espacio de nombres | Patrón | Descripción | Restricción de valores |
|-------------|------|------|---------|
| `project` | `project/{name}` | Ámbito del proyecto | libre |
| `layer` | `layer/{name}` | Capa de la arquitectura Strata | L1, LM1, L2, LM2, L3, Route, Atomic, Molecule, Partial, Page, Layout, Foundation, Contract, DataState, Primitive_UI, Semantic_Component, Feature_Block, Route_Surface, App_Shell |
| `domain` | `domain/{domain}` | Dominio de negocio | libre |
| `tech` | `tech/{technology}` | Tecnología o framework | libre |
| `audience` | `audience/{role}` | Lector destinatario | developer, planner, devops, all |

Ejemplo: `tags: [project/my-api, layer/L2, domain/auth, tech/jwt]`

También se permiten etiquetas sin espacio de nombres, pero la compilación emite una advertencia.
Reglas de validación detalladas: `core/templates/vault/_meta/taxonomy.yaml` → `tag_namespaces`, `validation`
