# ideation.shape

## Visión general

Una idea es útil mucho antes de estar terminada. Esta habilidad ayuda a la persona a ordenar una idea hasta que pueda usarse —en planificación, una especificación, una decisión o una retrospectiva— sin crear la idea por ella. Cada idea es una nota con cinco facetas (origen, problema, método, resultado, sentido). Se permiten facetas vacías; son las próximas preguntas. El agente estima cuántas condiciones y cuántas órdenes necesita todavía la idea y pide a la persona que lo confirme; el número confirmado es el peso de la idea, y la suma de los pesos de todas las ideas abiertas es la carga de reflexión que la persona lleva. Las ideas pueden crecer sin límite; a una idea sin crecimiento durante más de 30 días se le propone archivarla, nunca borrarla.

El método de preguntas y las herramientas para cuando hay bloqueo siguen jwynia/agent-skills `brainstorming` v1.1 (MIT): estados descritos como señales, preguntas e intervenciones; su protocolo de divergencia aquí es una herramienta, no el esqueleto.

## Cuándo usarla

Cuando la persona trae una idea, un problema que quiere atacar, una intuición, o está bloqueada. No para escribir requisitos (strata.spec) ni para registrar una decisión ya tomada (strata.decision): son candidatos del siguiente flujo. No para generar ideas en nombre de la persona. La conversación por sí sola es de solo lectura; escribir o hacer crecer una nota de idea eleva la sesión a sesión única (DEC-2026-11-01-18).

## Proceso

1. **Sacarla.** Ejecuta `python3 -m kb ideas list` y busca ideas abiertas parecidas y enfoques existentes (`python3 -m kb search "<las palabras de la persona>" --hybrid`). Muestra lo que existe y la carga de reflexión, y pregunta: "¿Sobre qué que ya existe podría apoyarse esto?" Ofrece tres opciones: una nota nueva, añadir a una nota existente, o reforzar lo que ya está abierto y solo apuntar esto. Evidencia: la lista y la elección de la persona.
2. **Naturaleza.** Pregunta si la idea ataca un problema o fenómeno claro, o intenta concretar una intuición difusa. Una idea de problema empieza por el problema y luego el resultado y el método; una intuición empieza por el sentido y el origen. Evidencia: `nature` en la nota.
3. **Cinco facetas.** Pregunta de una en una: qué resuelve (problema), qué quiere obtener (resultado), qué le parece significativo a la persona (sentido), qué hace para lograrlo (método), dónde empezó (origen). Escribe las palabras de la persona. Una faceta que aún no puede responder se escribe "비어 있음". Si el método está lleno y el problema o el resultado vacíos, la idea está atada a una forma: pregunta "¿Qué debe lograr esto? ¿Este método es una forma de hacerlo?" Evidencia: las secciones de facetas de la nota.
4. **Condiciones y peso.** Estima las condiciones que deben cumplirse para que la idea funcione y cuántas órdenes llevaría; un experimento mínimo puede ser una condición. Muestra la estimación y pide a la persona que la corrija o confirme. Solo entonces escribe `conditions`, `orders_expected` y `weight_confirmed`. Evidencia: la confirmación de la persona.
5. **Ampliar, acotar, eliminar.** Usa las facetas vacías como términos de búsqueda de referencias; muestra cada una con su fuente. Si los candidatos se acumulan, agrúpalos por enfoque y pide un representante y un experimento mínimo por grupo. La persona elige ampliar o acotar el objetivo y cómo eliminar: eliminación dura (quitar lo poco claro y centrarse en lo que queda) o eliminación suave (ordenarlo todo y comprimir a través de los vínculos). No evalúes mientras se llenan las facetas; elimina solo cuando la persona lo elija. Escribe los casos eliminados y sus razones en la nota. Entre ideas, `python3 -m kb ideas near <nota> [--embed]` muestra faceta por faceta lo cerca que están las demás ideas, candidatos de relación (alternativa, reutilización, agrupación, competencia) con sus valores, candidatos de vínculo y una línea de sesgo de vecindad; `python3 -m kb ideas map <nota> [--facet F]` escribe un lienzo de Obsidian centrado en la idea. Ninguno escribe la nota: añade solo los vínculos que la persona elija, cada uno con un evento `link`. Evidencia: la sección de casos eliminados.
6. **Cuando hay bloqueo.** Si todas las opciones son variaciones, diagnostica el estado por sus señales y usa solo la herramienta que corresponde: ceguera de convergencia → lista primero las opciones obvias; bloqueo de función → separa el qué (WHAT) del cómo (HOW); colapso de ejes → gira quién, cuándo, escala o método; encierro de dominio → extrae material de colisión con `python3 -m kb ideas draw --note <nota>` (primero registros fuera de los proyectos de la idea, la lista de restricciones cuando faltan registros). Pregunta con qué choca el material; la persona escribe lo que ve. Evidencia: el material mostrado y las palabras de la persona.
7. **Registrar el crecimiento y cerrar.** Por cada faceta llenada, vínculo añadido, uso en otro flujo o condición cumplida, ejecuta `python3 -m kb ideas event <nota> facet|link|use|condition "<qué>"` (una nota archivada se reabre). Luego ejecuta `python3 -m kb skills next ideation.shape` y muestra los candidatos tal cual, "no hacer nada" incluido; la persona elige. Registra la elección en el archivo activo y en la sección de juicio del traspaso. Evidencia: las líneas de evento y la elección.

## Formato de la nota

`$STRATA_VAULT/ideas/<YYYY-MM-DD>-<slug>.md`, revisada con `python3 -m kb ideas check`:

```markdown
---
title: "<la idea en palabras de la persona>"
type: idea
created: YYYY-MM-DD
nature: problem | intuition
status: active | archived
projects: [<proyectos relacionados>]
conditions:
  - {text: "<condición>", met: false}
orders_expected: 2
orders_done: 0
weight_confirmed: YYYY-MM-DD
---

# <título>

## 발단
## 문제
## 방법
## 결과
## 의미
## 소거한 사례
## 발전 기록

- YYYY-MM-DD facet — <qué creció>
```

Archivar (`python3 -m kb ideas tidy --apply`, vista previa por defecto) solo pone `status: archived` y `archived: {date, reason}`; la nota se queda donde está.

## Racionalizaciones

| Pensamiento | Refutación |
|---|---|
| "Unas ideas de ejemplo le ayudarían a empezar." | Entonces la nota contiene tus ideas. Da material y una pregunta; la persona escribe lo que ve. |
| "La faceta vacía es obvia; la lleno yo." | Una faceta vacía es la próxima pregunta. Llenarla oculta el hueco que la persona debería mirar. |
| "El peso es solo una estimación; lo escribo." | Solo un peso confirmado cuenta en la carga de reflexión. Pregunta primero. |
| "Está claro que esta idea toca planificarla." | El flujo es una sugerencia. Muestra los candidatos con "no hacer nada" y deja elegir a la persona. |
| "Esa idea no ha ido a ninguna parte; bórrala." | Se archiva, nunca se borra. Una intuición a medias puede encontrar más tarde la pieza que le falta. |

## Señales de alarma

- Una frase de faceta que la persona no dijo ni aprobó.
- Evaluar ideas mientras aún se llenan las facetas.
- Un peso sin `weight_confirmed`.
- Novedad que no sirve al problema ni al resultado.
- Idear desde cero sin haber buscado enfoques existentes.
- Tomar "lo contrario" por divergencia: sigue en el mismo eje.

## Verificación

- La nota pasa `python3 -m kb ideas check`.
- Cada frase de faceta y el peso remiten a palabras de la persona en esta sesión.
- Se registraron eventos de crecimiento para lo que cambió.
- La persona eligió el siguiente flujo entre los candidatos.
