# Contrato de diseño del frontend (Design Contract)

> Canónico: strata-kit `core/docs/es/architecture/frontend-design-contract.md` — migrado desde strata `docs/03-architecture/frontend-design-contract.md` (orden 2026.10.29-06, 2026-10-29). El YAML de reglas está en `core/rules/`.

> Reglas legibles por máquina: `core/rules/layer-rules.yaml` → `frontend.variants.web` (Foundation · Primitive_UI · Semantic_Component),
> `core/rules/naming-convention.yaml` → `frontend.Foundation.token_alias` · `markers.token_exception`
> Este documento define el **contrato verificable** entre el diseño (tokens, variantes, composición) y la implementación.
> No presupone ninguna herramienta de diseño, herramienta CSS ni biblioteca de UI concretas. Los enlaces con herramientas están en `profiles/frontend.next-web/docs/es/frontend-tokens.md`.

## Principio de frontera

Core responde solo a dos preguntas: "qué hace este componente" y "dónde se decide la apariencia de este componente".
"Cómo se ve" debe derivarse de una combinación de tokens y ejes de variante, y no debe decidirse directamente dentro del código del componente.

La palabra "token" mezcla tres conceptos. Los separamos.

| Concepto | Definición | Dónde vive |
|---|---|---|
| Token | El sistema de valores: valores base (primitive) e intenciones (alias) | Foundation |
| Variant | Los ejes que expone un componente (variant · intent · size · state) | Primitive UI |
| Composition | Cómo se combinan los componentes. Se expresa mediante un **contrato** (nombre = significado, props = intención, slots), no por tamaño | Semantic Component · Feature Block |

## Tres niveles de tokens

| Nivel | Función | Ejemplo de nombre | Referencias permitidas | Herramienta de diseño |
|---|---|---|---|---|
| T1 Primitive | Valores base: escalas de paleta, espaciado, tipografía | `cool-neutral-30` · `blue-80` · `space-4` | Solo T2. Se prohíben las referencias desde componentes | Colección de variables "Primitive" |
| T2 Alias | Intención. **El único vocabulario compartido por agentes, diseñadores y código** | `color.surface.default` · `color.text.muted` · `color.action.primary.bg.hover` · `color.status.pending.fg` | Primitive UI · Semantic · Feature | Colección de variables "Semantic" (modos: light/dark/density) |
| T3 Component | Override por componente. Generado y opcional. Apunta a un alias T2, nunca a un valor raw | `button.solid.primary.bg` | Solo el componente que lo posee (y sus partes internas) | No se mantiene por defecto |

**Nombres de alias**: `{category}.{object}.{role}.{state?}` — category (color · space · radius · shadow · typography), object (surface · text · border · action · status · …), role (default · muted · bg · fg · …), state (hover · active · disabled · …).
Los modos (claro, oscuro, densidad) divergen en la **capa de valores** del alias, mientras el nombre sigue siendo uno.

**Reglas**
- T1 solo se referencia desde T2. Que un nombre T1 aparezca en el código de un componente es una violación.
- Un token de componente T3 solo lo referencia el componente que lo posee (y sus partes internas), y apunta a un alias, nunca a un valor raw. Cuando otro componente o pantalla necesita el mismo valor, se promueve a alias.
- Fuera de Foundation están prohibidos los valores raw (hex · px · rgba · nombres de escala de paleta), aplicado por propiedad de diseño: color, espaciado, tamaño de fuente e interlineado, radio, sombra, z-index. Los valores calculados o medidos en tiempo de ejecución (desplazamientos de scroll virtual, anchos de referencia medidos, anchos de columnas de datos y dimensiones continuas similares) se permiten como excepciones marcadas con `@strata:computed <reason>` (sin caducidad; un motivo vacío no cuenta). Un valor arbitrario que referencia una variable de alias no es un valor raw. Los nombres de clase de CSS utilitario deben reflejar tal cual los nombres de alias.
- Añadir un alias nuevo es una decisión de arquitectura — se exige un registro de decisión (`@strata:token-exception` es una vía de escape temporal con caducidad, véase §Política de excepciones más abajo).

## Ejes de variante

Primitive UI expone cuatro ejes. **No se usan nombres de paleta como valores de un eje** — los valores se definen por "qué significan", no por "cómo se ven".

| Eje | Valores (vocabulario por defecto) | Nota |
|---|---|---|
| `variant` | solid · outline · subtle · clean | Forma |
| `intent` | primary · neutral · danger · success · warning · info | Intención. Un proyecto puede extender un eje de estado de dominio (por ejemplo `status: pending · completed`) como **eje separado**. No se mezcla en el mismo eje |
| `size` | sm · md · lg | Un proyecto puede redefinir los valores |
| `state` | default · hover · focus · active · disabled | Estado de interacción. Los **estados de datos** (loading · empty · error) empiezan en Semantic Component |

Los nombres de propiedad del componente en la herramienta de diseño y los nombres de props en el código deben ser **idénticos**. Esta es la premisa de la comprobación de alineación.

## Composition Legality — legalidad de la composición

> La apariencia de un Semantic Component y de un Feature Block debe ser una **función pura de (los valores de los ejes de variante del Primitive UI que tiene debajo) × (tokens Alias)**.

Aquí "apariencia" significa las propiedades visuales propias del componente: color, tipografía, espaciado interior (padding), borde y el aspecto de cada estado. La colocación entre componentes, el margen exterior, el viewport y el comportamiento responsive, y el contenido y los recursos quedan fuera de esta regla; pertenecen a los elementos de layout (grid, stack y similares) que coloca el padre. Este alcance es lo que miden las comprobaciones de valores raw y de paleta.

Esta línea sustituye al Molecule/Organism de Atomic Design (una clasificación por tamaño). La composición se juzga por su legalidad, no por su tamaño.

| Veredicto | Ejemplo |
|---|---|
| Legal | `<Button intent="danger" variant="outline">` + `color.text.muted` · un valor arbitrario que referencia una variable de alias · un ancho medido en tiempo de ejecución con un comentario de motivo |
| Violación | `bg-blue-80` (referencia directa a T1) · `style={{color:'#303140'}}` (valor raw) · `className="bg-[#fff]"` (valor arbitrario) |

La correspondencia con la variante Atomic sigue el §Mapeo de `core/docs/es/architecture/frontend-atomic.md`. En resumen: Atom → Primitive UI, Molecule → Semantic Component (agnóstico a los datos) o Feature Block (llama a DataState), Organism retirado, Partial → Feature Block (Section).

## Artefactos de diseño y alineación

Una funcionalidad tiene tres artefactos. Cada uno tiene versión y **cualquiera de ellos** puede ser el punto de entrada. La puerta (gate) no es un orden sino una comprobación de alineación entre pares.

| Artefacto | Qué contiene | Forma |
|---|---|---|
| Spec | Qué hace — requisitos, comportamiento, estados | especificación de la tarea · KB specification |
| Design | Cómo se ve | `design_ref` (abajo) |
| Impl | Código | Repositorio |

**design_ref** (`core/docs/es/methodology/task-spec-schema.md` → `inputs.design_ref`)

| kind | Significado |
|---|---|
| `figma` | Referencia a un archivo o nodo de la herramienta de diseño |
| `storybook` | Las stories son el artefacto de diseño (canónico cuando no hay herramienta de diseño) |
| `claude_design` | Lienzo de borrador. Artefacto del punto de entrada `spec_first`; se promueve a `storybook` o `figma` al confirmarse |
| `none` | Declara **explícitamente** que no hay artefacto de diseño — `reason` es obligatorio (por ejemplo herramienta interna, solo texto) |

**Definición de alineado (aligned)**: el contrato del componente — nombre, ejes de variante y valores, alias usados, ejes de estado — es idéntico en Design e Impl.
Las herramientas comparan sobre esta definición (comparación de nombres de propiedad, render de la story frente al frame). La revisión humana usa la misma definición.

**Estado de alineación** (`completion.design_sync`)

```text
aligned   El contrato Design ↔ Impl coincide
stale     Un lado cambió y hay que volver a comprobar — en este estado no se puede declarar la finalización
waived    Discrepancia intencionada. Se exige reason + until (fecha de caducidad)
none      Trabajo con design_ref.kind: none
```

**Punto de entrada** (`_order.entry_point`)

```text
design_first   Design → (Design↔Spec) → Impl → (Impl↔Design)
dev_first      Impl → (Impl↔Spec) → Design(retrofit) → (Impl↔Design)
spec_first     Spec → Design·Impl en paralelo → ambas comprobaciones de alineación
change         Cambia cualquier artefacto → los demás pasan a stale → incompleto hasta recuperar la alineación   (por defecto)
```

La revisión no es un paso separado, sino **algo que dispara cada transición de artefacto**. El orden no es fijo.
La independencia de la verificación la define el eje `design_verified` de `core/docs/es/methodology/verification-tier.md`.

## Alcance canónico de la herramienta de diseño

Lo que se guarda en la herramienta de diseño (por ejemplo Figma) se mantiene acotado.

| Candidatos canónicos | Referencias (no canónicas) | Lo que no se guarda |
|---|---|---|
| Variables de token T1·T2 (incluidos los modos) | Frames de pantalla a nivel de Feature | Lógica de composición · flujo de datos · límites de hooks |
| Componentes Primitive UI y propiedades de variante | | Textos i18n (las claves viven en el código; la herramienta guarda anotaciones de clave) |
| Ejes de estado de los Semantic Component (loading · empty · error) | | Enrutamiento · límites de permisos · valores base de layout |

**La fuente canónica de los tokens es el archivo de tokens del repositorio de código** (recomendado). Motivos: los agentes y la CI pueden leerlo de forma fiable, se puede generar a partir de él un catálogo de alias que cabe en el presupuesto de contexto (`core/docs/es/methodology/context-protocol.md` CB-1) y no depende del acceso a la herramienta de diseño.
Se permite sincronizar de la herramienta de diseño al código, pero los conflictos se resuelven con un registro de decisión. La elección contraria (la herramienta como canónica) es posible como decisión en el profile del proyecto.

**Hay un único punto de resolución de tokens** — el paso de compilación de Foundation (archivo de tokens → variables CSS · constantes TS · variables de la herramienta). Los componentes referencian nombres de alias; un token de componente solo lo referencia el componente que lo posee.

## Cuando no hay herramienta de diseño

Hay una sola regla — **Primitive UI y Semantic Component tienen stories.** Sin herramienta de diseño, la story es el `design_ref`; cuando exista una herramienta, se pasa a una comprobación de alineación story↔herramienta.
La salida de una herramienta de borradores (como Claude Design) sirve de `design_ref` solo hasta que se confirma, y se promueve al confirmarse.

## Política de excepciones

Cuando un valor puntual introducido por un diseñador no se puede expresar como alias:

1. **Promover** — añadir un alias nuevo junto con un registro de decisión. El PR que cambia el archivo de tokens referencia el id DEC.
2. **Etiqueta de excepción** — `@strata:token-exception {reason} until {YYYY-MM-DD}`. La comprobación falla al caducar. La sintaxis está en `core/docs/es/conventions/strata-markers.md`.
3. **Medir** — mantener en 0 el número de valores raw fuera de Foundation, medido por diff y contado por propiedad de diseño (`profiles/frontend.next-web/enforcement/`).

Los valores calculados o medidos en tiempo de ejecución (desplazamientos de scroll virtual, anchos de referencia medidos, anchos de columnas de datos y dimensiones continuas similares) no son valores de diseño puntuales. Se quedan en el código como excepciones, cada una marcada con `@strata:computed <reason>`, y no se cuentan como valores raw. Los valores de diseño puntuales usan `@strata:token-exception`, que caduca.

## Separación Core / Convention / Profile

| Naturaleza | Ubicación | Ejemplo |
|---|---|---|
| Contrato verificable | Este documento · `core/rules/layer-rules.yaml` · `core/rules/naming-convention.yaml` | Los componentes referencian alias (los tokens de componente solo desde su propietario), la definición de alineación, el enum de puntos de entrada |
| Enlace con herramientas | `profiles/frontend.next-web/docs/es/frontend-tokens.md` · `profiles/frontend.next-web/docs/es/frontend-styling.md` | Formato del archivo de tokens, generador, mapeo de clases CSS utilitarias, herramienta de stories |
| Política del proyecto | Tier P del proyecto (`layer-map.yaml` · decisions) | Ruta del archivo de tokens, ejes de extensión de intent, dirección canónica, intensidad de aplicación por zone |
