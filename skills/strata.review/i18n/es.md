# strata.review

## Resumen

Obtiene una revisión independiente desde un contexto nuevo sin compartir toda la conversación: un paquete estructurado con la decisión, evidencia que prioriza punteros y una petición acotada, una sola ida y vuelta, y un triaje registrado de la respuesta.

## Cuándo usarlo

Para decisiones no triviales, cambios que tocan contratos, o a petición. No para cada edición; el paquete le cuesta contexto al revisor.

## Proceso

1. Elige el nivel (0 puntero, 1 resumen, 2 decisión + evidencia, 3 diff, 4 completo) según lo que el revisor necesita. Evidencia: el nivel y el motivo.
2. Escribe el paquete: ancla de la decisión, evidencia como path:lines, petición limitada a una o dos brechas, preguntas abiertas. Evidencia: el archivo del paquete.
3. Envíalo a una sesión revisora que no sea la sesión de trabajo; una sola ida y vuelta. Evidencia: el registro del relay.
4. Adjunta la respuesta textualmente y haz el triaje: aceptar, revisar, escalar. Si la revisión vino de fuera de la sesión de trabajo (otro modelo, una persona, una revisión cruzada), escribe también un registro de revisión en el vault en projects/<project>/reviews/<fecha>-<slug>.md, de tipo review, con review_of (la revisión evaluada), received y source: una sección de 'resumen de la respuesta' (aceptado, rebatido, hallazgos que el informe no vio, decisiones del usuario, decisiones y órdenes resultantes) y la sección 'original' textual (DEC-2026-10-30-03). Evidencia: el triaje con motivos y la ruta del registro.
5. Si la respuesta cambió una decisión, regístrala con strata.decision.

## Racionalizaciones

| Pensamiento | Réplica |
|---|---|
| "Solo preguntaré en mi propio contexto." | Tu contexto carga tus suposiciones. El punto es uno nuevo. |
| "Envía toda la conversación para que no se pierda nada." | Las conversaciones completas entierran la pregunta. Evidencia que prioriza punteros, petición acotada. |
| "El revisor estuvo de acuerdo, listo." | Registra el triaje. El acuerdo sin registro no es evidencia. |

## Señales de alerta

- Un paquete sin petición.
- Múltiples rondas automáticas.
- Salida del revisor editada antes de adjuntarla.

## Verificación

- El paquete está completo.
- Una sola ida y vuelta.
- El triaje está registrado.
