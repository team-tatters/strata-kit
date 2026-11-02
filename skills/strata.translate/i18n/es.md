# strata.translate

## Resumen

Completa los locales faltantes de tarjetas, cuerpos de skills, roles y documentos a partir del texto canónico, usando el glosario, sin cambiar el significado, los identificadores ni la estructura.

## Cuándo usarlo

Cuando la comprobación i18n reporta locales pendientes, después de redactar texto nuevo, o a petición. Traduce el significado; nunca traduzcas los identificadores.

## Proceso

1. Ejecuta tools/i18n_check.py y lista los elementos pendientes. Evidencia: la salida.
2. Lee el glosario y el texto canónico. Evidencia: rutas.
3. Escribe cada locale faltante, manteniendo idénticos los identificadores, enums, claves y marcadores de posición; mantén el orden de las secciones en los cuerpos de skills. Evidencia: el diff.
4. Vuelve a ejecutar la comprobación; los errores deben ser cero y las advertencias menos. Evidencia: la salida.
5. Señala cualquier frase en la que el texto canónico fue ambiguo, con la pregunta para el autor.

## Racionalizaciones

| Pensamiento | Réplica |
|---|---|
| "Una traducción aproximada es mejor que ninguna." | Una regla aproximada es otra regla. Traduce con precisión o señala. |
| "El identificador se lee mal en el idioma de destino, lo localizaré." | Los identificadores están en inglés por política. Localiza la etiqueta, no el id. |
| "Los marcadores de posición pueden moverse." | Los marcadores de posición deben coincidir exactamente o el generador se rompe. |

## Señales de alerta

- Un enum o una clave traducidos.
- Un locale con una frase de más o de menos.
- Advertencias de la comprobación que no disminuyeron.

## Verificación

- Los identificadores son idénticos.
- Errores de la comprobación en cero, advertencias disminuidas.
- Las ambigüedades están señaladas.
