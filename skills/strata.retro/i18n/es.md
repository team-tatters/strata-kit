# strata.retro

## Resumen

Una retrospectiva sirve para que la persona entienda, no para que el agente sea más eficiente. El agente prepara el material y pregunta; la persona explica con sus propias palabras; después el agente señala lo que dicen los registros y dónde guardan silencio. El resultado es una nota escrita por la persona y, si algo merece llevarse a la metodología o a las decisiones, cada cosa pasa a la skill que la gestiona.

## Cuándo usarla

Cuando la persona quiere mirar atrás: una semana, una orden, una fase del proyecto o una decisión y su cadena de reemplazos. No sirve para comprobar si un trabajo está terminado (strata.verify) ni para una revisión independiente de un cambio (strata.review). El modo de trabajo es de solo lectura hasta que la persona acepta escribir una nota; escribirla eleva la sesión a sesión única.

## Proceso

1. **Acordar el material y generar el paquete.** Fijar con la persona un periodo y un proyecto, o una decisión de partida (su cadena de reemplazos y las revisiones y sesiones que la nombran — un paquete más pequeño cuando un periodo entero es demasiado), y, si hace falta, un nodo o un término de búsqueda. Ejecutar `python3 -m kb retro-bundle --project P --from D --to D [--node N] [--query Q]` o `python3 -m kb retro-bundle --project P --decision DEC-id`. Indicar la carpeta y los recuentos de `00-목차.md`, y que la carpeta puede subirse tal cual a NotebookLM. Evidencia: la ruta de la carpeta y los recuentos.
2. **Dejar que la persona elija qué mirar.** Mostrar tal cual la lista de elementos de `00-목차.md`: cada decisión, revisión y sesión con los hechos de su registro (fecha, nodos, relación de reemplazo, revisiones o decisiones vinculadas). Preguntar por dónde empezar. Si la persona pregunta qué dice un elemento, citar literalmente su sección de conclusión del paquete, con archivo y encabezado. No resumir, ordenar ni decir cuál salió mal. Evidencia: la elección de la persona.
3. **Preguntar antes de decir nada.** Sobre el elemento elegido, una pregunta cada vez: cuál era la premisa, por qué perdieron las alternativas, qué se sabe ahora que entonces no, qué elegiría hoy y por qué. Esperar la respuesta con sus propias palabras. Evidencia: las preguntas hechas.
4. **Señalar los registros después de que la persona haya explicado.** Donde la explicación y los registros difieren, o los registros callan (sin alternativas, sin contexto, un juicio revertido en la sección de proceso de juicio de la sesión), citar el paquete con archivo y encabezado y preguntar por ese hueco. Sin veredictos como «fue una buena decisión». Evidencia: cada señalamiento con su fuente.
5. **Escribir la nota de aprendizaje, con consentimiento.** Preguntar si se guarda una nota. Si sí, decir que la sesión pasa a sesión única y escribir `$STRATA_VAULT/retrospectives/<YYYY-MM-DD>-<tema>.md` con frontmatter `title`, `type: reference`, `created`, `tags: [retrospective, project/<p>]`, `source` (las condiciones del paquete) y tres secciones: **Qué se miró** (condiciones del paquete y elementos elegidos), **Lo entendido, en mis palabras** (las palabras de la persona o un texto que aprobó línea a línea), **Candidatos para traspasar** (cada uno con su destino y estado). Evidencia: la ruta de la nota.
6. **Traspasar los candidatos que la persona confirme.** Una lección válida más allá de este proyecto → strata.distill. Un hueco en el método → una entrada del backlog. Una decisión que hoy tomaría de otro modo → strata.decision con reemplazo. Cada uno solo después de que la persona diga que sí. Evidencia: la skill invocada por candidato, o «ninguno» con el motivo.

## Racionalizaciones

| Pensamiento | Réplica |
|---|---|
| «Veo qué salió mal; decirlo ahorra tiempo.» | Aquí el objetivo no es el tiempo. Lo que construye comprensión es la explicación de la persona; tu conclusión la sustituye. |
| «Un resumen breve de las decisiones ayudará.» | Un resumen es un veredicto sobre lo que importó. Muestra los elementos con los hechos del registro, cita la conclusión literalmente si te lo piden y deja elegir. |
| «Redacto yo la sección de comprensión y que la corrija.» | Entonces la nota es tuya. Escribe sus palabras o lo que aprobó línea a línea. |
| «Este candidato es claramente del backlog; lo registro.» | Registrar cambia el estado. Pregunta primero y pásalo a la skill responsable. |

## Señales de alarma

- Una primera respuesta que evalúa, ordena o resume el periodo.
- Un señalamiento a un registro sin el archivo y el encabezado del paquete.
- Una nota cuya sección de comprensión suena a prosa del agente.
- Una entrada de backlog, un patrón destilado o una decisión de reemplazo que la persona no confirmó.

## Verificación

- El paquete se generó con las condiciones acordadas y se mostraron sus recuentos.
- Las preguntas fueron antes que cualquier señalamiento y cada señalamiento citó su fuente.
- Si se escribió una nota: la persona aceptó, está en retrospectives/ y sus tres secciones siguen el formato descrito.
- Cada candidato traspasado fue confirmado y fue a la skill responsable.
