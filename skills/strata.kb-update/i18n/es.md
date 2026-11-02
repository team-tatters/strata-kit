# strata.kb-update

## Resumen

Mantiene el conocimiento de la forma construida igual al código: encuentra el documento que es dueño de cada ruta cambiada, lo actualiza en el lugar con sus fuentes, o registra por qué no hace falta ningún cambio, y luego regenera las vistas generadas.

## Cuándo usarlo

Después de que cambió código cubierto; cuando se dispara una puerta o un aviso de deuda; a petición. También para declarar doc_change: none con un motivo, que es un resultado válido.

## Proceso

1. Lista los archivos cambiados y resuelve sus documentos dueños mediante covers. Evidencia: el mapeo.
2. Para cada dueño: actualiza en el lugar la sección relevante; fija updated y sources. Evidencia: el diff.
3. Para las rutas sin dueño: crea un documento de forma o amplía covers. Evidencia: el nuevo mapeo.
4. Donde la forma no cambió: escribe doc_change: none con el motivo. Evidencia: la declaración.
5. Reconstruye el índice y ejecuta la comprobación de enlaces. Evidencia: salidas.

## Racionalizaciones

| Pensamiento | Réplica |
|---|---|
| "El cambio de código es interno, la documentación no se ve afectada." | Entonces declara doc_change: none con ese motivo. La puerta necesita la declaración, no la suposición. |
| "Actualizaré la documentación en la próxima sesión." | La próxima sesión no sabe qué cambió. Actualiza ahora o declara. |
| "Un sello de fecha basta." | Un sello sin una comprobación de contenido es desvío con una fecha encima. |

## Señales de alerta

- Una ruta cubierta cambiada sin actualización ni declaración.
- Un documento actualizado sin sources.
- Páginas de nodo regeneradas a mano.

## Verificación

- El mapeo está completo.
- El índice y la comprobación de enlaces pasan.
- Las declaraciones tienen motivos.
