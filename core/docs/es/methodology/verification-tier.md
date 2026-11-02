# Nivel de verificación (Verification Tier)

> Canónico: strata-kit `core/docs/es/methodology/verification-tier.md` (migrado el 2026-10-29 desde strata `docs/04-agents/verification-tier.md`, DEC-2026-10-29-11).

> Un eje de independencia de la verificación, ortogonal al modo de ejecución (Verbal/Task).
> El modo de ejecución trata de *cómo se trabaja*; el nivel de verificación define *quién verifica el resultado*.
> Este documento es la source of truth del enum `verification_tier`.

## Definiciones de Tier

| Tier | valor del enum | Definición | Independencia de la verificación |
|------|----------------|------------|----------------------------------|
| **Solo** | `solo` | Quien ejecutó verifica con su propia lista de comprobación | Ninguna |
| **Self-Verified** | `self_verified` | Verifica un Reviewer independiente dentro del mismo entorno de ejecución/familia de herramientas | Media |
| **Cross-Verified** | `cross_verified` | Verifica un Reviewer de otro entorno de ejecución, familia de herramientas o familia de modelos | Alta |

- Los nombres de herramientas no se escriben en Core. Las correspondencias como "ejecuta X → verifica Y" van en el adaptador de cada herramienta (AGENTS.md, settings).
- El Reviewer no ve toda la conversación, sino solo **la solicitud + el diff + las reglas + los resultados de las pruebas + la lista de comprobación**.
- El nombre que se muestra es `Cross-Verified`; el valor del enum que se escribe en `_order.yaml` es `cross_verified`.

## Valores por defecto y rango obligatorio

```text
Verbal Mode: si se omite verification_tier → solo
Task Mode:   se recomienda indicar verification_tier en _order.yaml
Cambios en una fuente de verdad de Core (layer-rules / naming-convention / task-spec-schema / agent-roles):
             → cross_verified obligatorio
Otros cambios en documentos y adaptadores de Core (core/docs/, core/templates/, etc.):
             → cross_verified recomendado
```

No se hace declarar un Tier por cada modificación pequeña. Si el coste de declarar supera el beneficio de verificar, Strata se vuelve pesado.

## Patrones de implementación

El TDD Writer/Reviewer (`core/docs/es/methodology/session-splitting.md` §2.4) es uno de los patrones de implementación del Tier Self/Cross-Verified.
El documento session-splitting trata de cómo dividir las sesiones; este documento contiene el significado de la independencia de la verificación y el enum.

La implementación concreta en herramientas de Cross-Verified la cubre `skills/strata.review/SKILL.md`.
Esa skill es el procedimiento que realiza de hecho el `cross_verified` de este documento; este documento no define el procedimiento.

## Relación con otros ejes

- **Execution Mode**: la elección y el cambio entre Verbal/Task los define `core/docs/es/methodology/execution-modes.md`.
- **Agent Operations**: el `reviewer: cross_verified` del Decision Inbox usa este Tier. La disciplina operativa la define `core/docs/es/methodology/agent-operations.md`.
- **Methodology Feedback Loop**: las lagunas de metodología que encuentra un Reviewer se registran en el backlog y se promueven mediante el flujo de Promotion Gate de `core/docs/es/methodology/task-spec-schema.md`.

## Eje de verificación del diseño (design_verified)

El tercer eje, ortogonal al modo de ejecución y al nivel de verificación. Define quién comprobó **la coherencia entre el entregable de diseño y la implementación** (`core/docs/es/architecture/frontend-design-contract.md` §Artefactos de diseño y alineación).
Este documento es la source of truth del enum `design_verified` de `_order.yaml`.

| Valor | Definición |
|---|---|
| `none` | Sin entregable de UI (`design_ref.kind: none`), o sin verificar |
| `self` | El implementador lo contrastó por su cuenta con la definición de coherencia (nombre, eje, alias, eje de estado) |
| `designer` | Lo confirmó el responsable del entregable de diseño (el diseñador o el encargado de la herramienta de diseño) |
| `cross` | Lo confirmó un Reviewer de otro entorno de ejecución o modelo, comparando el render del story o los frames |

Valores por defecto y rango obligatorio:

```text
Sin design_ref, o kind: none → none
Primitive UI · Semantic Component nuevo/modificado (paquete de UI compartido) → se recomienda designer o superior
Feature Block · Route Surface → self o superior
```

Si `completion.design_sync` es `stale`, el trabajo no está completo, sea cual sea el valor de este eje. `waived` lleva un motivo y una fecha de caducidad.
