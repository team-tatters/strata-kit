# strata.handoff

## Resumen

Escribe el traspaso que permite a la próxima sesión continuar sin esta conversación: qué se hizo con evidencia, qué queda pendiente y por qué, qué decisiones se registraron, qué vigilar y qué destilar hacia el núcleo personal. Luego registra, verifica y publica en tres pasos separados.

## Cuándo usarlo

Al final de una sesión, en el límite de una tarea, antes de una división o una compactación, o a petición. Cuánto escribir lo decide el modo de trabajo (using-strata): solo lectura no escribe traspaso; sesión única lo escribe solo cuando quedan pendientes; varias sesiones y orquestación lo escriben al final de cada sesión.

## Proceso

1. Registra: escribe completed (con archivos y evidencia), in_progress (blocker y unblocked_by para cada uno, y machine —el alias de env-config.yaml— cuando solo una máquina puede desbloquearlo; MB-strata-kit-2026-049), decisions_made (ids DEC), el rastro de juicio (qué se preguntó a la persona y qué respondió, juicios que se revirtieron y por qué, en pocas líneas, en la sección de ese nombre — DEC-2026-10-30-03), hechos e hipótesis (hechos confirmados y con qué se confirmaron, suposiciones aún no confirmadas, hipótesis descartadas y por qué; se rellena siempre que la sesión termina por una señal de reinicio: la conversación superó la línea de aviso de tokens o los intentos sobre una hipótesis se bloquearon dos veces; DEC-2026-10-31-11, session-splitting 5.1), warnings, next_session. Evidencia: el archivo del traspaso.
2. Columna vertebral: completa los enlaces de orders y kb_updates. Evidencia: el frontmatter.
3. Destila: lista los candidatos de destilación para el núcleo personal, o 'none' con el motivo. Evidencia: la sección de candidatos.
4. Memoria: ejecuta `python3 -m kb hygiene --memory` y mira los hechos que esta sesión escribió o cambió. Propón mover cada hecho de estado de avance (el trabajo en curso, lo siguiente, cambios sin confirmar, bloqueos) a in_progress o warnings de este traspaso, y pon `verified` con la fecha de hoy en los hechos que la persona confirma como aún correctos. Quitar un hecho de la memoria es una pregunta aparte, hecha después de moverlo: solo para los hechos que la persona aprueba uno a uno, moviendo el archivo a `_archive/` con `retired` y `retired_reason` y quitando su línea del índice; nunca un borrado simple (context-protocol §7, DEC-2026-10-31-16·17). Evidencia: la propuesta y las respuestas de la persona, o «ninguna memoria escrita en esta sesión».
5. Verifica: ejecuta la puerta de cobertura, la comprobación de enlaces y la comprobación de registros sin confirmar. Evidencia: salidas. La línea de la puerta «código cambiado sin especificación N · candidatos M · necesita especificación nueva K» (con los módulos que necesitan su propia especificación) va en el traspaso; sus candidatos de covers esperan en projects/<project>/_meta/covers-candidates.yaml (source: impact) hasta que alguien los apruebe y ejecute `python3 -m kb hygiene --covers-apply`. Si la sesión cambió conocimiento y no código (un concepto, una política o una decisión), la puerta también lista «código a revisar de nuevo (advisory)»: los covers de las especificaciones de los mismos nodos temáticos y los affects de las decisiones reemplazadas; anota en el traspaso qué se revisó o por qué no. Si el grado de la puerta queda sin resolver (una línea FAIL o BLOCK; el script deja una línea «no-go» al principio del traspaso y en stderr), la sesión no se cierra como terminada: escribe la especificación (strata.kb-update) o deja una excepción con motivo y fecha en el gate-overrides.yaml de Tier P, e indica en el traspaso cuál de las dos hiciste (DEC-2026-10-29-08).
6. Publica: prepara (stage) solo las rutas listadas (traspaso, ledger, espejos) y confirma (commit) por el canal de fin de sesión; informa con veracidad si el push tuvo éxito o falló. Si el remoto avanzó, nunca hagas rebase ni autostash sobre archivos que esta sesión no escribió: publica los commits de esta sesión sobre el remoto desde un clon temporal, o detente y reporta la superposición. Antes de confirmar, lee las reglas de commit del proyecto: lista la raíz del proyecto y lee AGENTS.md, CLAUDE.md y cualquier archivo de reglas o notas que haya allí (README, CONTRIBUTING, archivos con nombres como *NOTES* o *RULES*); si una regla del proyecto o del usuario difiere de una indicación por defecto del harness, como un trailer de atribución, sigue la regla del proyecto o del usuario.

## Racionalizaciones

| Pensamiento | Réplica |
|---|---|
| "'Esperando al usuario' basta para el elemento pendiente." | ¿Esperando qué, y qué lo desbloquea? Escribe ambas cosas o el elemento se arrastrará para siempre. |
| "Haré commit de todo en el vault." | Solo las rutas de esta sesión. Los cambios de otras sesiones no te corresponde publicarlos. |
| "Esta vez no hay nada que destilar." | Di 'none' y por qué. La ausencia también es información. |

## Señales de alerta

- Un elemento pendiente sin blocker.
- Una publicación que preparó archivos que no escribiste.
- Un traspaso sin valor en next_session.

## Verificación

- Los elementos pendientes están completos.
- Las salidas de las puertas están en la respuesta.
- Las rutas publicadas están listadas; el estado del push es veraz.
