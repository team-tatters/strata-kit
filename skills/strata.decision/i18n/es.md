# strata.decision

## Resumen

Registra una decisión de arquitectura como un registro duradero con el escritor de decisiones, en la misma sesión en que se tomó, y extrae un candidato a tarjeta de recomendación cuando la decisión se generaliza más allá de este proyecto.

## Cuándo usarlo

En el momento en que se toma o se descubre una elección duradera. No para elecciones locales de implementación que un cambio posterior puede revertir sin tocar un contrato.

## Proceso

1. Enuncia la decisión en una frase, el motivo y las alternativas consideradas. Evidencia: el texto.
2. Ejecuta el escritor de decisiones con topic, decision, reason, affects. Pasa cada alternativa considerada con --alternative 'opción: por qué se descartó' y los conceptos o fuentes consultados con --background, para que una retrospectiva posterior vea lo que no se eligió (DEC-2026-10-30-03). Evidencia: el id DEC y la ruta del índice regenerado.
3. Si se reemplaza un registro anterior, ejecuta supersede; si se retira, ejecuta withdraw. Evidencia: la salida de la CLI.
4. Si la decisión se generaliza, redacta un candidato a tarjeta (claim, strength, evidence = este DEC) en el backlog. Evidencia: la ruta del candidato.
5. Pon el id DEC en decisions_made del traspaso.

## Racionalizaciones

| Pensamiento | Réplica |
|---|---|
| "Lo registraré al final de la sesión." | Las sesiones terminan de golpe. Regístralo ahora; es un solo comando. |
| "Es obvio, nadie necesita un registro." | La próxima sesión no eres tú. El registro es para ella. |
| "Puedo editar el índice directamente." | El índice se genera. Las ediciones manuales se sobrescriben y el registro se pierde. |

## Señales de alerta

- Una decisión enunciada en el chat sin id DEC.
- Un índice editado a mano.
- Una regla reemplazada que sigue citándose como vigente.

## Verificación

- El id DEC está en la respuesta.
- El índice fue regenerado por la CLI.
- decisions_made del traspaso está actualizado.
