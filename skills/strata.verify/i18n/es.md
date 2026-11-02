# strata.verify

## Resumen

Sustituye la impresión de que algo está terminado por evidencia. La evidencia se registra en el momento en que se ejecuta una prueba, un verificador o una compilación, y se compara en el momento en que se afirma que está terminado: si un archivo de la tarea cambió entretanto, la evidencia está obsoleta y el comando se vuelve a ejecutar. Construye una tabla con lo que exigía la habilidad responsable, qué prueba cada punto y qué no se pudo verificar, y luego declara go o no-go.

## Cuándo usarlo

Antes de cualquier informe de finalización, solicitud de merge o afirmación de 'listo'; cuando se pregunta si algo funciona; en el momento en que aparece 'debería funcionar' o 'parece correcto'. Nunca se omite porque el cambio sea pequeño.

## Proceso

1. Reúne los puntos de validación de la habilidad responsable y de la tarea. Evidencia: la lista.
2. Ejecuta cada comando que produce evidencia (pruebas, verificadores, compilación) a través del registrador, indicando los archivos que cambió la tarea: `python3 "$STRATA_KIT/tools/verify_evidence.py" record --files <archivos o directorios de la tarea> -- <comando>`. El registrador muestra la salida, devuelve el código de salida del comando y añade una entrada (comando, código de salida, hora, final de la salida, hash del contenido de los archivos indicados) a `.strata/local/verify/<sesión>.yaml`; la sesión es el archivo activo por sesión más reciente salvo que se indique `--session`. Indica solo los archivos de esta tarea: otras sesiones pueden estar editando la misma copia de trabajo. Evidencia: salidas con códigos de salida y la ruta del archivo de evidencia.
3. Antes del informe, ejecuta `python3 "$STRATA_KIT/tools/verify_evidence.py" check`. La última entrada de cada comando aparece como superada o fallida, vigente u obsoleta (con los archivos que cambiaron). Vuelve a ejecutar un comando obsoleto; uno fallido es un punto no-go. Evidencia: la salida de check.
4. Rellena la tabla: punto, evidencia (la línea de check, o la ejecución externa si es CI), verificado o no verificado con motivo.
5. Declara go o no-go. Es no-go si algún punto must no está verificado o su evidencia está obsoleta. Un traspaso que diga `tests_passed: true` indica el archivo de evidencia. Un comportamiento que el cambio añade o altera debe ejercitarlo una prueba confirmada; un comando puntual es una comprobación manual, no evidencia de finalización: marca el elemento como no verificado y declara no-go hasta que exista esa prueba.

Cuando la pregunta es el proyecto entero y no una tarea —¿strata funciona de verdad aquí?: comprobadores instalados y ejecutados, guía al día, decisiones confirmadas, decisiones solo sobre fuentes del núcleo, la última ejecución del librarian—, ejecuta `python3 "$STRATA_KIT/tools/doctor.py" <proyecto>` (solo lectura; `--json` da los mismos elementos). Sus elementos default y block cuentan como los elementos must de arriba; los de referencia se informan, no se califican (DEC-2026-10-31-22·28).

## Racionalizaciones

| Pensamiento | Refutación |
|---|---|
| «Ya ejecuté las pruebas antes.» | `check` dice si ese «antes» sigue siendo válido. Si está obsoleto, ejecútalas ahora. |
| «Registrar es un estorbo; basta con ejecutar el comando.» | El registro es lo que permite comprobar la afirmación más tarde: tú mismo tras una compactación, o la siguiente sesión. |
| «Es un cambio de una línea.» | Los cambios de una línea rompen compilaciones. La tabla son tres líneas. |
| «Aquí no puedo ejecutarlo.» | Entonces escribe «no verificado» y qué lo verificaría. No lo afirmes. |

## Señales de alerta

- Un informe de finalización sin tabla.
- «Debería funcionar» en un mensaje de finalización.
- Pruebas descritas sin mostrar la salida.
- `tests_passed: true` sin archivo de evidencia, o una tabla que cita evidencia que `check` da por obsoleta.

## Verificación

- La tabla está completa.
- `check` devuelve 0 para los comandos citados (vigentes y superados), o el punto cita una ejecución externa.
- Se declaró go o no-go.
