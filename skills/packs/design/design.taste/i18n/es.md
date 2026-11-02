# design.taste

## Resumen

El gusto es un registro de juicios, no un estilo que elige el agente. Esta habilidad mantiene ese registro para un proyecto o una marca —nunca para una persona en su conjunto—, porque el gusto se juzga en el contexto en el que se sitúa el trabajo (DEC-2026-11-01-10). La nota de gusto tiene cuatro secciones: gusto (líneas que la persona promovió), señales (reacciones y elecciones), inferencias (lo que el agente supuso, marcado) y rechazos (lo que la persona descartó y por qué). Una etiqueta que aparece en tres briefs distintos se convierte en candidata a promoción; la persona decide. La nota de expresión escribe cómo se ve ese gusto: los primitivos (color, desenfoque, opacidad, espaciado, radio, tipografía) una sola vez, y cada técnica como un párrafo legible con un bloque YAML de capas y relaciones —aclarar y oscurecer en luminosidad OKLCH, opacidad, contraste WCAG— que `kb taste expression` calcula (DEC-2026-11-01-11).

El procedimiento toma su forma de skeltonmedia/design-taste-skills (MIT; véase el NOTICE del paquete — no es Taste Skill, es otro repositorio): entrevista sobre referencias, un registro de rechazos, promoción solo de las señales que se repiten, inferencias marcadas. El texto y las comprobaciones de aquí son propios de strata.

## Cuándo usarlo

Mientras la persona diseña y reacciona a algo; cuando un proyecto o una marca necesita que se escriba o se revise su gusto; cuando una técnica debe escribirse de modo que pueda comprobarse. No para el brief en sí (design.brief) ni para los tokens o el contrato de componentes de un producto: eso es la traducción de la implementación. Leer una nota de gusto es de solo lectura; escribir una señal, una inferencia o una técnica eleva la sesión a sesión única (DEC-2026-11-01-18).

## Proceso

1. **Encontrar la nota.** Pregunta para qué proyecto o marca es. Abre su nota de gusto y su nota de expresión, u ofrece crearlas a partir del ejemplo del paquete; ejecuta `python3 -m kb taste check <taste.md>` y muestra los candidatos. Evidencia: las rutas y la salida de la comprobación.
2. **Entrevista, una pregunta cada vez.** Para cada referencia: qué notaste primero, qué hay en ella que lo produce, si pertenece aquí. Escribe la respuesta como una señal: `- YYYY-MM-DD 반응|고름 #tag [[brief]] — "sus palabras"`. Cuando la persona parte de un valor y no de una referencia (un valor central de una marca, una palabra como "confianza"), usa cinco ejes como marco — forma, color, sensación, textura, objeto — y pide en cada uno una asociación y una pista visible; las pistas de la persona son señales, y cualquier asociación que añada el agente es una inferencia. Reducir a unas tres palabras clave que no choquen se hace solo con la persona; cuando dos chocan, pregunta cuál lidera y cuál queda en la parte pequeña de acento (DEC-2026-11-01-13). Evidencia: las nuevas líneas de señal, leídas de vuelta a la persona.
3. **Rechazos.** Cuando la persona descarta algo, pregunta por qué y escribe `- YYYY-MM-DD #tag [[brief]] — "sus palabras" — 이유: …`. Un rechazo sin motivo es una pregunta aún abierta. Evidencia: las líneas de rechazo.
4. **Inferencias.** Todo lo que el agente concluye de las señales —"parece preferir colores tranquilos"— va a la sección de inferencias como `- [추론] #tag … — YYYY-MM-DD`, y se muestra a la persona como lectura del agente. Evidencia: las líneas marcadas.
5. **Promoción.** Para cada candidato que muestra la comprobación (tres briefs distintos; las repeticiones dentro de un mismo brief cuentan una vez), muestra sus señales y pregunta: promover, mantener o descartar. Solo al promover, escribe `- #tag <la frase de la persona> — 승격 YYYY-MM-DD · 근거 [[a]] [[b]] [[c]]`. Nunca promuevas a partir de una sola reacción llamativa. Evidencia: la elección de la persona y la comprobación superada.
6. **Expresión.** Cuando la persona nombra cómo debería verse algo, escribe o actualiza los primitivos y luego la técnica: un párrafo en sus palabras, un bloque YAML que referencia los primitivos solo por nombre, las capas y las relaciones que sostienen el juicio (el borde es más claro que la página; el texto se lee a 4,5:1 sobre el vidrio, el texto grande a 3:1). En el trabajo sin contrato de producto (diapositivas, pósteres, informes), una técnica puede nombrar roles como valores derivados — `text.primary: color.ink`, `accent: color.accent` — para que un brief pueda apuntar a roles; los valores de componente siguen en el contrato del producto. Ejecuta `python3 -m kb taste expression <expression.md> --show` y lee de vuelta los valores calculados. Evidencia: 0 problemas y los valores.
7. **Siguiente.** `python3 -m kb skills next design.taste`: design.brief para empezar un trabajo que se apoye en estas líneas, o nada.

## Racionalizaciones

| Pensamiento | Réplica |
|---|---|
| "Claramente le encanta esto; lo escribiré como su gusto." | Una reacción es una señal. El gusto es lo que se mantiene a lo largo de tres trabajos distintos, y lo promueve la persona. |
| "Se nota su estilo por las referencias." | Eso es una inferencia. Escríbela marcada, muéstrala y deja que la corrija. |
| "Un valor hexadecimal es más claro que un nombre." | Un valor en bruto oculta el juicio. Nombra el primitivo y escribe la relación que lo hace correcto. |
| "Mantengamos un solo archivo de gusto para la persona; es más simple." | El gusto se juzga en el contexto de un proyecto o una marca. Una nota compartida mezcla juicios hechos para cosas distintas. |
| "Lo rechazó; el motivo es obvio." | Pregunta. El motivo es lo que hace reutilizable un rechazo. |

## Señales de alerta

- Una línea de gusto sin fecha de promoción o con menos de tres briefs detrás.
- Una inferencia del agente escrita fuera de la sección de inferencias o sin su marca.
- Una señal parafraseada en lugar de citada.
- Una técnica con valores de color en bruto o sin ninguna relación.
- Una nota de gusto para una persona en lugar de un proyecto o una marca.

## Verificación

- `python3 -m kb taste check <taste.md>` informa 0; se mostraron los candidatos y la persona eligió para cada uno.
- `python3 -m kb taste expression <expression.md>` informa 0 para cada técnica tocada.
- Cada línea nueva son palabras de la persona o texto que aprobó, leído de vuelta a ella.
