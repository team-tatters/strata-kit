# design.brief

## Resumen

Esta es la etapa de diseño de la persona. Se diseñe lo que se diseñe —un documento, un objeto físico, una imagen, una publicación, una pantalla—, el trabajo empieza por un brief: para qué es, quién lo ve, en qué medio, bajo qué restricciones, con qué referencias y qué debe ser cierto para darlo por terminado. El brief es de la persona; el agente pregunta y anota, no decide el gusto. Un diseño se apoya en el gusto de la persona y en las técnicas que lo expresan (una superficie de vidrio, una sombra suave en relieve, una pila de bordes y tonos); el brief nombra las que usa este trabajo.

El contrato de diseño frontend (core/docs/<locale>/architecture/frontend-design-contract.md) es otra cosa: el flujo técnico que lleva un diseño ya decidido al código. Este paquete no lo sigue ni lo cambia (DEC-2026-11-01-09). Los dos se encuentran en un solo punto: cuando un entregable entra en un producto, el contrato lo señala con `design_ref`. Traducir la expresión de la persona a los tokens del producto es trabajo de la implementación.

## Cuándo usarlo

La persona va a diseñar algo, en cualquier medio; una especificación o un lanzamiento necesita algo diseñado; la persona quiere juzgar un diseño frente a su propósito. No para escribir la especificación (strata.spec) ni para implementar una pantalla (strata.build-task). Conversar sobre un diseño es de solo lectura; escribir el brief eleva la sesión a sesión única (DEC-2026-11-01-18).

## Proceso

1. **Brief.** Pregunta de una en una y escribe las siete secciones: Purpose, Audience, Medium and format, Constraints, References, Acceptance criteria, Deliverable (propósito, público, medio y formato, restricciones, referencias, criterios de aceptación, entregable). El propósito empieza por qué se está diseñando — una página web, una pantalla de app, diapositivas, un informe, una infografía, un póster, una imagen o publicación, un objeto físico u otra cosa — y se anota también en el frontmatter del brief como `category` (`web`, `app`, `slides`, `report`, `infographic`, `poster`, `image`, `post`, `object`, `other`); después, la frase que esta pieza debe transmitir; después, el contenido en orden — lo que debe estar y lo que puede salir. La categoría decide el adaptador del paso 3. Una sección sin respuesta dice desconocido. Evidencia: el brief y su categoría.
2. **Referencias.** Para cada referencia, pregunta qué notó primero la persona, qué hay en ella que lo produce y si pertenece a este trabajo. Escribe su respuesta junto al enlace. Cuando el proyecto o la marca tenga una nota de gusto y una nota de expresión (design.taste), nombra las líneas de gusto (#tag) y las técnicas en las que se apoya este trabajo. Una reacción o un rechazo que la persona aprueba tal como está escrito entra en la nota de gusto como señal de este brief, a través de design.taste. Evidencia: la sección References.
3. **Hacer o encargar.** La persona diseña, o el agente hace borradores dentro del brief. Las opciones que ofrece el agente se marcan como suyas; la persona elige. Lee el adaptador de la categoría del brief en `data/adapters.md`: diapositivas, informes e infografías usan el adaptador de documento (argumento, títulos de acción, elección de gráfico y estructura); web y app usan una skill de diseño externa si la persona elige una y, si no, la breve alternativa de ese archivo — nunca ambas. Cuando el entregable es una página web o una pantalla de app y la persona lo quiere, usa una skill de diseño que ya tenga instalada — por ejemplo Taste Skill (Leonxlnx/taste-skill, `design-taste-frontend`) o Impeccable (pbakaus/impeccable); pregunta cuál y no instales ninguna por tu cuenta. Pásale el propósito, el público y las restricciones del brief, y los primitivos y técnicas del proyecto o la marca cuando existan (Taste Skill: `--keep palette,type`; Impeccable: su `DESIGN.md`). Lo que elija esa skill es una opción del lado del agente, no el gusto de la persona; siguen decidiendo los criterios de aceptación del brief y el veredicto de la persona (DEC-2026-11-01-12). Evidencia: los borradores, la skill usada si la hubo y la elección de la persona.
4. **Juzgar.** Ofrece las comprobaciones comunes de `data/adapters.md` como criterios de aceptación candidatos, como sugerencias del agente; solo los que la persona elija se suman a los criterios. La persona juzga cada criterio de aceptación; escribe su veredicto. Un criterio que falla devuelve el trabajo al paso que lo causó — propósito, orden del contenido, jerarquía, composición, valores o foco — y no solo al lugar donde se nota. Señala el resultado en la sección Deliverable con `design_ref` (`kind`, `ref`, `version`). Cuando el resultado entra en un producto, ese `design_ref` es donde toma el relevo el proceso propio del producto. Evidencia: los veredictos y la referencia.
5. **Siguiente.** `python3 -m kb skills next design.brief`: design.taste cuando el trabajo dejó reacciones o rechazos que registrar, strata.order cuando el entregable entra en un producto, strata.review, o nada.

## Racionalizaciones

| Pensamiento | Réplica |
|---|---|
| "Es solo un póster; un brief es excesivo." | Bastan cinco líneas. Sin propósito ni público nadie puede decir si está terminado. |
| "Sé lo que queda bien aquí." | Eso es el promedio de lo que el modelo ha visto. El gusto es la reacción de la persona a sus referencias; pregúntala. |
| "Con el enlace de referencia basta." | Un enlace no dice qué importó. Escribe a qué reaccionó la persona. |
| "Las reglas de tokens del producto deberían dar forma a esto." | Aquí no. El contrato recibe el entregable en design_ref; la implementación traduce. |
| "La sección Medium and format ya dice qué es." | Esa sección recoge tamaño y tipo de archivo. Lo que se diseña decide el adaptador y la skill externa; pregúntalo primero. |
| "El adaptador tiene buenos valores por defecto; los aplico." | Son comprobaciones de oficio y puntos de partida, no el aspecto de la persona. Primero sus referencias y su gusto. |

## Señales de alerta

- Un artefacto entregado sin brief.
- Un propósito, un público o un criterio de aceptación que la persona nunca dijo.
- Referencias listadas como enlaces sueltos.
- La elección de aspecto del agente registrada como gusto de la persona.

## Verificación

- El brief tiene siete secciones con las palabras de la persona, con lo desconocido marcado, y una categoría.
- Cada criterio de aceptación lleva el veredicto de la persona.
- La sección Deliverable señala el resultado con design_ref.
