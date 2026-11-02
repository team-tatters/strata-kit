# using-strata

## Resumen

`using-strata` es el punto de entrada. Hace dos cosas y nada más: imprime dónde está la sesión (para que el usuario y el agente compartan los mismos hechos) y encamina la tarea hacia la skill que la tiene a su cargo. Nunca hace el trabajo por sí misma y nunca cambia; las extensiones llegan del registro por capas, no de este archivo.

## Cuándo usarlo

- Al inicio de cada sesión, antes de cualquier respuesta, incluida una pregunta aclaratoria, una búsqueda en el código o la lectura de un archivo. Las preguntas son tareas.
- Cada vez que la tarea cambia de forma: un reporte de error en medio de una funcionalidad, una solicitud de despliegue, una solicitud de actualizar la documentación.
- No cuando te despacharon como subagente para ejecutar una tarea concreta: entonces sigue la tarea e ignora esta skill.

## Proceso

1. **Lee el manifiesto del proyecto.** Abre `.strata/profile.yaml` en la raíz del proyecto. Si falta, detente e invoca `strata.init-wizard`. Evidencia: la ruta del manifiesto y su valor `project`.
2. **Carga el registro por capas solo cuando no hay encabezado.** Si el hook de inicio imprimió un encabezado de strata, ese encabezado ya muestra las tarjetas must vigentes y el estado de cada capa del registro. Úsalo y no vuelvas a abrir la constitución ni los registros completos. Haz la correspondencia de rutas del paso 5 con las descripciones de skills que muestra el arnés, y abre el archivo de registro de una capa de perfil o de proyecto solo cuando el encabezado muestre que esa capa tiene rutas propias. Sin encabezado, haz lo siguiente. Lee `skills/registry.yaml` de strata-kit, luego el registro del perfil y después el del proyecto (`.strata/kit/registry.yaml`, que escribe el asistente, y el `skills/registry.yaml` del Tier P cuando el proyecto tiene paquetes de skills). Abre cada archivo; cuando falte el archivo de una capa, di "ausente" para esa capa en lugar de omitirla. Las capas posteriores añaden rutas y sobrescriben las anteriores por `skill`. Abre también cada archivo del `required_context` de esta skill (la constitución) en lugar de apoyarte en un resumen de ella. Evidencia: la lista de rutas, con la capa de la que vino cada una, y las rutas de required_context abiertas. La capa de usuario (`~/.strata/skills`: los paquetes del kit en `packs/`, las habilidades propias de la persona en `local/`) se lee después del perfil y antes del proyecto; solo añade rutas: un nombre que otra capa ya tiene se rechaza, salvo una habilidad local que nombra con `overrides:` la habilidad del núcleo que reemplaza, y la cabecera lo muestra (`python3 -m kb skills check`, DEC-2026-10-31-36).
3. **Imprime el encabezado de contexto.** Dominio (trabajo o personal), id del proyecto y alias, id del perfil, las tarjetas must vigentes (solo ids), las tarjetas should exceptuadas con sus motivos, y la siguiente acción tomada del último traspaso o del archivo de active-task. Si el hook de inicio imprimió el encabezado, vuelve a mostrar ese encabezado y añade el modo de trabajo; no lo reconstruyas a partir de los archivos. Si no se puede leer ni un archivo activo ni un traspaso (variable sin definir, herramienta denegada, archivo inexistente), dilo y lee los rastros del propio repositorio —notas como NOTES o HANDOFF, `git log`, ramas— antes de preguntar en qué punto está el trabajo; el encabezado indica dónde buscó. Evidencia: el encabezado en la respuesta, antes de cualquier otra cosa.
4. **Fija el modo de trabajo.** Si el arnés asignó uno (una pieza de Quilt indica su modo en sus instrucciones), úsalo. Si no, elige: solo lectura (investigación, preguntas, revisión; sin cambios en archivos ni en estado externo), sesión única (un cambio que termina en esta sesión), varias sesiones (trabajo que cruza sesiones: existe o existirá una orden), orquestación (varias sesiones o roles trabajando en paralelo). Obligaciones: solo lectura, solo el encabezado y la ruta, sin archivo activo ni traspaso; sesión única, archivo activo con `mode` y `harness_session_id` (el id de sesión del arnés, `CLAUDE_CODE_SESSION_ID` en Claude Code, para que el encabezado y la restauración tras la compactación encuentren el archivo de esta sesión), evidencia de verificación, registros de decisiones y un traspaso solo cuando quedan pendientes; varias sesiones, además la orden y un traspaso al final de cada sesión; orquestación, además políticas de permisos por rol, restricciones inyectadas en los archivos de tarea y paquetes de revisión. Una sesión de solo lectura que va a cambiar estado pasa primero a sesión única. Los registros de decisiones y la confirmación antes de un cambio de estado se aplican en todos los modos. Evidencia: el modo en el encabezado.
5. **Haz coincidir la tarea con una ruta.** Compara la solicitud con los triggers en el locale solicitado, con `en` como respaldo. Si alguna ruta aplica de forma plausible, nómbrala. Si aplican varias, las skills de proceso (`strata.spec`, `strata.order`) van antes que las de implementación (`strata.build-task`). Evidencia: la ruta y el motivo en una línea.
6. **Invoca la skill.** Anuncia "using <skill> because <reason>" y síguela al pie de la letra. Crea un todo por cada elemento de la lista de verificación de esa skill. Si tras leerla la skill no encaja, dilo y vuelve al paso 5.

## Racionalizaciones

| Pensamiento | Réplica |
|---|---|
| "Es solo una pregunta simple." | Las preguntas son tareas. Imprime el encabezado y encamina. Cuesta una lectura. |
| "Necesito más contexto antes de revisar las skills." | La revisión de skills va antes de reunir contexto; una skill te dice qué contexto reunir. |
| "Recuerdo lo que dice esta skill." | Las skills cambian con la revisión del núcleo. Lee la versión actual. |
| "La skill es excesiva para este cambio." | Los cambios pequeños se vuelven grandes. Encaminar es barato; saltarse un punto de control no. |
| "Es solo lectura, así que el encabezado sobra." | La solo lectura quita los archivos, no el encabezado. El encabezado es lo que muestra las tarjetas must. |
| "El usuario tiene prisa." | El encabezado son cinco líneas. Una ruta equivocada cuesta más tiempo que imprimirlo. |

## Señales de alerta

- Una respuesta que empieza con una respuesta o una acción y sin encabezado de contexto.
- Trabajo que avanza sin una skill nombrada y sin un motivo declarado.
- Una sesión que edita archivos en un proyecto sin `.strata/profile.yaml`.
- Una tarjeta must listada en el encabezado que los pasos siguientes luego intentan esquivar con argumentos.
- Una sesión de solo lectura que edita un archivo sin pasar antes a sesión única.

## Verificación

Antes de continuar con la skill encaminada, confirma todo lo siguiente y decláralo en una línea:

- El encabezado se imprimió primero y nombra el id del proyecto y el perfil.
- Se leyeron las capas del registro o las indicó el encabezado del hook de inicio, y la ruta (o "none, because …") está nombrada.
- Se declaró el modo de trabajo.
- Se cargó la lista `required_context` de la skill encaminada.
