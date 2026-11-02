# Frontera de ubicación de datos (Data Placement)

> Fuente canónica: strata-kit `core/docs/es/environment/data-placement.md` (migrado el 2026-10-29 desde strata `docs/06-environment/data-placement.md`, DEC-2026-10-29-11).

> La única fuente de verdad (source of truth) sobre **dónde viven los artefactos de Strata y quién los rastrea**.
> Reúne reglas que estaban dispersas (la tabla de datos de cross-model-bridge, CLAUDE.md, task-spec-schema y la distinción local/shared de 01-context).
> Principio central: **"Las sesiones son desechables, los datos viven fuera de Core y el historial de trabajo vive fuera del repo del proyecto."**

## 0. Por qué hace falta (el problema que resuelve)

El diseño inicial hacía que `.strata/handoffs/` y `.strata/tasks/` se **rastrearan con git en el repo del proyecto para compartirlos entre sesiones**. Como resultado:

- **Churn de commits**: los traspasos y las tareas son *historial de trabajo* que se crea y cambia en cada sesión, pero se confirmaban en el repo de código para compartirlos, y la frecuencia de commits era anormalmente alta.
- **Doble almacenamiento**: el traspaso se escribía en `.strata/handoffs/*.yaml` (repo) y se sincronizaba a `sessions/*.md` del vault dejando el original en el repo, de modo que la misma información quedaba duplicada en dos sitios.
- **Deriva de ubicación**: los modelos nuevos (shared session ledger, task-spec) ya tienen el vault como fuente de verdad, pero las plantillas y scripts antiguos seguían apuntando a `.strata/`, y un mismo artefacto acabó con dos fuentes de verdad.

La solución es **sacar el historial de trabajo del repo del proyecto (al vault) y dejar en el repo solo la guía propia del proyecto**. Esto completa la parte que quedó inacabada de la decisión que ya había movido el ledger y el relay al vault.

## 1. La frontera de 3 Tiers

```text
Tier L · local      {project}/.strata/local/        excluido de git   estado de ejecución local a la máquina y volátil
Tier P · project    {project}/.strata/              rastreado en git  'guía' propia del proyecto (junto con el código)
Tier V · vault      $STRATA_VAULT/projects/{n}/     git del vault     'historial' de trabajo y artefactos de colaboración
```

El criterio de clasificación en una línea:

> **Si es volátil, es L; si es guía propia del proyecto, es P; si es historial de trabajo o un artefacto de colaboración, es V.**

| Tier | Ubicación | git | Naturaleza | Frecuencia de cambio |
|---|---|---|---|---|
| **L · local** | `{project}/.strata/local/` | Excluido (.gitignore) | Depende de la máquina, se rompe en otras máquinas, regenerable | Alta (irrelevante porque no se rastrea) |
| **P · project SoT** | `{project}/.strata/` (raíz) | Rastreado | La arquitectura y las restricciones de este proyecto. Debe revisarse en un PR junto con el código | Baja (solo cuando cambia la arquitectura) |
| **V · vault/shared** | `$STRATA_VAULT/projects/{n}/` | git del vault (aparte) | Historial y artefactos compartidos entre sesiones y entre personas. Independiente de los commits del repo | Alta (sin churn porque está fuera del repo) |

## 1.5 Placement Profile (embedded | detached)

La **ubicación física** del Tier P es una de dos, según la política de repo del proyecto.
El significado del Tier (guía propia del proyecto) y la obligación de revisión son los mismos; solo cambia la ubicación. (DEC-2026-08-19-01)

| Profile | Dónde está la fuente de verdad del Tier P | Rastro en el repo | Criterio de aplicación |
|---|---|---|---|
| **embedded** (por defecto) | `{project}/.strata/` — rastreado en git | Una línea de ignore para `.strata/local/` | Repos personales o controlados — el Tier P puede revisarse en un PR junto con el código |
| **detached** | `$STRATA_VAULT/projects/{n}/strata/` — git del vault | Solo `.strata/local/` excluido de git (cero commits) | Repos de equipo, etc., donde confirmar `.strata` va contra la convención |

La **fuente de verdad del profile es un archivo manifest** — si el puntero se guardara solo en la máquina local, no se restauraría en un PC nuevo (refleja la revisión cruzada del 2026-08-19):

| Profile | Ubicación del manifest | Dónde se conserva |
|---|---|---|
| embedded | `{project}/.strata/profile.yaml` (rastreado en git) | El repo del proyecto — **también se puede identificar un proyecto nuevo que aún no tiene decisiones** |
| detached | `$STRATA_VAULT/projects/{n}/strata/profile.yaml` | El vault — **un PC nuevo restaura el profile con solo hacer pull del vault** |

```yaml
# profile.yaml — placement profile manifest
profile: detached        # embedded | detached (el manifest del lado del repo solo admite embedded)
project: "{project-name}"
```

`.strata/local/vault-link.yaml` (Tier L, excluido de git) es una **caché local opcional** — no es la SoT y todo funciona sin ella.

- **Reglas del resolver del Tier P** (comunes a todo consumidor que lea el Tier P — correspondencia de implementación: `python3 -m kb --help`, `core/docs/es/kb-engine.md`):
  ① `.strata/profile.yaml` del repo (declaración embedded) → embedded
  ② existe `.strata/decisions.yaml` o `.strata/decisions/` en el repo (detección legacy) → embedded
  ③ `.strata/local/vault-link.yaml` (caché local) → detached
  ④ `$STRATA_VAULT/projects/{basename del directorio}/strata/profile.yaml` → detached (bootstrap de un PC nuevo)
  ⑤ Si no existe ninguno, el proyecto no usa Strata
- El árbol del Tier P detached: `strata/{profile.yaml, decisions/, decisions.yaml, constraint-registry.yaml, layer-map.yaml}`
- Si hace falta no tocar el repo en absoluto, registra `.strata/` en el **gitignore global** (`~/.config/git/ignore`) en lugar de en el `.gitignore` del repo del equipo.
- Con detached, continuar una sesión entre PCs **se completa con un único pull del vault** (hook de sincronización: DEC-2026-08-19-02).
- Una decisión que deba compartirse con el equipo se promueve a `docs/` del repo, aparte de su custodia en el vault (el mismo patrón que la regla de promoción de contratos de API del §2).

## 2. Ubicación por artefacto (la tabla canónica)

| Artefacto | Tier | Ruta | Notas |
|---|---|---|---|
| active-task (por sesión) | L | `.strata/local/active/{session-id}.yaml` | El estado actual cuando se interrumpe una sesión (regla absoluta). Un archivo por sesión para que las sesiones concurrentes no se sobrescriban entre sí (DEC-2026-08-19-05) |
| session-plan.yaml | L | `.strata/local/session-plan.yaml` | |
| session-log.txt | L | `.strata/local/session-log.txt` | Lo escribe el hook SessionEnd |
| last-compaction.yaml | L | `.strata/local/last-compaction.yaml` | Instantánea de PreCompact |
| agent-sessions.yaml (mapeo de sesiones) | L | `.strata/local/agent-sessions.yaml` | claude_id ↔ codex_id, depende de la máquina |
| **profile manifest** | **P** | `.strata/profile.yaml` (embedded) / `strata/profile.yaml` del vault (detached) | Fuente de verdad del placement profile (§1.5) |
| **registro de decisión** | **P** | `.strata/decisions/DEC-{date}-{NN}-{slug}.yaml` | La **fuente de verdad** de la decisión — una decisión = un archivo. La numeración y el registro pasan por el CLI decision writer (seguro con sesiones concurrentes, DEC-2026-08-19-05) |
| **decisions.yaml (índice)** | **P** | `.strata/decisions.yaml` | Un **índice T0 regenerado a partir de los registros**. Prohibido editarlo a mano |
| **constraint-registry.yaml** | **P** | `.strata/constraint-registry.yaml` | Registro de restricciones de contexto |
| **layer-map.yaml** | **P** | `.strata/layer-map.yaml` | Mapeo usado para comprobar violaciones de capas |
| cowork DB | L | `.strata/cowork/cowork.sqlite*` | Estado volátil de CoWorking (incluido WAL). Lo que se promueve a persistente va a tasks (V) y a registros de decisión (P) |
| ~~shared/~~ | — | `.strata/shared/` | **deprecated** — el historial de trabajo debe migrarse por completo al Tier V. Prohibido crear nuevos |
| **handoffs (traspasos)** | **V** | `$STRATA_VAULT/projects/{n}/sessions/` | Misma ubicación que el shared session ledger. **Se escriben directamente en el vault** |
| **shared session ledger** | **V** | `$STRATA_VAULT/projects/{n}/sessions/` | Source of truth del contexto |
| **tasks (especificaciones de tarea)** | **V** | `$STRATA_VAULT/projects/{n}/tasks/{date}/{nn}-{title}/` | `_order.yaml` + `task-{nn}.yaml` |
| **registros de relay** | **V** | `$STRATA_VAULT/projects/{n}/relays/` | Intercambio de request/feedback |
| **Hub delivery state** | **L** | `.strata/local/` o la DB local del Hub | hub_id, cursor del inbox, estado de pull/ack. Depende de la máquina y de la sesión |
| **Hub audit projection** | **V** | `$STRATA_VAULT/projects/{n}/sessions/` o `relays/` | Resumen de packets/reviews/decisions que una persona debe retomar |
| **methodology-backlog (project)** | **V** | `$STRATA_VAULT/projects/{n}/backlog/methodology-backlog.yaml` | Cola operativa = naturaleza de historial de trabajo |
| **exploration-report / draft api-specs** | **V** | `$STRATA_VAULT/projects/{n}/sessions/` (o junto a tasks) | Artefactos intermedios que se traspasan entre sesiones (las API accepted se promueven — véase la nota de abajo) |
| **espejo de notas DEC** (espejo ADR para personas) | V | `$STRATA_VAULT/projects/{n}/decisions/DEC-{date}-{NN}.md` + `_generated-index.md` | Un **espejo para lectura humana y backlinks**, generado a partir de los registros. La fuente de verdad es el Tier P. **Cuándo se genera**: **justo después** de que `add`, `regen-index` o `migrate` del CLI decision writer escriban los registros y el índice, **en la misma ejecución**, se llama al DEC projection generator y se **regenera por completo** la parte de ese proyecto (idempotente; elimina las notas sin fuente de verdad). El commit lo hace el canal de fin de sesión (handoff/ledger close → commit+push del vault); para reflejarlo de inmediato se usa `--sync` (DEC-2026-08-21-01) |

| **árbol de nodos temáticos (toc.yaml)** | **V** | `$STRATA_VAULT/projects/{n}/_meta/toc.yaml` | La **fuente de verdad** del índice legible por personas. Es guía por naturaleza, pero todos sus consumidores (el generador de páginas de nodo, el índice del KB, el resolver de cobertura) están del lado del vault y un proyecto detached no tiene dónde ponerlo en el repo, así que es V. No es un cambio que deba revisarse junto con el código |
| **páginas de nodo** | V | `$STRATA_VAULT/projects/{n}/nodes/{node-id}.md` | Una **vista de unión** (capa Index, prohibido editarla a mano) generada a partir de toc.yaml y el frontmatter de cuatro caras (especificación, restricción, decisión, sesión). **Cuándo se genera**: la construcción del índice del KB y el canal de fin de sesión (handoff/ledger close) regeneran por completo la parte de ese proyecto en la misma ejecución (idempotente; elimina las páginas sin fuente de verdad). No se deja a una ejecución manual aparte — la lección del espejo de notas DEC |

> **Una página de nodo no es una fuente de verdad** — las fuentes de verdad de las cuatro caras son, respectivamente, la especificación (V), la Constraint Card (V) y el registry (P), el registro de decisión (P) y la sesión (V); la página de nodo las reúne en solo lectura. La cara de "deuda" también es solo un indicador; su fuente de verdad es el hecho mismo de que el documento de sesión no tenga una declaración `doc_change`.
>
> **La fuente de verdad de las decisiones es el Tier P** — la ubicación física depende del profile (embedded = `.strata/` del repo, detached = `projects/{n}/strata/` del vault, §1.5). `projects/{n}/decisions/` del vault contiene **notas DEC** generadas a partir de los registros (para lectura humana y backlinks, prohibido editarlas a mano) y no es una SoT legible por máquina.
>
> **Papel y límites del espejo de notas DEC** (DEC-2026-08-21-01): en un proyecto embedded, la fuente de verdad de los registros **no se puede leer desde otra máquina hasta que se haga commit y push del repo del proyecto**. El espejo es un complemento entre entornos que cubre ese hueco por el canal del vault; no sustituye a la fuente de verdad. Por tanto ① el espejo debe generarse en **la misma ejecución** que registra el registro (dejarlo a una ejecución manual aparte lo deja vacío — el caso real de cero espejos en un proyecto backend el 2026-08-21), y ② las puertas de fin de sesión (el handoff generator y `validate`/`close` del CLI del ledger) **avisan de los registros sin commit** en `.strata/decisions*` del repo (no bloquean). Un proyecto detached no es objetivo de la puerta porque los registros mismos están en el vault y el canal de fin de sesión los confirma juntos.
>
> **Regla de promoción de contratos de API**: los `draft api-specs` son Tier V (intermedios de traspaso entre sesiones), pero un **accepted API contract** (el momento en que pasa a ser la base del código, de los clientes y de la documentación) no es historial de trabajo sino un project artifact → **se promueve al Tier P o a `docs/openapi` del repo**.
>
> **Aviso sobre la visibilidad del backlog**: el `methodology-backlog` del proyecto es en sí una cola operativa y por tanto Tier V, pero **si un elemento accepted cambia el Tier P (`decisions`/`constraint-registry`/`layer-map`), ese cambio del Tier P debe aparecer en el mismo PR** (visibilidad en la revisión de código — aunque el backlog pase al vault, *la plasmación de la decisión en el código* se revisa en el repo).

## 3. Reglas de .gitignore (proyecto)

Se excluye el Tier L y solo se rastrea el Tier P. El Tier V está fuera del repo del proyecto desde el principio, así que no importa.

```gitignore
# Strata — excluir Tier L (local, cowork) y rastrear solo Tier P (guía)  [embedded profile]
.strata/local/
.strata/cowork/
.strata/**/*.tmp

# El Tier P se rastrea de forma explícita (no se excluye):
#   .strata/decisions/  .strata/decisions.yaml
#   .strata/constraint-registry.yaml
#   .strata/layer-map.yaml
```

En el **detached profile**, el principio es no tocar el `.gitignore` del repo — registra `.strata/` en el gitignore global (`~/.config/git/ignore`) para mantener el rastro en el repo en cero (§1.5).

> ⚠️ Esto está **invertido** respecto a la regla antigua (rastrear `handoffs/` y `tasks/`). Antes era "rastrear para compartir", pero ahora compartir es tarea del **vault (Tier V)** y el repo no los rastrea.

## 4. Por qué esta frontera (justificación)

- **Lo que depende de la máquina (L) se rompe si se sube a git.** Los IDs de sesión y las rutas locales no significan nada en otra máquina (igual que el principio local/shared de la tarjeta `rec.session.state-in-files`).
- **La guía (P) comparte el destino del código.** Las decisiones de arquitectura y las restricciones deben verse junto con ese código al revisarlo o revertirlo, así que por defecto viven en el mismo repo y en el mismo PR (embedded). Pero si la convención del repo del equipo no permite confirmar `.strata`, se mueve **solo la ubicación** al vault (detached, §1.5) — la naturaleza de la guía y la obligación de revisión no cambian. Su baja frecuencia de cambio no crea churn.
- **El historial (V) tiene su propio canal para compartirse.** Los traspasos, el ledger y los relays son historial que conecta sesiones y personas. Ese intercambio corre por cuenta del **vault (su propia sincronización git/Obsidian)**, así que no hay razón para ponerlos en el repo de código. El repo de código solo recibe commits cuando cambian el código o la guía.

## 5. Relación con otros documentos

- **Sincronización del vault**: los traspasos se escriben directamente en el vault (el antiguo flujo de doble almacenamiento "original en el repo → conversión al vault" se abole). Quién escribe cada artefacto generado del vault lo fija DEC-2026-10-29-04 — las notas DEC están integradas en la ejecución del CLI decision writer (tabla del §2), las páginas de nodo las genera el librarian (`kb views-publish`) y los metadatos del índice se generan en cada máquina.
- **task-spec-schema.md** (`core/docs/es/methodology/task-spec-schema.md`): las tareas y el backlog son Tier V. Esta tabla es la fuente de verdad de las rutas.
