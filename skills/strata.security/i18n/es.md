# strata.security

## Resumen

El núcleo entrega al operador una nota al día: qué es nuevo, qué sigue abierto, qué se cerró y qué objetivos nadie vigila. Esta habilidad es el lado humano de esa nota. Lee lo que escribió el trabajo diario, devuelve el juicio de la persona a los archivos (una orden, un riesgo aceptado, un umbral, un enlace) y rehace las listas de objetivos cuando la persona trae nuevas mediciones. No recolecta, califica ni parchea por sí sola: el trabajo diario recolecta y califica con las reglas registradas, y el parcheo ocurre solo mediante `patch plan` y `patch run` con una condición que se cumple.

## Cuándo usarla

Leer la nota es el disparador diario. También cuando hay algo nuevo que vigilar (un servidor, un escritorio, un archivo de dependencias), cuando la persona pregunta si una vulnerabilidad nos afecta, o cuando hay que fijar un umbral o un riesgo aceptado. No para la respuesta a incidentes (flujo del operator) ni para el almacén de defectos del producto.

## Proceso

1. **Leer la nota del día.** Abrir `security/notes/<day>.md`. Primero las líneas urgentes, luego los abiertos con su primer día, luego los objetivos ciegos. Si el encabezado dice que una capa no se vio, decirlo antes que nada. Evidencia: la ruta de la nota y su línea de counts.
2. **Seguir los enlaces antes de juzgar.** Por cada ítem, abrir el registro y la coincidencia en `security/matches/<day>.yaml`: qué identificador coincidió, qué rango, qué puntuación y de qué fuente (NVD, CNA, proveedor), si un valor se completó desde otra fuente. Evidencia: el id del registro y el de la coincidencia.
3. **Clasificar con la persona.** Los urgentes ya tienen orden (la creó el trabajo diario, atribuida a infra por defecto): mostrarla y preguntar solo la atribución (`assign`). Para los avisos preguntar: promover a orden (`promote <match> --by`), aceptar como riesgo con razón y plazo (`accept ... --until --by`) o dejarlo en la nota. Nunca decidir solo. Evidencia: la salida del comando.
4. **Dar ojos a los objetivos ciegos.** Pedir a la persona el lugar de aviso (un repositorio de GitHub, una página del proveedor) y escribirlo como enlace manual en `security/sources.yaml`; para un repositorio sin lockfile, nombrar el SBOM que necesita. Evidencia: la línea de manual_links.
5. **Rehacer las listas desde mediciones, nunca desde el servidor.** Cuando la persona pega `docker ps`, un compose, `dpkg-query` o versiones de SO, conservar solo imágenes, versiones y nombres de paquetes (quitar variables, contraseñas, hashes), ponerlos donde apunta `security/registry.yaml`, ejecutar `python3 -m kb security inventory --project <p> --env <e> --write` y mostrar la diferencia. Evidencia: la salida del diff.
6. **Cambiar un umbral solo con el comando.** `python3 -m kb security grading set --project <p> [--env <e>] threshold <valor> --by <persona>`: la línea de history es el registro. Evidencia: la entrada de history.
7. **Parchear solo con una condición que se cumple.** `patch plan <order>` nombra la condición (nivel de código · sin caída · reemplazo en minutos · aceptación registrada). `patch run` se niega sin una; la aceptación de la persona debe constar en la orden antes de una ejecución que la requiera. Evidencia: el plan y el registro de ejecución en la orden.

## Racionalizaciones

| Pensamiento | Réplica |
|---|---|
| «El título dice ejecución remota; lo marco urgente.» | Las calificaciones vienen de puntuaciones y del umbral registrado. Sin puntuación es aviso con razón no-score: mostrar, no subir. |
| «Está en KEV, así que es urgente.» | KEV ordena la nota; nunca califica (DEC-02). Bajo el umbral es aviso. |
| «Entro por ssh y compruebo la versión yo mismo.» | El agente no entra en servidores. Pedir a la persona la salida del comando. |
| «El compose tiene las versiones; lo guardo tal cual.» | También tiene contraseñas. Conservar imágenes y versiones; decir qué se omitió. |
| «La persona está ocupada; acepto este riesgo por ahora.» | Un riesgo aceptado es de la persona, con razón y plazo. Dejarlo en la nota. |

## Señales de alerta

- Una calificación o umbral editado a mano en un archivo.
- Un riesgo aceptado sin plazo, o registrado por el agente.
- Un comando de servidor ejecutado desde la sesión.
- Un compose o archivo de entorno copiado al vault con secretos.
- Un objetivo ciego convertido en coincidencia de CVE solo por el nombre.

## Verificación

- Cada acción nombra una línea de la nota o un id de coincidencia de ese día.
- `python3 -m kb security inventory --all` termina con 0 tras cambiar listas.
- El history de grading.yaml creció exactamente con los cambios hechos; las filas de accepted-risks.yaml tienen reason, until y by.
- No se tocó ningún servidor ni los flujos propios del producto.
