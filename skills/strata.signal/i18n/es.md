# strata.signal

## Resumen

La etapa de operación muestra indicadores; no se hace cargo de los flujos del producto. La alimentan dos tipos: las mediciones del propio strata (revisión del kit, sesiones, verificación, traspasos, git) y los indicadores de flujo del producto que un proyecto lee, solo en lectura, de flujos que ya tiene: un registro de QA, los casos de prueba de cobertura. Cuando uno empeora, esta skill lo guarda en una nota con su evidencia y deja la elección a la persona: muestra a qué podría llevar el cambio y por qué, y luego registra lo que la persona escogió.

## Cuándo usarla

Cuando el informe diario del librarian muestra señales abiertas nuevas, cuando la comprobación lista señales estancadas o cuando la persona ve que un indicador empeora y quiere conservarlo. No sirve para un incidente del producto, una alerta o un comentario de usuarios: eso corresponde a las funciones propias del producto. Tampoco para decidir una regla (strata.decision). Escribir una nota eleva una sesión de solo lectura a sesión única.

## Proceso

1. **Encontrar el cambio.** Ejecutar `python3 -m kb signals candidates --project <p>` y mostrar los candidatos; `python3 -m kb indicators show --project <p>` muestra los indicadores de flujo del producto frente a la recogida anterior. Escribir los candidatos con `--write` cuando la persona esté de acuerdo (el trabajo diario del librarian los escribe por su cuenta, sin destino). Evidencia: la lista de candidatos o las rutas de las notas.
2. **Comprobar la evidencia.** La sección de evidencia de cada nota contiene el valor medido con su base: la revisión o la recogida anterior, y el umbral. Si un candidato se apoya en demasiado poco (una sesión, una sola recogida), decirlo en la nota. Evidencia: la sección de evidencia de la nota.
3. **Mostrar adónde podría ir y preguntar.** Para cada señal abierta, dar los candidatos con un motivo cada uno: una entrada del backlog de metodología (un hueco en cómo trabajamos o en el kit), una nota de idea (vale la pena desarrollarla pero aún no está clara, ideation.shape), un documento de planificación (trabajo que planificar, strata.planning), una decisión (strata.decision, cuando fija una regla) o descartarla (ruido, ya resuelto). Mejorar el flujo propio del producto es trabajo planificado como cualquier otro: empieza por la elección de la persona, no por que esta skill escriba en ese flujo. No elegir. Evidencia: los candidatos y la pregunta.
4. **Crear el elemento receptor y luego registrar la elección.** Escribir el elemento receptor solo con el texto que la persona aprobó: mostrar la entrada del backlog antes de añadirla; pasar una idea a ideation.shape y una planificación a strata.planning. Después ejecutar `python3 -m kb signals route --project <p> <nota> --to <id del elemento o ruta del vault> --by <persona>`. Para descartar, `--drop "<motivo>" --by <persona>`. El comando rechaza un destino que todavía no existe. Evidencia: la salida de route.
5. **Comprobar las notas.** Ejecutar `python3 -m kb signals check --project <p>`. Corregir cada problema que liste; las señales abiertas más de 14 días se presentan a la persona como pregunta, no como una decisión tuya. Evidencia: la salida del comando y su código de salida.

## Racionalizaciones

| Pensamiento | Réplica |
|---|---|
| «La tendencia es evidente; añado directamente la entrada al backlog.» | Entonces nadie la eligió y el próximo lector no puede ver de dónde salió. Escribe la señal, muestra los candidatos y deja que la persona escoja. |
| «La persona está ocupada; elijo yo el destino más probable.» | El destino es de la persona (DEC-2026-11-01-17). Déjala abierta y pregunta; una señal abierta no cuesta nada, un elemento equivocado cuesta una limpieza. |
| «El indicador de QA empeoró; registro el defecto o corrijo el registro.» | El registro de QA y el almacén de defectos son el flujo propio del producto. El kit los lee; cambiarlos es trabajo planificado que elige la persona. |
| «Este informe de incidente es importante; lo guardo también como señal.» | Los incidentes y los comentarios tienen su sitio en las funciones del producto. Una segunda copia aquí divide el registro. |

## Señales de alarma

- Una entrada de backlog, una nota de idea o una decisión creada a partir de una señal sin aprobación de la persona.
- Una nota enrutada cuyo decided_by es el agente o el librarian.
- Una nota sin la base de comparación en su evidencia.
- Cualquier escritura en los flujos propios del producto (registro, almacén de defectos, informes de cobertura) hecha desde esta skill.

## Verificación

- Cada nota nueva está en projects/<p>/signals/ y su evidencia tiene el valor y su base.
- Cada nota enrutada nombra a la persona que eligió, y su destino existe.
- No se escribió nada en los flujos propios del producto.
- `python3 -m kb signals check --project <p>` termina con 0, y las señales estancadas se plantearon a la persona.
