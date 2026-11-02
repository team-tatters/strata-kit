# strata.planning

## Resumen

La etapa de planificación es un filtro (DEC-2026-11-01-04). Un plan en bruto mezcla conversaciones sin decidir, código y reglas; si se inyecta tal cual, cada lector posterior (una búsqueda, una herramienta de inyección como Onyx, un compañero) lee basura. Por eso la fuente nunca se resume de entrada. Se divide en hechos, uno por fila, y cada fila recibe un destino. Solo los documentos depurados —el PRD (reglas que una persona puede observar) y la Logical Tech Spec (garantías que sobreviven a un cambio de implementación)— y los registros de decisión se inyectan y se comparten. La fuente y las tablas de trabajo quedan como respaldo. **Los documentos de planificación no llevan código ni arquitectura**: tablas, columnas, clases, servicios, rutas de API, códigos HTTP, frameworks y proveedores van al destino 'code' y se convierten en material para una especificación, una orden o una decisión.

## Cuándo usarlo

Llega una fuente de planificación externa; una nota de idea (ideation.shape) está lista para convertirse en plan; un paquete existente necesita revisar su tabla de correspondencias. No para escribir criterios de aceptación de un plan ya depurado (strata.spec), ni para elecciones de arquitectura (strata.decision). El modo de trabajo es de solo lectura mientras solo se lee la fuente; escribir el paquete lo eleva a sesión única, y un paquete que ocupa más de una sesión es de varias sesiones, con un traspaso al final de cada sesión (DEC-2026-11-01-18).

## Proceso

1. **De la fuente a la lista de hechos.** Coloca la fuente sin tocar bajo `source/` (o márcala con `category: source`). En `audit/facts.md`, escribe un hecho por fila: reglas, permisos, transiciones de estado, excepciones, datos, pantallas, criterios de aceptación, decisiones, supuestos, dependencias, historial de revisiones. Columnas, en este orden: `# | ubicación en la fuente | tipo | contenido (una frase que conserva el sentido de la fuente) | rol (planificación · especificación · código · contexto · duplicado) | ejes | subtema`. Los ejes son las cinco preguntas que una regla debe responder: identity, time, derivation, expiry, conflict (identidad, tiempo, derivación, caducidad, conflicto); escribe `n/a` cuando ninguno aplique. Evidencia: la lista de hechos.
2. **Árbol y decisiones.** Agrupa los subtemas en un borrador de árbol y obtén la confirmación de la persona antes de escribir ningún cuerpo. Los conflictos entre fuentes, o con decisiones posteriores, se convierten en preguntas; una respuesta que condiciona la arquitectura se registra con strata.decision. Evidencia: el árbol confirmado, las preguntas y sus respuestas.
3. **Escribe los documentos depurados y da un destino a cada fila.** En `audit/coverage.md` (`# | ubicación en la fuente | destino | nota`), cada hecho recibe exactamente uno de siete destinos: `<document> R<n>`, `isolated:<group>`, `defect:<what>`, `code`, `background`, `duplicate:#<n>`, `out of scope:<bundle>` (en orden: reflejado en un documento depurado, aislado, defecto, código, contexto, duplicado, fuera de alcance; en este último, la tabla de correspondencias del paquete receptor contiene la misma fila). Las contradicciones y los vacíos van a `audit/defects.md` junto con cómo los trataron los documentos depurados. Marca el PRD y la Tech Spec con `planning_doc: prd` / `tech-spec`. Evidencia: la tabla de correspondencias.
4. **Revisión de complejidad.** Cuando la política de una funcionalidad supera lo que una persona puede retener (la comprobación informa de un PRD de más de 800 palabras o 10 reglas, o de una Tech Spec de más de 1.200 palabras), construye una tabla de políticas por estado y propone aislar etapas o estados. Aislar cambia la política, así que decide la persona; las reglas trasladadas van a `audit/isolated.md`. Evidencia: la propuesta y la decisión.
5. **Comprueba, en un contexto nuevo.** Ejecuta `python3 -m kb planning check <paquete>`: filas sin destino, recuentos dobles, traspasos que el receptor no tiene, filas de regla sin eje, límites, expresiones de código en los documentos depurados (solo allí: la fuente y audit pueden nombrar cualquier cosa). Corrige y vuelve a ejecutar. Después envía el paquete a strata.review para una pasada solo de comprobación; el contexto que escribió el paquete es indulgente con él. Evidencia: la salida de la comprobación y la respuesta de la revisión.
6. **Impacto.** Ejecutar `python3 -m kb planning impact <paquete>`. A partir de los nodos de tema del frontmatter de los documentos refinados escribe `audit/impact.md` (archivo generado, solo evidencia): las especificaciones de esos nodos, el código que cubren, el código a un salto y sus pruebas (`--depth` para más), las decisiones de los nodos y otra planificación sobre los mismos nodos. Mostrar a la persona la línea de resumen y lo que choca — una decisión vigente que el plan contradice, otro plan sobre el mismo nodo. Cambiar una especificación o sustituir una decisión lo decide la persona. Sin nodos, preguntar a qué nodos de tema pertenece el plan. Evidencia: la línea de resumen.
7. **Siguiente.** `python3 -m kb skills next strata.planning`: strata.spec para los criterios de aceptación, strata.decision, o nada. **Atajo de decisión:** cuando la fuente es solo el orden del día de una decisión, sáltate los documentos depurados y pasa de la lista de hechos directamente a strata.spec o strata.decision.

## Límite de inyección

Se inyecta y se comparte: documentos depurados y decisiones. Solo respaldo: `source/`, `audit/` y todo lo marcado con `category: source` o `audit`. El límite se mantiene por ruta y por categoría (DEC-2026-11-01-05): la búsqueda de conocimiento omite el respaldo; `python3 -m kb planning boundary` imprime las rutas de exclusión para un conector de GitHub y las líneas `never` de share.yaml; `--list` imprime los documentos depurados que una herramienta de inyección puede leer. Notion queda fuera del kit: mantén la página de documentos depurados separada de la página de fuentes y apunta el conector al lado depurado.

## Racionalizaciones

| Pensamiento | Réplica |
|---|---|
| "La fuente es corta; basta con un resumen." | Un resumen decide en silencio qué descartar. La lista de hechos muestra cada descarte como una fila con destino. |
| "El nombre de la tabla aclara la regla." | Ata el plan a una implementación y se filtra a la inyección. Muévelo a una fila 'code'. |
| "Lo escribí yo, puedo comprobarlo yo." | El contexto que escribe es indulgente. Comprueba en uno nuevo. |
| "El conflicto es obvio; elijo la fuente más reciente." | Eso es una decisión de política. Regístralo como defecto y pregunta. |

## Señales de alerta

- Un documento depurado escrito antes de que la persona confirmara el árbol.
- Una lista de hechos con menos filas que reglas tiene la fuente.
- Una fila de la tabla de correspondencias sin destino, o la misma fila contada dos veces.
- Un documento depurado que nombra una tabla, una clase, una ruta de API o un proveedor.
- La fuente editada en el sitio.

## Verificación

- `kb planning check` no muestra destinos ausentes, recuentos dobles, traspasos rotos ni expresiones de código.
- El árbol, los aislamientos y el tratamiento de defectos citan la respuesta de la persona.
- Se ejecutó una revisión en contexto nuevo sobre el paquete.
- La fuente está bajo `source/`, sin tocar.
