# strata.init-wizard

## Resumen

El asistente ensambla la guía de un proyecto a partir de tarjetas de recomendación. Solo entrevista sobre lo que el código no puede responder, diagnostica el stack contra las reglas de detección del perfil, propone tarjetas con su evidencia, genera los adaptadores una vez que el usuario aprueba y verifica el resultado. También es la vía de regeneración cuando la revisión del núcleo avanza. Nunca escribe fuera de las rutas listadas en la propuesta aprobada.

## Cuándo usarlo

- Un proyecto no tiene `.strata/profile.yaml` (using-strata te envía aquí).
- El usuario pide configurar, cambiar o regenerar la guía.
- Un perfil, una tarjeta o una exención debe cambiar.
- No para el trabajo diario: ese lo encamina using-strata hacia la skill que lo tiene a su cargo.

## Proceso

1. **Diagnostica primero desde el código.** Ejecuta `python3 tools/wizard.py diagnose <project> --apply`. Lee los archivos de build y los manifiestos, aplica las reglas de detección del perfil, mide el presupuesto de lo que se carga siempre y lista lo que no pudo decidir. Evidencia: `.strata/kit/diagnosis.yaml`.
2. **Entrevista una pregunta a la vez.** Pregunta solo las preguntas abiertas del diagnóstico (tamaño del equipo, vida útil esperada, número de dominios con escrituras entre dominios, entornos compartidos, harnesses en uso). Nunca preguntes lo que el diagnóstico ya respondió. Registra cada respuesta en recommend con `--answer <clave>=<valor> --because <clave>=<motivo>` (claves `team_size`, `lifetime`, `cross_domain_writes`, `shared_envs`, `runtime`, `strata_python`); la propuesta las guarda en `answers` y el siguiente recommend las conserva. **Entorno de ejecución.** Muestra la parte `runtime` del diagnóstico —el python que ejecuta cada ruta (shell interactiva, hooks de Claude Code, MCP, launchd, sh no interactivo), las dependencias del kit que faltan y los gestores y archivos de versión encontrados— y pregunta con qué python corre el kit. Presenta las opciones con sus ventajas e inconvenientes tal como las imprime recommend (`asdf`: muchos lenguajes en un archivo, pero sus shims no están en el PATH de launchd ni de una shell no interactiva, así que necesita la ruta absoluta; `uv-venv`: aislado, reproducible desde el lockfile, instala python, un solo lenguaje; `mise`: compatible con asdf, más env y tareas; `pyenv`; `brew`·`system`: fáciles, fijación y aislamiento débiles) y la opción por defecto `uv-venv` con su motivo (el kit en un venv de uv, se conserva el gestor de runtimes de la persona). Registra la elección con `--answer runtime=<opción>`; generate escribe entonces un único STRATA_PYTHON en archivos de fragmentos bajo `.strata/kit/runtime/` (hooks y env de settings, comando MCP, EnvironmentVariables de launchd, líneas de `~/.zshenv`) y la persona los aplica: nunca edites tú los archivos del home. Evidencia: `answers` y `runtime` de la propuesta, y `tools/doctor.py` sin elementos runtime después de que la persona los aplique.
3. **Propón tarjetas.** Ejecuta `python3 tools/wizard.py recommend <project> --profile <id> [--locale ko] --apply`. Presenta cada tarjeta como: id, strength, claim, las referencias de evidencia y los contraejemplos. Las tarjetas must se explican, no se negocian. Por cada tarjeta should que el usuario rechace, registra `waived_reason`. Por cada objeción a una tarjeta must, registra un candidato counter_example (va al backlog, no al proyecto). Las tarjetas must opcionales (`adoption: opt_in`, fuera de la constitución) se preguntan: la propuesta muestra cada una con su valor por defecto (el `wizard.adopt_cards` del usuario en `~/.strata/config.yaml` y luego el `cards_default` del perfil); registra la respuesta con `--adopt <id>` o `--decline <id>=<motivo>` (el rechazo queda con su motivo en la propuesta y el registro). Las tarjetas must condicionales (`adoption: conditional`) no se preguntan: se cargan cuando su hecho se cumple en el proyecto — `uses_vault` (`--uses-vault yes|no`), `uses_quilt` (`--harness …,quilt`), `domain_work` (el dominio); di cuáles se cargaron y por qué. Pregunta el grado de aplicación por familia de reglas (`layers`, `naming`, `rules`): advisory solo registra infracciones, default falla salvo una excepción con motivo y caducidad, block falla; las familias no declaradas siguen en block. Regístralo con `--enforce <familia>=<grado>`; va al manifiesto y los verificadores se ejecutan con `kb enforce run`. Un verificador en modo aviso que imprime infracciones y termina con 0 se envuelve con `--violation-exit 0,1 --violation-pattern <su marca de infracción>`; una entrada errónea del registro no se edita: se añade una corrección con `kb enforce correct`. Evidencia: `.strata/kit/proposal.yaml` con `approved: true` puesto por el usuario.
4. **Genera.** Ejecuta `python3 tools/wizard.py generate <project> --apply`. Escribe solo las rutas listadas en la propuesta y estampa `core_revision` y `adapter_revision`. Un archivo existente escrito a mano (sin marca de generado al inicio) se conserva salvo que la propuesta lo nombre en `overwrite_handwritten`; antes, mueve su texto a `.strata/kit/notes.<locale>.md`. Evidencia: la lista de archivos escritos en la salida del comando.
5. **Verifica.** Ejecuta `python3 tools/wizard.py verify <project>`. Comprueba el presupuesto (bytes siempre cargados), los encabezados de revisión, el registro, y pasa cinco solicitudes de muestra por los triggers del registro. Evidencia: salida 0 y el informe.
6. **Registra.** Si la elección del perfil o una exención es una decisión de arquitectura para este proyecto, regístrala con el escritor de decisiones. Evidencia: el id DEC en la respuesta.

## Racionalizaciones

| Pensamiento | Réplica |
|---|---|
| "El stack es obvio, omite diagnose." | Diagnose también mide el presupuesto y encuentra desvíos. Ejecútalo; es un solo comando. |
| "El usuario conoce las reglas, omite la evidencia." | Una tarjeta sin evidencia es una opinión. Muestra las referencias; ese es todo el sentido. |
| "Esta tarjeta must no encaja aquí, exceptúala." | Una must no se exceptúa. Explícala y registra la objeción como candidato counter_example. |
| "Genera todo, que borren lo que no quieran." | Escribe solo las rutas aprobadas. Los archivos no pedidos son desvío. |
| "La verificación pasó la última vez." | La revisión del núcleo puede haber avanzado. Verifica después de cada generate. |

## Señales de alerta

- Preguntas de entrevista cuyas respuestas están en `package.json`, `build.gradle`, `go.mod` o `Cargo.toml`.
- Una propuesta con una tarjeta que no tiene entrada `evidence`.
- Un AGENTS.md generado sin `core_revision` en su encabezado.
- Archivos escritos fuera de la lista de rutas de la propuesta.

## Verificación

- `.strata/kit/proposal.yaml` existe con `approved: true` y cada tarjeta tiene evidencia.
- Cada tarjeta should exceptuada tiene `waived_reason`.
- `tools/wizard.py verify <project>` termina con salida 0 y su informe está en la respuesta.
- Toda decisión tomada está registrada y su id está en la respuesta.
