# Agent Operations (eje de operación de agentes)

> Canónico: strata-kit `core/docs/es/methodology/agent-operations.md` (migrado el 2026-10-29 desde strata `docs/04-agents/agent-operations.md`, DEC-2026-10-29-11).

> El **tercer eje ortogonal** de Strata. Execution Mode (cómo se trabaja) → Verification Tier (quién verifica) → **Agent Operations (cuándo, cuánto y cómo se digiere)**.
> La definición de Verification Tier tiene su source of truth en `core/docs/es/methodology/verification-tier.md`.
> Abarca: horario de operación (batch nocturno), presupuesto (budget envelope), estructura multisesión y la forma en que una persona digiere la producción creciente (Decision Inbox + puerta (gate) de validación de autoinformes).
> Estado: `draft` (diseño acordado. El packet de §1 y el CLI del ledger (`kb ledger`) de §5 están implementados. La verificación de resultados y la gate del Decision Inbox de §2–4 no cuentan con una herramienta automatizada: el agent-ops.py del antiguo strata no se usa desde 2026-06 (DEC-2026-10-29-12). El agent runner real no está implementado)

## 0. Por qué hace falta

Execution Mode y Verification Tier tratan de "cómo hacer bien una tarea".
Agent Operations trata del problema que está encima: **la disciplina operativa que evita que las personas sean un cuello de botella o se ahoguen cuando se ejecutan muchos agentes durante mucho tiempo**.

Premisa central (atraviesa todo este eje):

> El objetivo no es ejecutar muchos agentes. El objetivo es **limitar con firmeza la unidad de entrega, los roles, los resultados y la superficie que una persona tiene que mirar**.
> Todo dispositivo que aumenta la producción (multisesión, batch nocturno) ahoga a la persona si no existe un dispositivo que digiera esa producción (Decision Inbox, puerta de validación).

Principios en resumen:

1. Un relevo envía un **packet estructurado**, no la conversación completa.
2. La multisesión se opera **centrada en un Coordinator (hub-and-spoke)**, no como conversación N:N.
3. El trabajo nocturno se limita a un **budgeted batch**, no a la autonomía.
4. La persona mira solo el **Decision Inbox**, no el raw output.
5. Las etiquetas que ve la persona no son autoinformes, sino **etiquetas reevaluadas por verificación cruzada**.

Este documento es la source of truth de los primitives metodológicos de la familia runtime: **Relay Packet, Decision Inbox, review_gate, Shared Session Ledger**.
Los adapters/runtimes como el hub de Quilt no redefinen estos primitives; los consumen como superficies de routing, projection y execution.

---

## 1. Capas del Relay Packet (menos tokens + menos errores)

Está prohibido enviar la conversación completa. El objetivo no es reducir la cantidad de tokens, sino **aumentar la densidad de información por token**.
(Procedimiento de revisión cruzada: `skills/strata.review/SKILL.md`; el envío va por el hub de Quilt, `hub_send`)

```text
Level 0: solo la pregunta
Level 1: pregunta + conclusión actual + puntos en discusión            ← por defecto
Level 2: Level 1 + archivos/líneas de evidencia + resumen del diff  ← por defecto
Level 3: texto completo de los extractos necesarios
Level 4: transcript completo (solo como excepción)
```

Lo habitual es Level 1–2. Si se lanza la conversación en prosa tal cual, se difumina qué debe juzgar el otro lado.
Forma de packet recomendada:

```yaml
intent: "review"
decision_so_far: "La fuente canónica de Verification Tier se separó en verification-tier.md"
open_questions:
  - "¿Encajan el flujo de Promotion Gate y el límite del esquema de backlog?"
evidence:
  - file: "core/docs/es/methodology/verification-tier.md"
  - file: "core/docs/es/methodology/task-spec-schema.md"
constraints:
  - "No se ponen nombres de herramientas en los documentos de Core"
request:
  - "Señalar solo 1-2 huecos"
```

- **Adjuntar el ancla**: en varias idas y vueltas, para que el otro lado no olvide el acuerdo y se desvíe, se adjunta cada vez `decision_so_far` (resumen fijo).
- **Bloquear packets débiles**: si `evidence`/`request` están vacíos, se avisa antes de enviar — si se envía un packet vacío, existe el riesgo de que parezca Cross-Verified aunque no se haya realizado ninguna verificación. (Caso real: un Reviewer que recibió un packet vacío devolvió correctamente "no se puede revisar")

## 2. Multisesión (Model-A n · Model-B n)

Es posible, pero dejar que se hablen entre sí en N:N lleva a explosión de tokens, revisión duplicada y responsabilidad poco clara.
Lo habitual es **hub-and-spoke**.

```text
Coordinator
  ├─ ModelA-Review-1
  ├─ ModelA-Research-1
  ├─ ModelB-CodeReview-1
  ├─ ModelB-Impl-1
  └─ ModelB-Contrarian-1
```

No se permite que las sesiones hablen directamente entre sí. Todas depositan su resultado en la relay queue y el **Coordinator lo reúne**.

Estructura prohibida:
```text
Model A1 ↔ Model B1 ↔ Model A2 ↔ Model B2 ...   (el fan-out es fácil y el fan-in es difícil)
```

Separación de roles:

| Rol | Responsabilidad | Límite de autoridad |
|------|------|----------|
| Primary | Dirige el trabajo | — |
| Reviewer | Busca defectos | No dictamina, solo señala |
| Contrarian | Busca argumentos en contra | Se conecta con adversarial verify |
| Summarizer | Comprime los resultados | Prohibido cambiar el contenido |
| Archivist | Ordena decision/backlog | **Solo hasta `open→triaged`. `accepted/rejected` lo decide la persona** |

> **Clave**: el fan-out (multisesión) es fácil y el fan-in (síntesis) es difícil. Sin un punto de convergencia (Coordinator o persona), se agrava por sí solo el problema de §4.

Regla del árbol de trabajo (git worktree) (DEC-2026-09-17-01): incluso con Workers o sesiones en paralelo, el árbol de trabajo se crea **solo si el usuario ha aceptado esa propuesta**. El modo automático es igual. Lo habitual es la ejecución secuencial en una única rama del checkout que ve el usuario; si de verdad hace falta un árbol de trabajo, se propone la necesidad, el nombre de la rama y el plan de limpieza como un solo punto y se espera la respuesta. Al terminar, se deja la rama, se limpia el árbol de trabajo y se informa. La regla canónica es `core/docs/es/methodology/execution-modes.md` § Regla absoluta 7.

### 2.1 Esquema de resultados de ejecución

Todavía no hay un runner que ejecute la multisesión en sí. El resultado de plan que recibirá el Coordinator sigue el esquema de abajo, y en la revisión se comprueba la **prohibición de enlaces N:N**, el enum de roles y el límite de autoridad del Archivist (ahora no existe una herramienta de comprobación automática).

```yaml
multi_session:
  coordinator: "human"        # human | agent
  sessions:
    - id: "review-1"
      role: "reviewer"        # primary | reviewer | contrarian | summarizer | archivist
      tool: "codex"           # adapter label, no es un enum de Core
      packet_ref: "$STRATA_VAULT/projects/{n}/relays/..."
      allowed_transitions: [] # archivist solo permite ["open->triaged"]
```

Prohibido:
- `direct_peer_links`: enlace en el que las sesiones hablan directamente entre sí. Si se encuentra, se rechaza.
- Una transición en la que el Archivist dictamina hasta `accepted/rejected/applied`.

## 3. Protocolo del batch nocturno (22:00–08:00)

No es trabajo autónomo sino un **budgeted batch**. Para no romper el principio de "la decisión es de la persona", se separa así: **noche = generar, día = juzgar**.

### Antes de las 22:00 — la persona prepara
```text
1. Elegir 3–5 work packets para procesar esta noche
2. Indicar en cada packet el alcance/prohibiciones/presupuesto/condición de finalización
3. Limitar el alcance de escritura permitido (write_scope)
4. Definir las condiciones de parada
```

### Reglas del agente nocturno
```text
- Prohibidas las nuevas decisiones de arquitectura
- Prohibido el trabajo con impacto en producción
- Prohibido commit/deploy/borrado (o aprobación aparte)
- Si es ambiguo, parar y dejarlo como pregunta
- Cada agent entrega solo un resumen final de una página
- Todos los resultados esperan como needs_decision (no se adopta nada antes de cross_verified)
```

### budget envelope + límites duros
```yaml
agent_budget:
  max_turns: 8
  max_files_read: 12
  max_output_lines: 80
  write_scope: ["assigned/paths/only"]
  stop_if:
    - "architecture decision required"
    - "test cannot run"
    - "scope expands beyond assigned files"
```

> **Prioridad de las salvaguardas**: los límites duros (`max_turns`/`max_files`/`write_scope`) son la **primera** línea. La parada por criterio propio (`stop_if: si es ambiguo`) es la **segunda** — porque un agente que no reconoce la ambigüedad no se detiene. La primera siempre debe funcionar.

### 08:00 — lo que mira la persona
```text
- Elementos que requieren decisión / archivos realmente cambiados / resultados de tests / riesgos / resultados a descartar / candidatos para la siguiente instrucción
```

Los tokens/el tiempo se gestionan no con cifras exactas sino con un **budget envelope por sesión + ritmo por hora** (para no agotar el límite de madrugada y dejar un vacío).

### 3.1 Esquema de resultados del batch

Un batch nocturno se fija primero como **batch spec**, no como runner. Antes de empezar se comprueba que existan los packets y los
campos del hard budget (ahora no existe una herramienta de comprobación automática). Sea cual sea la herramienta de ejecución, no se inicia un batch nocturno sin esta spec.

```yaml
night_batch:
  window: "22:00-08:00"
  packets:
    - id: "nb-001"
      packet_ref: "$STRATA_VAULT/projects/{n}/relays/..."
      owner: "primary"
  budget:
    max_turns: 8
    max_files_read: 12
    max_output_lines: 80
    write_scope:
      - "assigned/paths/only"
    stop_if:
      - "architecture decision required"
      - "test cannot run"
```

Todo resultado nocturno se trata como `review_gate.required: true` en la gate de §4.

## 4. Decision Inbox + puerta de validación de autoinformes (el núcleo de este eje)

El cuello de botella de la persona no es "leer" sino "**juzgar**". La salida de los agentes se procesa no como información sino como una **unidad juzgable**.
La superficie que mira la persona es **un único Decision Inbox**. El raw output solo se almacena.

### 4.1 Formato de salida obligatorio (self-report)
```yaml
result:
  status: completed | blocked | needs_decision | rejected
  one_line: "qué se hizo"
  changed_files: []
  evidence: []          # pointer obligatorio (prohibida la explicación larga sin decision)
  tests: []
  risks:
    - severity: high | medium | low
      summary: ""
      action_needed: ""
  decisions_needed: []
  discardable_notes_ref: "..."   # el raw output solo se almacena aquí
```

### 4.2 Puerta de validación de autoinformes (Self-Report Validation Gate)

**Problema**: el `status`/`risks` anterior lo clasifica el agente **por sí mismo**. Si subestima su propio riesgo (high→low), en cuanto la persona mira solo el Inbox, un elemento mal clasificado queda enterrado y pasa.
**Base medida**: no se puede confiar en el autoinforme — el modelo no registra como hecho una afirmación propia sin respaldo, y cuando se le dan evidencia y código, verifica y luego acepta.

**Solución**: **antes** de entrar en el Decision Inbox, el relevo (verificación cruzada) reevalúa **solo las etiquetas de triage**.

```text
Qué se verifica:
  Volver a revisar todo el raw output ❌          (esto desharía el ahorro de tokens de §1)
  Reevaluar status / risk / decisions_needed / evidence pointer ✅
```

Flujo:
```text
Agent self-report
  → Relay reclassifies (solo las etiquetas)
  → agree    → entra en el Decision Inbox
  → disagree → se promueve a "needs_human_decision" (a la persona)
```

Prevención de bucles infinitos:
```yaml
review_gate:
  required: true
  reviewer: cross_verified
  max_review_rounds: 1            # prohibido que un Reviewer vuelva a llamar a un Reviewer
  disagreement_policy: human_decision   # desacuerdo = se promueve directamente al Inbox
```

### 4.3 Ramificación basada en el riesgo (no se reevalúa todo)

Reevaluarlo todo es caro. Se divide según el riesgo.

**Reevaluación obligatoria:**
```text
- status: completed pero con archivos cambiados
- risk: high o unknown
- existe decisions_needed
- relacionado con architecture / schema / migration / deletion / security
- resultados del batch nocturno (todos)
- cambios en methodology_backlog / decisions
```

**Muestreo (u omisión):**
```text
- low risk / resúmenes de documentos / resultados de exploración / trabajo en el que solo se ejecutaron tests
```

### 4.4 Alternativa cuando no hay reevaluador (valor seguro por defecto)

`reviewer: cross_verified` presupone un reevaluador de otra familia de modelos.
**Si no hay reevaluador** (p. ej. no hay sesión cross activa de noche), no se pudo verificar, así que
el elemento se clasifica automáticamente como **`needs_human_decision`** — como no se pudo verificar, no se deja pasar sino que se eleva a la persona.

### 4.5 Lo que hace la persona cada día (Agent Output Triage)
```text
1. Lo que se aprueba  2. Lo que se rechaza  3. Lo que se vuelve a preguntar  4. Lo que se descarta
```
Reglas: el raw output solo se almacena, la persona ve solo el digest, el digest debe tener evidence pointers, prohibido el texto largo sin decision.

### 4.6 Ejemplo de esquema (extensión de task completion)
```yaml
triage:
  self_report:
    status: completed
    risk: low
    decisions_needed: []
  review_gate:
    required: true
    reviewer: cross_verified
    result: reclassified            # agreed | reclassified | no_reviewer
    final_status: needs_decision
    reason: "clasificado como low, pero incluye un cambio de schema"
    max_review_rounds: 1
```

### 4.7 Reglas de dictamen de la gate

Ahora no existe una herramienta de verificación automática (el agent-ops.py del antiguo strata no se usa desde 2026-06, DEC-2026-10-29-12). Las reglas de dictamen de abajo las aplican la persona o el Builder al preparar la review y el Decision Inbox.

Dictamen de la gate:
- `completed` + archivos cambiados, `risk: high|unknown`, `decisions_needed`, señales de architecture/schema/migration/security/decision y los resultados del batch nocturno llevan `review_gate.required: true`.
- Si no hay reviewer, `result: no_reviewer`, `final_status: needs_decision`.
- `max_review_rounds` es siempre 1.
- Si hay `changed_files`, el `evidence` pointer es obligatorio.
Un item del Decision Inbox se expone solo con una de estas actions: `approve | reject | question | discard`. El raw output se
almacena en `discardable_notes_ref` y el Inbox solo contiene un pointer.

---

## 5. Shared Session Ledger (libro de sesión compartido)

> La **fuente única de verdad (source of truth)** para que tres trabajadores (**user / primary / reviewer**) compartan un mismo flujo de solicitud y colaboren.
> Los adapters de cada herramienta asignan los roles `primary`/`reviewer` a sesiones reales de la herramienta. El esquema de Core no tiene nombres de herramientas como enum.
> El contexto lo guarda este archivo, no la memoria de la sesión del reviewer — es la aplicación al relevo del primer principio de Strata ("la sesión es consumible, el documento es persistente").

### 5.1 Por qué un ledger (la solución de nivel superior para gestionar la sesión del reviewer)

Cuando un relevo se ejecuta durante mucho tiempo, "cómo mantener la sesión del reviewer" se vuelve un problema. Pero **si la unidad de verdad es el ledger compartido y no la sesión del reviewer**, el problema desaparece:

- La sesión del reviewer **puede ser volátil** — el contexto queda en el ledger, no en la memoria del reviewer.
- El `decision_so_far` / `evidence` / `open_questions` del siguiente relay packet se **generan desde el ledger**, no desde la memoria del reviewer (packet de §1).
- El usuario, con la herramienta con la que empiece, lee el mismo ledger y continúa (sin importar la herramienta ni el punto de partida).

> **Sin embargo, la regla de reinicio del reviewer (en torno a §1) no se descarta.** El ledger resuelve el problema del *mantenimiento del contexto*, pero
> la **contaminación** en la que el reviewer mezcla en su propio juicio **acuerdos antiguos que no están en el packet** es otra cuestión. El reinicio se mantiene, rebajado de "para mantener el contexto" a
> **"higiene de prevención de contaminación"** (el propósito es distinto, así que no desaparece aunque exista el ledger).

### 5.2 Ubicación · formato

```text
Ubicación: $STRATA_VAULT/projects/{project}/sessions/session-{date}-{slug}.md
      (fuera de Core; persistente, compartido, apto para indexar. .strata/local es estado local de la máquina, por lo que no sirve)
Formato: archivo Markdown + entradas de bloque YAML por actor (legible para personas e indexable por máquinas)
frontmatter obligatorio: session_id · project · status · actors · topic · created · next_session · nodes
      (nodes = los nodos temáticos a los que pertenece esta sesión — la gate de cobertura de §5.7 los deriva de los archivos cambiados y los contrasta)
actor: user | primary | reviewer | coordinator | archivist
tool: optional adapter label    (p. ej. claude | codex — no es un enum de Core)
```

### 5.3 Esquema de entrada

Cada entrada es una cabecera `## [actor] {ISO8601 timestamp}` + un bloque YAML. Append-only, en orden cronológico.

```markdown
## [user] 2026-06-01T12:34:00+09:00
​```yaml
intent: "define shared ledger"
request: "Que Claude/Codex/User compartan el mismo flujo de solicitud"
decision: null            # decisión del usuario / juicio de parada (si la hay)
​```

## [primary] 2026-06-01T12:40:00+09:00
​```yaml
tool: "claude"                         # optional adapter label
from_user: "propuesta de shared ledger"     # qué problema se recibió
action: "analizado con un marco de nivel superior"        # cómo se trató
to_reviewer:                        # resumen del packet enviado al reviewer (null si no hay)
  intent: "review"
  decision_so_far: "ledger is source of truth"
  questions: []
outcome: "aceptar | rebatir | aplazar"         # tratamiento de la respuesta del reviewer (si la hay)
​```

## [reviewer] 2026-06-01T12:45:00+09:00
​```yaml
tool: "codex"                          # optional adapter label
reviewed: "ledger proposal"          # qué se revisó
verdict: "agree | agree_with_caveat | disagree"
risks:
  - "single writer required"
returned: "la opinión clave devuelta"
​```

## [primary] 2026-06-01T15:10:00+09:00
​```yaml
action: "señal de reinicio — línea de aviso superada | dos fallos con una hipótesis"
confirmed: ["hecho confirmado (y con qué se confirmó)"]
assumed: ["suposición aún no confirmada"]
discarded: ["hipótesis descartada (y por qué)"]
​```

## next_session
​```yaml
next: "session-2026-06-01-qwer.md"   # obligatorio al hacer close (null prohibido — evita romper la cadena)
reason: "motivo por el que se pasa al siguiente flujo"
​```
```

La entrada `[primary] 2026-06-01T15:10` de arriba es una entrada de reinicio. Cuando una señal de reinicio (session-splitting 5.1) lleva el trabajo a una sesión nueva, lleva los mismos tres campos que la sección de hechos e hipótesis del traspaso (confirmed, assumed, discarded).

### 5.4 Writer único + bloqueo de archivo (B3 — evitar la contaminación por escritura concurrente)

Para no repetir en el ledger la contaminación del archivo de sesión que acabamos de medir (dos procesos haciendo append al mismo archivo a la vez):

- Los procesos de agente de cada herramienta **no escriben directamente el archivo del ledger.** Escriben solo mediante el CLI de entrada único (`python3 "$STRATA_KIT/kb" ledger`).
- **CLI único ≠ concurrencia única**: dentro del CLI debe haber un **bloqueo de archivo (flock)**. Aunque varios adapters llamen a `append` casi a la vez, se serializan.
- El ledger es un **archivo distinto** de los archivos de sesión TUI en vivo (`~/.claude/...`, `~/.codex/...`) — no tiene que ver con la ocupación del TUI, así que no es objeto del guard de lsof.

### 5.5 Disparadores de append (B1 — quién lo deja y cuándo)

Las entradas no se dejan automáticamente sino con **disparadores explícitos**:

```text
- Antes y después de un relevo: entrada primary (to_reviewer) al enviar el packet, entrada reviewer (verdict) al recoger la respuesta
- Decisión del usuario: entrada user (decision) cuando el user juzga adoptar/rechazar/parar
- Fin del trabajo: escribir el puntero next_session al hacer close (§5.6)
```

### 5.6 Encadenamiento de sesiones (B2 — next_session obligatorio)

Al cerrar un ledger **se debe** rellenar `next_session.next`. No se cierra con `null` —
si se corta, el siguiente trabajador no puede continuar el flujo (el mismo patrón que el "un pending debe tener blocker" del traspaso (handoff)).
Si no hay trabajo que continuar, se indica `next: "none"` + `reason` para dejar constancia de que es un *cierre intencional*.

### 5.7 Gate de cobertura (al terminar la sesión — ¿cambió el código pero no la forma?)

Cuando se cierra una sesión, la gate de fin de sesión (el handoff generator y el validate/close del CLI del ledger) comprueba lo siguiente **en el mismo lugar** que el aviso de registro de decision sin commit:

```text
Entrada: lista de archivos de código que cambió esta sesión (task completion.files_modified/created, o si no, el diff del repositorio)
① Para cada archivo cambiado, buscar la especificación que posee esa superficie mediante covers (resolvedor de cobertura)
② Reunir los nodes de las especificaciones propietarias y contrastarlos con los nodes del frontmatter del ledger y del traspaso — si faltan, avisar para que se rellenen
③ Si alguna especificación propietaria no se actualizó en esta sesión (updated anterior al inicio de la sesión) y
   el frontmatter no tiene doc_change: none + doc_change_reason → aviso + se registra como deuda de ese nodo
④ Si hay archivos cambiados sin especificación propietaria → aviso de "superficie sin dueño" (hay que crear una especificación o ampliar covers)
```

- **Es un aviso, no un bloqueo.** Es del mismo nivel que el aviso de registros sin commit. Pero si se ignora, queda en la cara de "deuda" de la página del nodo para que la vea la siguiente persona.
- `doc_change: none` sigue el mismo principio que `next: "none"` de §5.6 — prohibido el valor vacío, un none explícito + motivo.
- La fuente canónica de la deuda no es la página sino el hecho mismo de que "la sesión no tiene declaración de doc_change". Solo hay dos formas de saldar la deuda: actualizar la especificación (actualizar updated·sources) o anotar retroactivamente el motivo de doc_change en el documento de esa sesión.
- Formato de los valores: sección "Campos de nodo y cobertura" de `core/docs/es/knowledge-base/document-format.md`. Es una señal independiente de la política de revisión (90 días).

`nodes` está incluido en los campos obligatorios del frontmatter del ledger (§5.2). El valor lo deriva el resolvedor en ②, y solo las sesiones sin cambios de código hacen que una persona lo elija directamente.

---

## 6. Relación con los otros ejes

```text
②multisesión (fan-out) ┐
③batch nocturno (generar) ├→ ④Decision Inbox + puerta de validación (fan-in) ← sin ella ①②③ ahogan a la persona
①relevo (densidad↑)    ┘
⑤ledger ← la fuente de verdad compartida donde queda cada acto de ①~④ (sin importar herramienta ni punto de partida)
```

- **Execution Mode**: solo hace referencia a Agent Operations. (La determinación/transición de modo está en `core/docs/es/methodology/execution-modes.md`)
- **Verification Tier**: el `reviewer: cross_verified` de la puerta de validación usa tal cual el Cross-Verified Tier de `core/docs/es/methodology/verification-tier.md`.
- **Methodology Feedback Loop**: el límite `open→triaged` del Archivist sigue la Promotion Gate de `core/docs/es/methodology/task-spec-schema.md` y el backlog lifecycle. El dictamen (accepted) es de la persona.
- **Revisión cruzada**: el packet de §1 lo genera `skills/strata.review/SKILL.md` y lo envía a un reviewer de contexto nuevo (Quilt `hub_send`). La antigua herramienta de relevo Claude↔Codex (strata bridge) es una implementación pasada y no se usa.

## 7. Prioridad de adopción

```text
①estructurar el relay packet  → posible de inmediato (beneficio claro, riesgo bajo)
④Decision Inbox + gate        → llave maestra (la salvaguarda de ②③, diseñar primero)
⑤Shared Session Ledger        → antes de hacer circular el relevo en varias idas y vueltas (requiere writer único + bloqueo)
②multisesión / ③batch nocturno → tras diseñar ④⑤ (si se hacen antes, la persona se convierte en cuello de botella / se ahoga)
```

Las piezas ya existen: la revisión cruzada (strata.review, filtro de verificación cruzada) + el backlog lifecycle (cola de dictamen) + Verification Tier (puerta de confianza). El fan-in guardrail (verificación automática de resultados) todavía no existe: el antiguo agent-ops.py no se usa. No es invención sino **ensamblaje**.

## 8. Asuntos pendientes

- Medir el coste real en tokens de la reevaluación de `review_gate` (para verificar la hipótesis de la gate delgada).
- Si el Coordinator será un agente o lo asumirá la persona (según la escala de la multisesión).
- El runner multisesión y el runner de batch nocturno no están implementados. La implementación actual llega solo hasta la validación de los resultados de plan/batch/self-report/Inbox y la normalización de la gate.
- Dónde guardar `discardable_notes_ref` (raw output) — posibilidad de reutilizar relays/ del vault.
- `kb ledger` (antes session-ledger.py) está implementado (append/read/close/validate + flock). El resto del refinamiento está en la cola de verificación cruzada.
- La gate de cobertura de §5.7 está implementada — conectada al handoff generator (comprobación previa a la generación + prefill de nodos derivados) y al validate/close del CLI del ledger (aviso), y las páginas de nodo se regeneran tras close·handoff. El campo obligatorio `nodes` del ledger está en periodo de introducción, por lo que es de **nivel aviso** (la promoción a error llega tras la retroactividad). La retroactividad de los documentos existentes (nodes/covers) y el toc.yaml por proyecto no se han iniciado (methodology-backlog MB-strata-2026-007).
- Cómo vincular los disparadores de reinicio del reviewer (topic_change / max_rounds 3–5 / decision_accepted / packet_drift / high_risk) con las entradas del ledger.
