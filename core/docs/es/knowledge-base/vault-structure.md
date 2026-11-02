# Knowledge Base — Estructura del vault

> Canónico: strata-kit `core/docs/es/knowledge-base/vault-structure.md` (migrado el 2026-10-29 desde strata `docs/07-knowledge-base/vault-structure.md`, DEC-2026-10-29-11).

## Visión general

El vault es una base de conocimiento compatible con Obsidian que comparten todos los proyectos.
Se gestiona como un repositorio Git independiente, separado del código de los proyectos.

## Modelo de tres capas (Archive / Knowledge / Index)

Todo el contenido del vault pertenece a una de tres capas, y cada capa tiene su propia disciplina de mantenimiento (DEC-2026-08-19-04):

| Capa | Directorio | Disciplina |
|---|---|---|
| **Archive** | `projects/*/sessions/`, `projects/*/tasks/`, `projects/*/relays/` | append-only. Write-once es **lo normal**: no hay obligación de revisar ni de enlazar. Es un almacén de evidencias, no una KB |
| **Planning** (variante de Archive) | `projects/*/planning/{source}/` | Texto original de planificación (`type: planning`) traído de una herramienta externa de planificación (Notion, etc.). **Las secciones originales son inmutables** (disciplina de Archive); solo se actualiza la sección `## 구현 검토` (revisión de implementación) al final del documento: registra en una tabla, por cada elemento de política, si está implementado, en qué difiere de lo planificado y la evidencia, y se clasifica con el `implementation.status` del frontmatter. Las políticas con sustancia se destilan en especificaciones de Knowledge, y el `sources:` de esa especificación apunta al original (DEC-2026-09-09-01) |
| **Knowledge** | `projects/*/knowledge-base/`, `patterns/`, `_index/glossary.md` | **Obligación de update-in-place**: al actualizar, `updated:` es obligatorio, y es obligatorio un enlace de procedencia al documento de Archive que lo respalda (frontmatter `sources:`) |
| **Index** | `_index/`, cada `_index.md`, las notas DEC en `projects/*/decisions/`, las páginas de nodo en `projects/*/nodes/` | **Solo generado: prohibido editar a mano.** Se regenera desde la fuente canónica (registros, frontmatter, toc.yaml) (DEC projection generator, generador de páginas de nodo; correspondencia con la implementación: `python3 -m kb --help` · `core/docs/es/kb-engine.md`) |

La promoción de conocimiento (Archive → Knowledge) la realiza una sesión de destilación y pasa por la puerta (gate) del Decision Inbox.
Se prefiere actualizar un documento de Knowledge existente a crear uno nuevo (principio de documento vivo).

### Funciones y ubicaciones de los tres tipos de documento (DEC-2026-09-30-03)

| Documento | Qué contiene | Dónde se guarda | Búsqueda por defecto |
|---|---|---|---|
| Especificación (decisión) | La decisión tomada en el momento de implementar sobre el código y los requisitos de implementación, y su motivo, los símbolos de código afectados y si está vigente o sustituida | registro decision (Tier P) → espejo en nota DEC | antes de indexar: se leen directamente el índice (`decisions.yaml`) y las notas DEC (incluirlas en el índice es un trabajo posterior) |
| KB (Knowledge) | La forma final del servicio y del dominio, explicada con un índice y un flujo que las personas puedan entender | `knowledge-base/`, el índice en `_meta/toc.yaml` | incluido |
| Historial de trabajo (Archive·Planning) | Registros de sesión, especificaciones de tareas, diagnósticos e informes con fecha, texto original de planificación externa | `sessions/`, `tasks/`, `relays/`, `planning/` | excluido (solo a petición explícita) |

- **Un documento de KB por cada posición del índice.** No se crea un documento nuevo sobre el mismo tema; se reescribe el existente. Si inevitablemente se sustituye por uno nuevo, el antiguo se cierra con `status: superseded` + `superseded_by`.
- **Los informes, diagnósticos e instantáneas con fecha no son KB.** Un documento cuyo nombre de archivo o título contiene una fecha (como `*-2026-09-16.md`) registra los hechos de ese día, así que va en el historial de trabajo (`tasks/{date}/` o `sessions/`). La KB solo refleja la forma final que cambió como resultado, y apunta al informe con `sources:`.
- **La búsqueda por defecto mira solo la KB.** El historial de trabajo se incluye únicamente cuando se pide de forma explícita a la herramienta de búsqueda (`search_docs(include_history=true)` o indicando `category`, CLI `--include-history`). Es para que el historial no desplace a los documentos canónicos de los resultados.

La clave que atraviesa las tres capas es el **nodo de tema**. Un nodo es una unidad del índice que leen las personas, y su fuente canónica es el `_meta/toc.yaml` del proyecto.
Un documento declara su pertenencia con el `nodes:` del frontmatter, y la página de nodo se genera **uniendo** el Knowledge (forma final, política), las decisiones y el Archive (historial de trabajo) que apuntan a ese nodo.
Una página de nodo no es una promoción. No escribe nada nuevo; solo reúne lo que ya existe en una pantalla, y si hay un hueco lo deja a la vista. Ese hueco es la visualización de lo que falta.

## Estructura de directorios

```
vault/
├── .obsidian/           Ajustes de la aplicación Obsidian (compartidos, seguidos por git)
│   └── plugins/         Ajustes de plugins como Custom Sort y Dataview
├── .kb/                 ★ Gestión del índice de la KB
│   ├── manifest.json    Hash SHA256 por archivo (seguido por git)
│   ├── schema.sql       Definición del esquema de la BD (seguido por git)
│   └── store.sqlite     Store de la KB (strata-kit kb, .gitignore — el kb.sqlite legacy se eliminó con DEC-2026-10-28-13)
├── .local/              Ajustes por máquina (.gitignore)
│   └── resolved-paths.yaml
├── .gitignore
├── env-config.yaml      Lista de alias de máquinas registradas (sin rutas)
│
├── _index/              MOC (Map of Content)
│   ├── projects.md      Lista de proyectos + enlaces
│   ├── decisions.md     Índice de ADR entre proyectos
│   ├── patterns.md      Índice de patrones/lecciones
│   └── glossary.md      Glosario del dominio
│
├── _meta/               ★ Ajustes globales
│   └── taxonomy.yaml    Definición del sistema de clasificación (categorías, tipos, etiquetas)
│
├── projects/            Conocimiento por proyecto
│   └── {project-name}/
│       ├── overview.md          Stack tecnológico, propósito, estado actual
│       ├── _meta/               Ajustes del proyecto
│       │   ├── taxonomy.yaml    Taxonomy extendida del proyecto (hereda la global) — eje de directorios
│       │   └── toc.yaml         ★ Árbol de nodos de tema (fuente canónica del índice que leen las personas) — eje de temas
│       ├── knowledge-base/      ★ KB del proyecto (objeto de indexación)
│       │   ├── _index.md        MOC (índice dinámico con Dataview)
│       │   ├── domain/          Conocimiento del dominio (categoría 1)
│       │   │   ├── _index.md    MOC de la categoría
│       │   │   ├── epics/       Conocimiento del dominio por épica
│       │   │   └── {topic}/     Directorio de tema (definido en la taxonomy del proyecto)
│       │   │       ├── _index.md
│       │   │       └── *.md     Documentos de la KB
│       │   ├── architecture/    Arquitectura técnica (categoría 2)
│       │   │   ├── _index.md
│       │   │   ├── decisions/   ADR
│       │   │   ├── constraints/ Constraint Card
│       │   │   ├── api-contracts/
│       │   │   ├── data-models/
│       │   │   ├── infrastructure/
│       │   │   └── *.md
│       │   ├── guides/          Guías (categoría 3)
│       │   │   ├── _index.md
│       │   │   ├── onboarding/
│       │   │   ├── conventions/
│       │   │   ├── troubleshooting/
│       │   │   └── *.md
│       │   └── references/      Referencias (categoría 4)
│       │       ├── _index.md
│       │       └── *.md
│       ├── tasks/               ★ Especificaciones de tareas (Builder→Worker)
│       │   └── {yyyy.mm.dd}/    Agrupadas por fecha
│       │       └── {nn}-{title}/  Carpeta de Work Order
│       │           ├── _order.yaml    Orden de trabajo
│       │           └── task-{nn}-*.yaml  Especificación de ejecución del Worker
│       ├── strata/              ★ Tier P canónico de un detached profile (core/docs/es/environment/data-placement.md §1.5)
│       │   ├── profile.yaml     placement profile manifest (ancla de bootstrap para un PC nuevo)
│       │   ├── decisions/       registros decision (DEC-*.yaml, una decisión = un archivo)
│       │   ├── decisions.yaml   índice generado (prohibido editar a mano)
│       │   ├── constraint-registry.yaml
│       │   └── layer-map.yaml
│       ├── decisions/           Notas DEC — solo generadas (DEC projection generator, prohibido editar a mano)
│       │   └── DEC-YYYY-MM-DD-NN.md
│       ├── nodes/               Páginas de nodo — solo generadas (generador de páginas de nodo, prohibido editar a mano)
│       │   └── {node-id}.md     p. ej. orders.checkout-v2.coupon.md
│       ├── planning/            ★ Documentos de planificación (type planning) — los crea el importador de documentos de planificación, original inmutable + sección de revisión de implementación
│       │   └── {source-name}/   Por origen (p. ej. notion-orders-intake). Nombre de archivo {slug-del-título-original}--{primeros 8 caracteres del id de origen}.md — se conserva el idioma del título original
│       └── sessions/            Traspasos de sesión · ledger (Archive)
│           └── session-YYYY-MM-DD-{slug}.md
│
├── patterns/            Patrones transversales a los proyectos
│   └── {pattern-name}.md
│
├── strata-feedback/     Registros de feedback de la metodología
│   └── {topic}.md       Feedback aplicado/no aplicado
│
├── references/          Referencias externas, resúmenes de API
│   └── {reference-name}.md
└── assets/              Recursos binarios (imágenes, Excel, etc. — prohibido ponerlos en la raíz del vault)
```

## Reglas de nombres

| Objeto | Formato | Ejemplo |
|---|---|---|
| Directorio de proyecto | kebab-case | `my-api-server` |
| Nombre de archivo de documento | kebab-case.md | `auth-strategy.md` |
| Nota DEC (generada) | DEC-YYYY-MM-DD-NN.md | `DEC-2026-08-19-01.md` |
| Página de nodo (generada) | {node-id}.md — el id del nodo tal cual, con sus puntos (.) | `orders.checkout-v2.coupon.md` |
| Documento de sesión | session-YYYY-MM-DD-{slug}.md | `session-2026-08-19-vault-restructure.md` |
| Archivo MOC | sustantivo en singular | `projects.md`, `glossary.md` |

Los nombres de archivo de sesión usan solo el formato único anterior: el prefijo `handoff-*`, los nombres de archivo con fecha y sin prefijo y los archivos de sesión `.yaml` están en desuso (los legacy son objeto de migración). El identificador real es el slug, no un número de secuencia (NN).

## ID estable (frontmatter `id:`)

Todo documento del vault tiene en su frontmatter un ID estable que no cambia al moverlo ni al renombrarlo:

```yaml
id: "kb-shop-api-order-concepts"   # {prefijo}-{project}-{slug} — inmutable tras su creación
aliases: ["nombre de archivo antiguo"]  # al mover o renombrar, conserva el identificador original (absorbe las unlinked mentions de Obsidian)
```

Los prefijos cubren todas las clases de documento (incorporando la cross-review del 2026-08-19):

| Prefijo | Objeto | Ejemplo |
|---|---|---|
| `kb` | documentos de knowledge-base/ y patterns/ | `kb-shop-api-order-concepts` |
| `session` | sessions/ (traspasos · ledger) | `session-strata-2026-08-19-vault-restructure` |
| `order` | orden de trabajo `_order.md` | `order-strata-2026.08.19-01` |
| `task` | documentos de especificación de tareas | `task-strata-2026.08.19-01-task-03` |
| `dec` | notas DEC (generadas) | `dec-strata-2026-08-19-01` |
| `relay` | packet·feedback de relays/ | `relay-strata-2026-08-19-task01-core-spec-review` |
| `moc` | MOC de `_index/` y de cada `_index.md` | `moc-shop-api-knowledge-base` |
| `node` | páginas de nodo de `nodes/` (generadas) | `node-shop-api-orders.checkout-v2.coupon` |
| `plan` | documentos de planificación de `planning/` (importados) | `plan-shop-api-0123456789abcdef0123456789abcdef` — el slug es el id del origen (Notion), inmutable aunque se reimporte |
| `doc` | cualquier otro documento no cubierto arriba | `doc-vault-env-config` |

- **El valor de {project}**: bajo `projects/{name}/` es el nombre de ese proyecto. Los **documentos transversales a los proyectos** (`patterns/`, `references/`, `_index/`, la raíz del vault) usan `vault` (p. ej. `kb-vault-{slug}`, `moc-vault-decisions`).
- Una ruta es solo un medio de navegación, no una identidad a largo plazo. La identidad de los enlaces y las referencias la aporta `id:`.
- En una migración (mover o renombrar), se conserva el `id:` y se añade el nombre de archivo antiguo a `aliases:`.
- **El id de un nodo es un espacio de nombres distinto del id de un documento.** Es una ruta unida con puntos (.) desde los ancestros, como `orders.checkout-v2.coupon`, y no sigue el esquema de prefijos anterior. Un documento escribe los ids de nodo en su campo `nodes:`, y solo el id de **documento** de una página de nodo entra en el esquema de prefijos, como `node-{project}-{node-id}`. Los puntos en el slug solo se permiten con el prefijo `node`.

## Sistema de categorías de la KB

Se define en taxonomy.yaml y consta de cuatro categorías:

| Categoría | Propósito | límite de depth | Tipos principales |
|----------|------|:---:|-----------|
| `domain` | Conocimiento del dominio de negocio | 3 | concept, specification, flow |
| `architecture` | Decisiones de diseño, API, infraestructura, restricciones | 2 | specification, decision, overview, constraint |
| `guides` | Incorporación, convenciones, resolución de problemas | 2 | guide, pattern, runbook |
| `references` | Estándares externos, referencias de especificaciones | 2 | reference, glossary |

- Sin prefijo NN: el orden sigue el campo `order` de la taxonomy
- La categoría se deriva del directorio (no se escribe en el frontmatter)
- Los children de la categoría `domain` se definen en la taxonomy del proyecto
- Reglas detalladas: `templates/vault/_meta/taxonomy.yaml`

La categoría es el **eje de directorios** (dónde se coloca un documento), y el nodo de tema es el **eje de temas** (de qué trata un documento). Los dos son independientes.
La categoría no se escribe en el frontmatter porque duplicaría la ruta, pero `nodes:` es información que no puede derivarse de la ruta, así que no es una duplicación. Un documento puede pertenecer a varios nodos, y un nodo no crea un directorio.
Fuente canónica y reglas del árbol de nodos: el `_meta/toc.yaml` del proyecto; las reglas de formato están en la sección `topic_nodes` de la taxonomy global.

## Procedimiento de incorporación de un proyecto

Al registrar un proyecto nuevo en el vault:

1. Crear el directorio `vault/projects/{project-name}/`
2. Escribir `overview.md` (con el frontmatter obligatorio; véase document-format.md)
3. Actualizar `_index/projects.md` (capa Index — se sustituye por regeneración cuando pase a ser generado)
4. Crear `_meta/taxonomy.yaml` (define los temas de dominio del proyecto)
5. Crear `_meta/toc.yaml` (árbol de nodos de tema — basta con un primer nodo. El punto de partida es cuando los documentos empiezan a tener `nodes:`)
6. Crear los directorios de categoría bajo `knowledge-base/` (`domain/`, `architecture/`, `guides/`, `references/`)
7. Crear los directorios `sessions/` y `tasks/`. Si es un proyecto con detached profile, incluir `strata/` (Tier P): el manifest `profile.yaml` es obligatorio (core/docs/es/environment/data-placement.md §1.5). `decisions/` y `nodes/` los crean los generadores

### Contenido mínimo de overview.md

```markdown
---
title: "{nombre del proyecto}"
type: overview
project: {project-name}
tags: [{etiquetas del stack tecnológico}]
created: {YYYY-MM-DD}
updated: {YYYY-MM-DD}
status: active
---

## Propósito
{1-2 frases sobre el propósito del proyecto}

## Stack tecnológico
- Lenguaje: {language}
- Framework: {framework}
- BD: {database}

## Mapeo de capas Strata
{Mapeo de los directorios de este proyecto → capas de Strata}
```

## Lo que nunca se incluye

- Código fuente (los fragmentos de código se permiten como excepción)
- Artefactos de compilación
- Rutas absolutas específicas de un entorno
- Secretos, claves, tokens
- YAML de traspaso en bruto (solo se guarda un resumen)

Excepción: las **rutas relativas, símbolos, endpoints y nombres de tabla** del repositorio en el `covers:` del frontmatter son punteros, no código, así que se permiten. Las rutas absolutas y el cuerpo del código siguen prohibidos.
