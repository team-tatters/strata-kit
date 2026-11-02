# strata.build-task

## Resumen

Ejecuta una tarea: lee la especificación que la tarea lleva consigo, cambia solo los archivos nombrados dentro de una capa, ejecuta el comando de verificación e informa la finalización con evidencia y el cumplimiento de cada restricción.

## Cuándo usarlo

Se asigna un archivo de tarea de strata.order, o el usuario pide implementar un cambio planificado. No sin una tarea: una tarea incompleta se rechaza con la lista de lo que falta.

## Proceso

1. Lee la tarea y comprueba que está completa (capa, archivos, restricciones, verificación). Evidencia: la lista de comprobación. Recházala si está incompleta, pero antes lee los archivos nombrados y los documentos a los que apuntan, y enumera las decisiones que faltan como opciones concretas con una recomendación; leer no es adivinar, implementar sí. Después reclama la orden (`python3 -m kb order claim <order-id>`); si otra máquina o sesión la tiene, detente y pregunta a la persona. Evidencia: la salida de la reclamación.
2. Lee los archivos nombrados y un ejemplo existente del mismo patrón. Evidencia: rutas.
3. Escribe primero la prueba que falla cuando la tarea añade comportamiento, luego el código mínimo y después refactoriza. Evidencia: la salida de las pruebas antes y después.
4. Ejecuta el comando de verificación de la tarea y el verificador de capas. Evidencia: salidas y códigos de salida.
5. Informa: archivos cambiados, tabla de cumplimiento de restricciones, evidencia y todo lo que no se verificó.

## Racionalizaciones

| Pensamiento | Réplica |
|---|---|
| "La tarea está casi completa, puedo inferir el resto." | Inferir es como se cruzan las capas. Recházala y pide lo que falta. |
| "Las pruebas después del código están bien." | La prueba que falla es la evidencia de que la prueba prueba algo. |
| "La advertencia del verificador es un falso positivo." | Repórtala como advertencia con tu razonamiento; no la silencies. |

## Señales de alerta

- Ediciones a archivos que la tarea no nombra.
- Un informe sin salida de comandos.
- Una restricción marcada como cumplida sin motivo.

## Verificación

- La salida del comando de verificación está en el informe.
- Solo cambiaron archivos dentro de la capa.
- La tabla de cumplimiento de restricciones está completa.
