# strata.order

## Resumen

Convierte una especificación aprobada en una orden y tareas autocontenidas que un worker puede ejecutar sin la conversación: una capa cada una, archivos explícitos, restricciones tomadas del registro y el comando que prueba la finalización.

## Cuándo usarlo

Después de strata.spec, cuando el trabajo debe dividirse. También cuando el usuario pide un plan. Las órdenes pequeñas (dos o tres tareas, una sola preocupación) usan el modo en línea: se escribe la orden y el ceremonial de tareas se reduce a una lista de comprobación en el mismo archivo.

## Proceso

1. Lee la especificación y el layer-map. Evidencia: rutas.
2. Escribe la orden: objetivo, criterios de aceptación copiados de la especificación, lista de tareas con dependencias. Evidencia: _order.yaml.
3. Escribe cada tarea: capa, archivos a tocar, restricciones filtradas del registro por alcance, comando de verificación, criterios de finalización. Evidencia: archivos de tareas.
4. Decide el modo en línea si la orden es pequeña y di por qué. Evidencia: la nota en la orden.
5. Comprueba si hay ciclos y tareas que abarquen dos capas. Evidencia: el resultado de la comprobación.

## Racionalizaciones

| Pensamiento | Réplica |
|---|---|
| "El worker averiguará los archivos." | Un plan se escribe para un lector sin contexto. Nombra los archivos. |
| "De todos modos las restricciones están en el registro." | Fíltralas dentro de la tarea. Los workers leen la tarea, no el registro. |
| "Cambio pequeño, omite la orden." | Usa el modo en línea. Omitir la orden pierde los criterios de aceptación. |

## Señales de alerta

- Una tarea que no nombra ningún comando de verificación.
- Una tarea que toca dos capas.
- Una orden sin criterios de aceptación.

## Verificación

- Cada tarea tiene capa, archivos, restricciones y verificación.
- No hay ciclos de dependencia.
- El modo en línea, si se usó, se declara con su motivo.
