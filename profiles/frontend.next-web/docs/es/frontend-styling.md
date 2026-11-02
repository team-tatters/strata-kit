# Convención de Styling para frontend

> Fuente canónica: strata-kit `profiles/frontend.next-web/docs/es/frontend-styling.md` — migrado desde strata `docs/05-conventions/frontend-styling.md` (orden 2026.10.29-06, 2026-10-29). El YAML de reglas está en `core/rules/`.

> Límite de Core: `core/docs/es/architecture/frontend-web.md` · Contrato de diseño: `core/docs/es/architecture/frontend-design-contract.md` · Enlace de tokens: `profiles/frontend.next-web/docs/es/frontend-tokens.md`

Este documento es la convention que asigna las herramientas de estilos a las capas de Core.
Core no exige ninguna biblioteca de UI ni herramienta de CSS concreta.

## Layer Mapping

- Primitive UI decide su apariencia solo con tokens alias y los ejes variant (`variant · intent · size · state`).
- Un Semantic Component decide su apariencia solo mediante una combinación de valores de ejes de Primitive y tokens alias (Composition Legality).
- Un Feature Block es un fragmento de pantalla de un use case concreto y también expresa el layout mediante alias (space · radius).

## Reglas de valores de ejes

- El valor de un eje de color es una intención (`intent`). No se usan nombres de paleta (`green · red · blue`) como valores de eje.
- Si se necesita un estado de dominio (por ejemplo `pending · completed`), no se mezcla en `intent`; se deja en un eje `status` aparte.
- Los nombres de las propiedades de los componentes en la herramienta de diseño y los nombres de props en el código se mantienen iguales: es la premisa de la comprobación de coherencia.

## Project-Specific Mapping

Opciones como MUI, Tailwind, CSS-in-JS y paquetes de design-system van en el profile del proyecto o en una extensión específica del proyecto de esta convention.
Se use la herramienta que se use, la regla es la misma: las clases de utilidad y los objetos de estilo reflejan los nombres alias, y los valores raw y los nombres T1 no aparecen fuera de Foundation.
Esa elección no es una regla de Core, sino un constraint del proyecto.
