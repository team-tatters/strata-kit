# strata.spec

## Resumen

Produce la especificación deseada para un cambio: qué debe ser cierto cuando esté terminado, enunciado de modo que cada criterio pueda verificarse, y en qué se diferencia de lo que el sistema hace hoy.

## Cuándo usarlo

Se solicita un cambio y no existe especificación deseada; un documento de planificación carece de criterios de aceptación; el usuario pregunta si el plan y el comportamiento actual coinciden. No para refactorizaciones puras sin cambio de comportamiento. Responder si el plan y el comportamiento coinciden es de solo lectura; escribir o revisar una especificación eleva la sesión a sesión única (DEC-2026-11-01-18).

## Proceso

1. Lee la fuente de planificación y los documentos de la forma construida que el cambio toca. Evidencia: la lista de documentos leídos.
2. Escribe objetivos, alcance (dentro y fuera), criterios de aceptación (cada uno con la evidencia que lo probará), restricciones de las tarjetas aplicables, preguntas abiertas con la persona que responde cada una. Evidencia: la sección del documento de planificación.
3. Lista las diferencias entre lo deseado y la forma construida, una línea cada una. Evidencia: la lista de diferencias.
4. Señala cualquier criterio que necesitaría una nueva decisión de arquitectura; no la decidas aquí. Evidencia: los elementos señalados.
5. Cierra con la revisión de implementación de cada documento de planificación escrito o cambiado en esta sesión. Pon `implementation.status` según lo que hallaron los pasos 1 y 3 (implemented, partial, diverged, not-implemented o superseded; nunca lo dejes en unreviewed), `reviewed` con la fecha de hoy y `spec` con la especificación as-built cuyo covers posee el código que realiza el plan. Si ninguna especificación posee ese código, escríbelo como una línea de diferencia ("ninguna especificación posee <ruta>") en lugar de omitir `spec` en silencio. El coverage gate sigue `spec` desde el código cambiado hasta el plan; un plan sin él es invisible para el gate. Evidencia: el bloque implementation. Cuando la revisión encuentra que el plan y el código no coinciden, deja una solicitud de juicio (`python3 -m kb divergence add`, o las filas de nueva comprobación de la puerta con `kb coverage-gate --divergence-inbox`) y pregunta a la persona; nunca elijas tú el juicio (reglas de planificación de document-format, DEC-2026-10-31-35).

## Racionalizaciones

| Pensamiento | Réplica |
|---|---|
| "El usuario ya lo explicó en el chat." | El chat no es un artefacto duradero. Escríbelo en el documento de planificación o la próxima sesión no lo tendrá. |
| "Los criterios de aceptación pueden venir después de la implementación." | Entonces describen lo que se construyó, no lo que se quería. Escríbelos primero. |
| "La lista de diferencias es obvia." | Escríbela de todos modos; la puerta de convergencia la lee a ella, no tu memoria. |
| "La revisión de implementación puede esperar." | Ese después rara vez llega: la mayoría de los planes importados sigue sin revisar. Revisa ahora los que tocó esta sesión, mientras el código está abierto. |

## Señales de alerta

- Un criterio sin evidencia nombrada.
- Una especificación que cambia directamente un documento de la forma construida.
- 'Implement as discussed' sin documento.
- Un documento de planificación cerrado como unreviewed, o sin `spec` y sin una línea de diferencia que explique por qué.

## Verificación

- Cada criterio nombra su evidencia.
- La lista de diferencias existe.
- Las preguntas abiertas nombran a su responsable.
- Cada documento de planificación tocado tiene su bloque implementation (status, reviewed, spec o la línea de diferencia por falta de especificación).
