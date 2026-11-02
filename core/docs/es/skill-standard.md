# Estándar de skills

Una skill de strata-kit es un flujo de trabajo que un agente sigue, no una referencia que hojea. El esquema en `core/schemas/skill.schema.yaml` fija la forma; esta página explica por qué existe cada parte y cómo escribirla.

## Forma

```text
skills/<name>/
├── SKILL.md            English canonical: frontmatter + yaml block + six sections
├── i18n/ko.md …        localized bodies, same section order
├── evals/              pressure scenarios and results (RED / GREEN / REFACTOR)
├── references/         long material the body links to
└── scripts/            bundled tools, run through their interpreter
```

## Frontmatter

`name` es el identificador plano con el que el harness hace la coincidencia. Las skills del núcleo son `strata.<verb>`; la skill de entrada es `using-strata`.

`description` es lo único que un agente ve antes de decidir si abre la skill. Empieza con "Use when", y luego lista situaciones, síntomas y palabras clave. Nunca resume el flujo de trabajo: un agente que lee un resumen sigue el resumen en lugar del cuerpo, y el cuerpo es donde están los puntos de control.

## El bloque yaml

Justo después del H1 viene un bloque `yaml` delimitado con `id`, `version`, `owner`, `triggers`, `inputs`, `outputs`, `required_context`, `allowed_tools`, `validation`, `failure_modes`. Es el gemelo legible por máquina de la prosa, y el generador lo lee para construir los adaptadores y el registro. `validation` se corresponde uno a uno con la sección Verificación.

## Las seis secciones

1. **Resumen**: un párrafo, qué produce esta skill.
2. **Cuándo usarlo**: disparadores y no-disparadores explícitos.
3. **Proceso**: pasos numerados. Cada paso nombra un punto de control y la evidencia que deja (un archivo, la salida de un comando, un id de registro).
4. **Racionalizaciones**: las excusas que un agente usa para saltarse un paso ("this is just a small change", "I remember the rule"), cada una con una réplica. Por defecto los agentes toman el camino más corto; esta sección es el contrapeso.
5. **Señales de alerta**: signos observables de que la skill se está omitiendo o aplicando mal, escritos de modo que un revisor o una puerta puedan detectarlos.
6. **Verificación**: qué debe ser cierto, y qué evidencia lo prueba, antes de que la skill pueda reportar finalización. "Parece correcto" nunca es evidencia.

## Escribir para el agente

- Prohibiciones para los pasos que los agentes se saltan a sabiendas. Plantillas con campos obligatorios para las omisiones. Condicionales para el comportamiento que depende de una condición.
- Sin cláusulas de matiz. "Do not X unless it matters" reabre la negociación; escribe las excepciones reales como condicionales separados.
- Mantén `SKILL.md` por debajo de 300 líneas. El material de referencia largo va a `references/` y se enlaza, de modo que la skill cueste pocos tokens hasta que se necesite.
- Un ejemplo completo y ejecutable vale más que tres parciales.

## Probar una skill

Escribir una skill es desarrollo guiado por pruebas aplicado al proceso. Ejecuta los escenarios de `evals/` con un subagente que no tenga la skill y registra qué se saltó y cómo lo justificó (RED). Escribe la skill mínima que atienda esos fallos y ejecuta de nuevo (GREEN). Cierra los resquicios que encontró y ejecuta una vez más (REFACTOR). Conserva el escenario, el resumen de la transcripción y el veredicto en `evals/`. Una skill sin una ejecución RED registrada es un borrador.

## Localización

Traduce solo el cuerpo. El bloque yaml, el frontmatter y todos los identificadores permanecen en inglés. `en` y `ko` son obligatorios antes de que la skill esté `active`; los otros cuatro locales recurren al inglés con una advertencia (véase `LOCALES.md`).
